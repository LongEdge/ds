"""
任务分发: init -> ready
"""
from queue import Queue
from apscheduler.schedulers.background import BackgroundScheduler
from collections import defaultdict
import json
import requests
import threading


MAXSIZE_QUEUE = 1 # 最大队列个数



class CScheduler():
    """
    构造模型应用类型列表
    """
    def __init__(self, sql_monitor, plt_app_url):
        self.sql_monitor = sql_monitor
        self.plt_app_url = plt_app_url
        self.model_type_queue_dict = {} # 封装应用类型队列, 且最大列表为1
        """
        self.model_type_queue_dict = {
            "face_landmark": Queue: [report_id],
            "slim_wrinkle": Queue: [report_id],
            "bold_wrinkle": Queue: [report_id]
        }
        """
        self.select_reportid_dicts = defaultdict(lambda: defaultdict(int))
        """
        select_reportid_dicts = {
            "report_id1": {
                "task_type": "xx",
            },
            "report_id2": {
                "task_type": "xx",
            },
            
        }
        """
        self.lock = threading.Lock()  # 锁对象
        self.auto_scheduler()


    """
    循环热键更新
    """
    def auto_update_model_type(self):
        try:
            # 请求 plt_app_url 平台应用 url 更新模型类型列表
            response = requests.get(self.plt_app_url)
            if response.status_code != 200:
                print(f"请求模型应用类型列表失败, status_code: {response.status_code}")
                return
            # 解析返回的JSON数据
            type_list_dict = json.loads(response.text)["rows"]
            new_model_type_list = []

            # 获取模型类型列表
            if len(type_list_dict) > 0:
                for type_item in type_list_dict:
                    new_model_type_list.append(type_item["typeName"])

            # 加锁，更新 model_type_list 和 model_type_queue_dict
            with self.lock:
                # 更新 model_type_list
                self.model_type_list = new_model_type_list

                # 获取现有队列中的类型
                existing_types = set(self.model_type_queue_dict.keys())

                # 获取新的模型类型
                new_types = set(new_model_type_list)

                # 删除旧的模型类型队列（如果不在新的模型列表中）
                for old_type in existing_types - new_types:
                    del self.model_type_queue_dict[old_type]
                    print(f"Removed queue for model type: {old_type}")

                # 添加新的模型类型队列（如果不在现有队列中）
                for new_type in new_types - existing_types:
                    self.model_type_queue_dict[new_type] = Queue(maxsize=MAXSIZE_QUEUE)
                    print(f"Added queue for model type: {new_type}")

        except Exception as e:
            print(f"请求模型应用类型列表失败2, Exception: {e}")
            return

    """
    定时处理init任务
    """
    def auto_scheduler(self):
        scheduler_monitor = BackgroundScheduler()
        # scheduler_monitor.add_job(func=self.auto_prepare_task, args=(), trigger='interval', seconds=0.2)
        # scheduler_monitor.add_job(func=self.auto_appoint_task, args=(), trigger='interval', seconds=0.2)
        # scheduler_monitor.add_job(func=self.auto_update_model_type, args=(), trigger='interval', seconds=5)
        scheduler_monitor.add_job(func=self.monitor_node_info, args=(), trigger='interval', seconds=2)

        scheduler_monitor.start()

    """
    获取基于模型类型的队列
    """
    def get_model_type_queue(self):
        return self.model_type_queue_dict

    """
    自动准备任务
        """
    def auto_prepare_task(self):
        # 自动选择任务到对应的应用队列里
        with self.lock:
            for task_type in self.model_type_list:
                if self.model_type_queue_dict[task_type].full():
                    # 如果队列是满的就跳过
                    continue
                report_id = self.sql_monitor.auto_select_init_task(task_type) # 选择符合条件的report_id
                if None == report_id:
                    continue
                # 选择此report_id的候选节点
                task_info = self.sql_monitor.query_task_info_by_report_id(report_id)
                try:
                    task_info = json.loads(task_info)
                    if {} == task_info:
                        continue
                except Exception as e:
                    print("解析task_info失败, Exception: {}".format(e))
                    
                    self.sql_monitor.update_appoint_task_status(report_id, 2)
                    continue
                candidate_nodes = task_info['candidate_nodes']
                queue_data = {
                    "report_id": report_id, # 报告id
                    "candidate_nodes": candidate_nodes # 此报告id候选的节点
                }
                self.model_type_queue_dict[task_type].put(queue_data)


    """
    自动指派任务
    """
    def auto_appoint_task(self):
        # 循环self.model_type_queue_dict
        node_free_status = 2 # 2=在线
        with self.lock:
            for _, type_queue in self.model_type_queue_dict.items():
                if type_queue.empty():
                    continue
                queue_data = type_queue.queue[0]
                report_id = queue_data['report_id']
                candidate_nodes = queue_data['candidate_nodes']
                # 根据report_id从task_init选择候选的节点
                free_nodes = self.sql_monitor.query_node_by_status(node_free_status) # 所有空闲的节点
                print("candidate_nodes: ", candidate_nodes)
                print("free_nodes: ", free_nodes)

                # 策略选择一个可用的节点
                select_free_node = None
                for free_node in free_nodes:
                    if free_node in candidate_nodes:
                        select_free_node = free_node
                        break

                if None == select_free_node:
                    continue
                else:
                    # 1. 指派此节点到对应的报告上
                    appoint_res_code = self.sql_monitor.appoint_task(report_id, select_free_node) # 1=succ, 0=failed
                    # 2. 更新此任务的状态, task_init的is_appointment0->1且弹出任务
                    update_task_res_code = self.sql_monitor.update_appoint_task_status(report_id, 1) # 1=succ, 0=failed
                    if update_task_res_code == appoint_res_code:
                        # 如果指派成功, 就把这个任务从队列里弹出
                        type_queue.get()



    """
    定时节点的状态: 是否挂掉等
    """
    def monitor_node_info(self):
        self.sql_monitor.auto_update_node_live_status_by_master() # 更新节点状态
        self.sql_monitor.auto_del_invaild_node() # 删除无用节点
        self.sql_monitor.auto_clean_invalid_task() # 清除无用任务