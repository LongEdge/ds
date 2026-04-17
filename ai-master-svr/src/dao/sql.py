import sqlite3
import time
import json
from src.utils.SysLogger import CSysLogger
logger = CSysLogger('sql')

NODE_SAVE_DAYS = 7 * 24 * 3600 # 离线节点默认保留7天


class Sql:
    def __init__(self):
        self.conn = sqlite3.connect('test.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.c = self.conn.cursor()
        sql = 'create table if not exists Query(node_no integer ,' \
              'report_id VARCHAR(255)  ,db_id integer ,deal_status varchar(25) , ready_time integer , start_time integer , end_time integer)'
        self.c.execute(sql)
        self.conn.commit()
    

    """
    获取连接
    """
    def get_conn(self):
        return self.conn    
        
    """
    创建一条任务
    """
    def add_query_by_type(self, report_id, deal_type_no, submit_param, deal_port):
        try:
            sql = "SELECT db_id, deal_status, start_time, end_time FROM Query WHERE report_id = ? and deal_type_no = ?"
            param = [report_id, deal_type_no]
            now = int(time.time())
            cursor = self.c.execute(sql,param)
            nUpdateId = -1
            for row in cursor:
                if row[1] == 'ready' or (row[1] == 'running' and (now - row[2] < 480)):  # 开始运行8分钟内不能重新插入
                    print('already has same id in ready or running deal_status')
                    return -1, '记录已经存在, 请不要重复提交'
                elif (row[1] =='running' and (now - row[2] >= 480) ) : #运行时间超过8分钟，可以重新计算,即修改状态为ready
                    nUpdateId = row[0]
                elif ((row[1] =='ok') and (now - row[3] < 120)) : #刚完成的2分钟内不能重复提交
                    print('this reportid just completed the calculation task ,please resubmit after 2 minites')
                    wait_time = 120 - (now - row[3])
                    return -1, '此任务已完成, 重新提交请{}秒后重试'.format(wait_time)
                elif ((row[1] =='failed') and (now - row[3] >= 120)) : #完成计算2分钟后可以再次计算
                    nUpdateId = row[0] 

            print("nUpdateId: ", nUpdateId)

            if nUpdateId == -1 : #表示需要插入新的数据
                sql = "SELECT db_id FROM Query order by db_id desc limit 1"
                num = 1
                cursor = self.c.execute(sql)
                for row in cursor:
                    num = row[0] + 1
                    break
                param_inert = [num, deal_port, deal_type_no, report_id, now, submit_param]
                sql = "INSERT into Query VALUES(?,?,?,?,'init',?,0,0,?,0,0,'{}','{}', '[-1, -1]')"#末尾两位：默认优先级1  run_num= 0
                logger.info(sql)
                self.c.execute(sql, param_inert)
                self.conn.commit()
            elif nUpdateId > -1 : # 更新数据
                param_update = [now,nUpdateId]
                sql = "UPDATE Query SET deal_status ='ready',node_no = 0 , ready_time = ?, start_time =0, end_time = 0 WHERE db_id = ?"
                self.c.execute(sql, param_update)
                self.conn.commit()
            return 0, '添加任务成功'
        except sqlite3.IntegrityError as e:
            print(str(e))
            return -1, '添加任务异常, 请联系管理员 - 错误: {}'.format(e)
        
    """
    创建一条任务
    """
    def add_task_info(self, report_id, task_type, task_info):
        try:
            # 获取db_id
            sql = "SELECT db_id FROM Query order by db_id desc limit 1"
            db_id = 1
            cursor = self.c.execute(sql)
            for row in cursor:
                db_id = row[0] + 1
                break

            sql = "INSERT into task_init VALUES(?,?,?,?,0)"#末尾两位：默认优先级1  run_num= 0
            param_inert = [db_id, report_id, task_type, task_info]
            logger.info(sql)
            self.c.execute(sql, param_inert)
            self.conn.commit()
            return 0, '添加任务信息成功'
        except sqlite3.IntegrityError as e:
            print(str(e))
            return -1, '添加任务信息异常, 请联系管理员 - 错误: {}'.format(e)

     
    """
    插入一条任务的进度日志
    """
    def add_task_log(self, report_id, deal_type_no, task_info):
        try:
            deal_time = task_info['deal_time']
            task_info.pop("deal_time", None)
            task_info = json.dumps(task_info)
            param_inert = [deal_type_no, report_id, deal_time, task_info]
            sql = "INSERT INTO task_log_info (node_no, report_id, deal_time, task_info) VALUES(?,?,?,?)"#末尾两位：默认优先级1  run_num= 0
            logger.info(sql)
            self.c.execute(sql, param_inert)
            self.conn.commit()
            
        except sqlite3.IntegrityError as e:
            print(str(e))
            print(report_id + ' add task log is error!')
            return
    
    """
    高效批量插入任务进度日志
    使用 INSERT ... VALUES (...), (...), (...) 语法一次性插入多条
    """
    def add_task_logs_batch(self, report_id, deal_type_no, task_info_list):
        if not task_info_list:
            return

        try:
            values_list = []
            for task_info in task_info_list:
                deal_time = task_info.get('deal_time')
                task_info_copy = task_info.copy()
                task_info_copy.pop("deal_time", None)
                task_info_json = json.dumps(task_info_copy)
                # 注意：SQLite 的字符串需要单引号包裹，并转义单引号
                task_info_json = task_info_json.replace("'", "''")
                values_list.append(f"('{deal_type_no}', '{report_id}', {deal_time}, '{task_info_json}')")

            # 拼接 SQL
            values_str = ", ".join(values_list)
            sql = f"INSERT INTO task_log_info (node_no, report_id, deal_time, task_info) VALUES {values_str}"
            logger.info(f"批量插入 SQL 长度: {len(values_list)}")
            self.c.execute(sql)
            self.conn.commit()
            logger.info(f"成功批量插入 {len(values_list)} 条任务进度日志")
        except sqlite3.IntegrityError as e:
            logger.error(f"{report_id} 批量插入任务日志出错: {e}")
        except Exception as e:
            logger.error(f"批量插入异常: {e}")

    """
    查询一条任务的进度日志
    """
    def query_task_log(self, node_no, report_id, page_no=1, page_size=50):
        """
        分页查询指定 node_no 的 task_log_info 日志，按 deal_time 倒序排序。
        :param node_no: 节点编号
        :param page_no: 页码，从 1 开始
        :param page_size: 每页条数，默认 50
        :return: {
            'records': 查询结果列表,
            'total_count': 总记录数,
            'total_page': 总页数,
            'page_no': 当前页码
        }
        """
        try:
            page_no = int(page_no)
            page_size = int(page_size)
            offset = (page_no - 1) * page_size
            if "" == report_id:
                condition_count_tuple = (node_no,)
                condition_log_tuple = (node_no, page_size, offset)
                count_sql = """
                    SELECT COUNT(*) FROM task_log_info
                    WHERE node_no = ?
                """
                sql = """
                    SELECT node_no, report_id, task_info
                    FROM task_log_info
                    WHERE node_no = ?
                    ORDER BY id DESC
                    LIMIT ? OFFSET ?
                """
            else:
                condition_count_tuple = (node_no,report_id)
                condition_log_tuple = (node_no, report_id, page_size, offset)
                count_sql = """
                    SELECT COUNT(*) FROM task_log_info
                    WHERE node_no = ? and report_id = ?
                """
                sql = """
                    SELECT node_no, deal_time, report_id, task_info
                    FROM task_log_info
                    WHERE node_no = ? 
                    AND report_id = ?
                    ORDER BY deal_time DESC
                    LIMIT ? OFFSET ?
                """
            
            self.c.execute(count_sql, condition_count_tuple)
            total_count = self.c.fetchone()[0]
            total_page = (total_count + page_size - 1) // page_size

            # 查询分页数据
            logger.info(f"分页查询 SQL：{sql} | node_no={node_no}, page_no={page_no}")
            self.c.execute(sql, condition_log_tuple)
            records = self.c.fetchall()
            columns = ["node_no", "deal_time", "report_id", "task_info"]

            new_records = []
            for row in records:
                item = dict(zip(columns, row))

                # 原task_info如是JSON字符串则loads成字典，否则创建空字典
                task_info = json.loads(item["task_info"]) if item["task_info"] else {}

                # 👇把deal_time移动进task_info里
                task_info["deal_time"] = item["deal_time"]

                # 修改records结构
                item["task_info"] = task_info
                item.pop("deal_time", None)   # 删除外层deal_time字段

                new_records.append(item)

            records = new_records # 日志的task_info要被序列化成字典
            return {
                'records': records,
                'total_count': total_count,
                'total_page': total_page,
                'page_no': page_no
            }

        except Exception as e:
            logger.error(f"分页查询失败: {str(e)}")
            return {
                'records': [],
                'total_count': 0,
                'total_page': 0,
                'page_no': page_no
            }


    """
    @desc: 查询报告的信息
    @params: report_id 报告id
    @return: ok failed running error not found
    """
    # 里要返回任务所有的字段    
    def get_task_info(self, report_id):
        try:
            sql = "SELECT * FROM Query WHERE report_id = ?"
            self.c.execute(sql, (report_id,))
            result = self.c.fetchone()
            if result:
                res = dict(result)
                
                # 自动把 JSON 字符串字段转回字典
                for key in ['progress']:  # 这里列出需要自动转换的字段，不包括 param
                    if key in res and res[key]:
                        try:
                            res[key] = json.loads(res[key])
                        except json.JSONDecodeError:
                            pass  # 如果不是 JSON 字符串就保持原样
                
                # 删除 param
                res.pop('param', None) # 业务要求
                
                return res  # 字典格式返回完整记录
            return {'status': 'not found'}
        except sqlite3.Error as e:
            return {'error': str(e)}



    """
    移除任务
    """
    def remove_task(self, report_id):
        try:
            # 删除日志
            sql_log = "DELETE FROM task_log_info WHERE report_id = ?"
            param = [report_id]
            self.c.execute(sql_log, param)
            self.conn.commit()

            sql = "DELETE FROM Query WHERE report_id = ?"
            param = [report_id]
            self.c.execute(sql,param)
            self.conn.commit()


            return 1
        except sqlite3.IntegrityError as e:
            return 0
            
    """
    移除所有的任务
    """
    def remove_all_task(self):
        try:
            sql = "DELETE FROM Query"
            self.c.execute(sql)
            self.conn.commit()
            return 1
        except sqlite3.IntegrityError as e:
            return 0
        

    """
    强制提交的条件: 这条记录已经存在
    逻辑: 更新已经存在的任务, 将这条记录的状态重新更新成ready
    """
    def prior_add_query(self, report_id):
        try:
            now = int(time.time())
            sql = "SELECT db_id FROM Query WHERE report_id = ?"
            db_id = -1
            cursor = self.c.execute(sql, [report_id])
            for row in cursor:
                db_id = row[0]
                break

            param_update = [now,db_id]
            sql = "UPDATE Query SET deal_status ='ready', ready_time = ?, start_time =0, end_time = 0, priority = -1 WHERE db_id = ?"

            self.c.execute(sql, param_update)
            self.conn.commit()

        except sqlite3.IntegrityError as e:
            print(str(e))
            print(report_id + ' add query is error!')
            return

    """
    取出一个任务,分布式节点向master请求任务调用
    总体逻辑如下:
        1. 开发模式
            节点处于开发状态, 节点仅关心此节点相关联的任务, 开发模式在节点中设置debug;
        2. 发布模式
            节点处于发布状态, 有如下情况按需处理
                2.1 状态1: 指定某个节点计算某条任务, 那么此任务仅会被此节点执行且此节点全量关注此任务直到任务完整生命周期结束；
                2.2 状态2: 当不存在状态1且自身关联的任务状态都是成功时, 则任取一个符合条件的任务进行计算;
                2.3 状态3: 状态1和状态2不存在时则让节点进行下一轮请求;
                2.4 完整的生命周期指: 任务最多无人值守自动处理3次, 超过3次则自动PASS此任务;
    """
    def handle(self, node_no, deal_type_no, dev_mode):
        if 1 != 1:
            # 每天0点清理历史任务
            a = time.localtime(time.time())
            if a.tm_hour == 0 and 0 < a.tm_min < 6:
                sql = "DELETE FROM Query WHERE deal_status IN ('ok', 'failed')"
                self.c.execute(sql)
                self.conn.commit()

        now = int(time.time())
        starttime = now - 480   # 8 分钟前
        endtime = now - 60      # 1 分钟前

        # -------------------------------------------------
        # 1. 优先取出绑定当前节点的任务
        # -------------------------------------------------
        if "debug" == dev_mode:
            """
            debug模式下仅关心自身相关联的任务
            """
            sql = """
                SELECT report_id, param, db_id, run_num, node_no
                FROM Query
                WHERE node_no = ?
                AND deal_type_no = ?
                AND deal_status = 'ready'
                ORDER BY priority ASC, ready_time
                LIMIT 1
            """
            params = [node_no, deal_type_no]
            cursor = self.c.execute(sql, params)
            row = cursor.fetchone()

            if row:
                report_id, process_param, db_id, run_num, node_no = row
                run_num += 1
                sql1 = """
                    UPDATE Query
                    SET deal_status = 'running',
                        start_time = ?,
                        run_num = ?
                    WHERE db_id = ? AND node_no = ?
                """
                self.c.execute(sql1, [now, run_num, db_id, node_no])
                self.conn.commit()
                return report_id, process_param, db_id, deal_type_no
            else:
                return None, None, None, None
        else:
            # -------------------------------------------------
            # 2. 没有绑定任务，就取一个未指定节点的公共任务
            # -------------------------------------------------

            # 2.1 首先查找自己计算过并且状态是失败的节点, 或者状态是运行中并且运行时间超过8分钟的任务
            sql = """
                SELECT report_id, param, db_id, run_num
                FROM Query
                WHERE deal_type_no = ?
                AND node_no  = ?
                AND (
                    deal_status = 'ready'
                    OR (deal_status = 'running' AND start_time < ?)
                    OR (deal_status = 'failed' AND run_num < 4 AND end_time < ?)
                )
                ORDER BY priority ASC, ready_time
                LIMIT 1
            """
            params = [deal_type_no, node_no, starttime, endtime]
            cursor = self.c.execute(sql, params)
            row = cursor.fetchone()
            if row:
                report_id, process_param, db_id, run_num = row
                run_num += 1
                sql1 = """
                    UPDATE Query
                    SET node_no = ?, deal_status = 'running',
                        start_time = ?, run_num = ?
                    WHERE db_id = ? AND deal_type_no = ?
                """
                self.c.execute(sql1, [node_no, now, run_num, db_id, deal_type_no])
                self.conn.commit()
                return report_id, process_param, db_id, deal_type_no


            # 2.2 如果没找到关于自己的任务, 就取一个任意取一个未指定的就绪状态公共任务
            sql = """
                SELECT report_id, param, db_id, run_num
                FROM Query
                WHERE deal_type_no = ?
                AND (node_no IS NULL OR node_no = '' OR node_no = '-1')
                AND (deal_status = 'ready')
                ORDER BY priority ASC, ready_time
                LIMIT 1
            """
            params = [deal_type_no]
            cursor = self.c.execute(sql, params)
            row = cursor.fetchone()

            if row:
                report_id, process_param, db_id, run_num = row
                run_num += 1
                sql1 = """
                    UPDATE Query
                    SET node_no = ?, deal_status = 'running',
                        start_time = ?, run_num = ?
                    WHERE db_id = ? AND deal_type_no = ?
                    AND (node_no IS NULL OR node_no = '' OR node_no = '-1')
                """
                self.c.execute(sql1, [node_no, now, run_num, db_id, deal_type_no])
                self.conn.commit()
                return report_id, process_param, db_id, deal_type_no

            # -------------------------------------------------
            # 3. 没有任务就返回全None, 等待下一轮
            # -------------------------------------------------
            return None, None, None, None
        

    """
        指派任务的处理节点
    """
    def appoint_task(self, report_id, node_no):
        sql = """
            UPDATE Query
            SET node_no = ?, 
            deal_status = 'ready'
            WHERE report_id = ?
        """
        try:
            db_params = [node_no, report_id]
            c = self.conn.cursor()
            c.execute(sql, db_params)
            self.conn.commit()
            c.close()
            return 1
        except sqlite3.IntegrityError as e:
            return 0

    """
        更新指派任务为无需指派: 0=未指派, 1=指派成功, 2=指派失败
    """
    def update_appoint_task_status(self, report_id, appoint_code):
        sql = """
            UPDATE task_init
            SET is_appointment = ?
            WHERE report_id = ?
        """
        try:
            db_params = [appoint_code, report_id]
            self.c.execute(sql, db_params)
            self.conn.commit()
            return 1
        except sqlite3.IntegrityError as e:
            return 0


    """
    查询空闲(状态为2)的节点: 0=离线, 1=运行, 2=在线
    """
    def query_node_by_status(self, node_status):
        try:
            nodes = []   # 工具编号
            sql = "SELECT node_no FROM node_info WHERE node_status = ?"
            param = [node_status]
            c = self.conn.cursor()
            cursor = c.execute(sql, param)
            for row in cursor:
                nodes.append(row[0])
            c.close()
            return nodes
        except sqlite3.IntegrityError as e:
            return []
    
    """
    查询report_id的候选节点    
    """
    def query_task_info_by_report_id(self, report_id):
        try:
            sql = "SELECT task_info FROM task_init WHERE report_id = ?"
            param = (report_id,)   # tuple更标准

            c = self.conn.cursor()
            cursor = c.execute(sql, param)
            row = cursor.fetchone()
            c.close()
            if row is None:
                return None

            task_info = row[0]
            return task_info

        except sqlite3.Error as e:
            return {}


    """
    主动汇报心跳数据
    """
    def report_node_live_status(self, node_no, node_op_status):
        sql = "UPDATE node_info SET node_live_time_last = ?, node_status = ? WHERE node_no = ?"
        now = int(time.time())
        param = [now, node_op_status, node_no]
        self.c.execute(sql,param)
        self.conn.commit()
        
        return True


    # 获得master的描述信息
    def get_master_info(self):
        try:
            master_info_list = []   # 工具编号
            sql = "SELECT DISTINCT deal_type_no, deal_type_version FROM node_info"
            param = []
            cursor = self.c.execute(sql, param)
            for row in cursor:
                data = {
                    'deal_type_no': row[0],
                    'deal_type_version': row[1],
                }
                master_info_list.append(data)

            return master_info_list
        except sqlite3.IntegrityError as e:
            return ""
        
    # 获得master下的节点的所有信息: 是否运行等
    def get_node_info_by_master(self, page_no=1, page_size=50):
        """
        分页查询指定 的 node_info 记录
        :param page_no: 页码，从1开始
        :param page_size: 每页记录数
        :return: {
            'records': 当前页数据列表,
            'total_count': 总记录数,
            'total_page': 总页数,
            'page_no': 当前页码
        }
        """
        try:
            page_no = int(page_no)
            page_size = int(page_size)
            offset = (page_no - 1) * page_size

            # 查询总记录数
            count_sql = "SELECT COUNT(*) FROM node_info"
            self.c.execute(count_sql)
            total_count = self.c.fetchone()[0]
            total_page = (total_count + page_size - 1) // page_size

            # 查询分页数据
            sql = """
                SELECT node_no, node_status, deal_type_no, deal_type_version, node_loc, node_live_time_last
                FROM node_info Order By node_status DESC
                LIMIT ? OFFSET ?
            """
            self.c.execute(sql, (page_size, offset))
            rows = self.c.fetchall()

            columns = ['node_no', 'node_status', 'deal_type_no', 'deal_type_version', 'node_loc', 'node_live_time_last']
            records = [dict(zip(columns, row)) for row in rows]
            
            # 计算节点的过期时间: 离线大于7天的节点将被删除
            now = int(time.time())
            for item in records:
                 # 取出时间戳并转为 int
                live_time = int(item.get('node_live_time_last', 0))
                item['node_exp_remain_time'] = self.format_seconds2day(NODE_SAVE_DAYS - (now - live_time))   # 节点过期时间提醒
                item.pop('node_live_time_last', None) # 移除node_live_time_last

            return {
                'records': records,
                'total_count': total_count,
                'total_page': total_page,
                'page_no': page_no
            }

        except sqlite3.IntegrityError as e:
            # 这里你可以考虑打印日志或者记录异常
            return {
                'records': [],
                'total_count': 0,
                'total_page': 0,
                'page_no': page_no
            }

    """
    计算天数
    """
    def format_seconds2day(self, sec):
        if sec < 0: sec = 0
        d = sec // 86400
        h = (sec % 86400) // 3600
        m = (sec % 3600) // 60
        return f"{d}天{h}小时{m}分钟"
        
    
    """
    master监控并更新节点的状态: 这里只设置为: 0=死, 活着的状态
    node节点会自己更新为: 1=running 2=waiting
    这里不需要锁表: 一旦node挂了超过1分钟那肯定挂了, master直接更新就行了

    """    
    def auto_update_node_live_status_by_master(self):
        try:
            now = int(time.time())
            # 更新已经挂了的但是没更新的节点, 超过1分钟不汇报心跳就认为就挂了
            sql = "UPDATE node_info SET node_status = 0 WHERE node_status != 0 AND ABS(node_live_time_last - ?) > 5" 
            param = [now]
            self.c.execute(sql, param)
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            return ""
        
    """
    自动移除无效的节点, 规则: 上一次心跳大于7天的节点
    """
    def auto_del_invaild_node(self):
        try:
            now = int(time.time())
            # 更新已经挂了的但是没更新的节点, 超过1分钟不汇报心跳就认为就挂了
            sql = "DELETE FROM node_info WHERE node_status = 0 AND ABS(node_live_time_last - ?) > 7 * 24 * 3600" 
            param = [now]
            self.c.execute(sql, param)
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            return ""

    """
    自动移除无效的任务, 规则: 上一次处理时间: ok且大于3天|failed且>7天
    """
    def auto_clean_invalid_task(self):
        try:
            now = int(time.time())
            sql1 = """SELECT report_id FROM Query 
                WHERE ((deal_status = 'ok') AND ABS(ready_time - ?) > 3 * 24 * 3600)
                OR ((deal_status = 'failed') AND ABS(ready_time - ?) > 7 * 24 * 3600)
            """
            self.c.execute(sql1, (now, now))
            report_ids = [row[0] for row in self.c.fetchall()]

            if report_ids:
                # 删除日志
                sql_log = "DELETE FROM task_log_info WHERE report_id IN ({})".format(
                    ",".join("?" * len(report_ids))
                )
                self.c.execute(sql_log, report_ids)

                # 删除任务
                sql_task = """DELETE FROM Query 
                    WHERE ((deal_status = 'ok') AND ABS(ready_time - ?) > 3 * 24 * 3600)
                    OR ((deal_status = 'failed') AND ABS(ready_time - ?) > 7 * 24 * 3600)
                """
                self.c.execute(sql_task, (now, now))

            self.conn.commit()

        except sqlite3.IntegrityError:
            return ""
        

    """
    master调度任务: 根据策略, init->ready 为任务指定节点
    """    
    def auto_select_init_task(self, task_type):
        sql = """
                SELECT db_id, report_id
                FROM task_init
                WHERE task_type = ?
                AND is_appointment = 0
                ORDER BY db_id ASC
                LIMIT 1
            """
        params = [task_type]
        c = self.conn.cursor()
        cursor = c.execute(sql, params)
        row = cursor.fetchone()
        c.close()
        if row is None:
            return None
        
        db_id = row[0]
        report_id = row[1]
        return report_id
        
    
    """
    master调度任务: 根据策略, init->ready 为任务指定节点
    """    
    def auto_update_init_task(self, distribute_dicts):
        try:
            # 0. 提交任务, 需要task_info表, 记录increase_db_id, report_id, task_info(有模型类型), is_appointment(0=未指派,1=已指派)
            # 0.1 这里要维护一个跟类型相关的列表

            # 1. 我查询这条任务可用的所有节点, 查询节点状态为空闲的节点作为指定的节点

            ids = list(distribute_dicts.keys())

            case_sql = " ".join(
                [f"WHEN '{k}' THEN '{v}'" for k, v in distribute_dicts.items()]
            )
            id_sql = ",".join([f"'{i}'" for i in ids])
            
            # 更新sql
            sql = f"""
            UPDATE Query
            SET 
                node_no = CASE report_id
                    {case_sql}
                END,
                deal_status = 'ready'
            WHERE report_id IN ({id_sql})
            AND deal_status = 'init'
            """
            c = self.conn.cursor()
            c.execute(sql)
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            return ""



    """
    删除数据后缩小db尺寸
    """
    def auto_vacuum(self):
        self.conn.execute("VACUUM;")
        

    # 查询有多少在排队
    def query_for_ready(self):
        sql = "SELECT count(*) FROM Query WHERE deal_status = 'ready'"
        cursor = self.c.execute(sql)
        for row in cursor:
            return row[0]
        return 0
    # 查询有多少数据在运行
    def query_for_running(self):
        sql = "SELECT count(*) FROM Query WHERE deal_status = 'running'"
        cursor = self.c.execute(sql)
        for row in cursor:
            return row[0]
        return 0

    # 查询有多少数据在排队
    def query_for_ahead(self, report_id):
        try:
            sql = "SELECT report_id FROM Query WHERE deal_status ='ready' order by ready_time"
            cursor = self.c.execute(sql)
            num =0
            for row in cursor:
                reportid = row[0]
                num = num + 1
                if reportid == report_id:
                    break
            return num
        except sqlite3.IntegrityError as e:
            print(str(e))
            return None 

    """
    更新任务的处理状态
    """
    def update_task_status(self,report_id,db_id,status):
        try:
            now = int(time.time())
            sql = "UPDATE Query SET deal_status = ? ,end_time = ? WHERE report_id = ? and db_id = ?"
            report_id = [status,now,report_id,db_id]
            self.c.execute(sql,report_id)
            self.conn.commit()
            return 'OK'
        except sqlite3.IntegrityError as e:
            print(str(e))
            return 'Failed'

    """
    更新任务的处理状态
    """
    def update_task_progress(self,report_id,db_id,progress):
        try:
            now = int(time.time())
            sql = "UPDATE Query SET progress = ? WHERE report_id = ? and db_id = ?"
            report_id = [json.dumps(progress),report_id,db_id]
            self.c.execute(sql,report_id)
            self.conn.commit()
            return 'OK'
        except sqlite3.IntegrityError as e:
            print(str(e))
            return 'Failed'
        

    """
    获得列表的状态
    """
    def get_list_by_status(self, deal_status, page_no=1, page_size=50):
        """
        分页查询 Query 表中符合 deal_status 的记录，返回分页结果
        :param deal_status: 过滤状态，传'all'表示不过滤
        :param page_no: 页码，从1开始
        :param page_size: 每页条数
        :return: {
            'records': 当前页数据列表,
            'total_count': 总记录数,
            'total_page': 总页数,
            'page_no': 当前页码
        }
        """
        try:
            page_no = int(page_no)
            page_size = int(page_size)
            offset = (page_no - 1) * page_size

            # 先计算总记录数
            if deal_status == 'all':
                count_sql = "SELECT COUNT(*) FROM Query"
                self.c.execute(count_sql)
            else:
                count_sql = "SELECT COUNT(*) FROM Query WHERE deal_status = ?"
                self.c.execute(count_sql, (deal_status,))
            total_count = self.c.fetchone()[0]
            total_page = (total_count + page_size - 1) // page_size

            # 查询分页数据
            if deal_status == 'all':
                sql = """
                    SELECT report_id, ready_time, start_time, end_time, param, run_num, deal_status, node_no, capability_id
                    FROM Query
                    LIMIT ? OFFSET ?
                """
                self.c.execute(sql, (page_size, offset))
            else:
                sql = """
                    SELECT report_id, ready_time, start_time, end_time, param, run_num, deal_status, node_no, capability_id
                    FROM Query
                    WHERE deal_status = ?
                    LIMIT ? OFFSET ?
                """
                self.c.execute(sql, (deal_status, page_size, offset))

            rows = self.c.fetchall()

            columns = ['report_id', 'ready_time', 'start_time', 'end_time', 'param', 'run_num', 'deal_status', 'node_no', 'capability_id']
            records = [dict(zip(columns, row)) for row in rows]

            return {
                'records': records,
                'total_count': total_count,
                'total_page': total_page,
                'page_no': page_no
            }

        except sqlite3.IntegrityError as e:
            print(str(e))
            return {
                'records': [],
                'total_count': 0,
                'total_page': 0,
                'page_no': page_no
            }

          
    def update_deal_status_batch(self,deal_status1,deal_status2):
        try:
             if deal_status1 =="failed" and deal_status2 =="ready": #只提供吧failed状态修改成 ready
                now = int(time.time())
                sql = "UPDATE Query SET deal_status = '?' ,ready_time = ? WHERE deal_status = '?' "
                report_id = [deal_status2,now,deal_status1]
                self.c.execute(sql,report_id)
                self.conn.commit()
                ret = {
                    'deal_status_org':deal_status1,
                    'deal_status_mod':deal_status2,
                    'msg':'OK'
                }
                return ret
        except sqlite3.IntegrityError as e:
            print(str(e))
            ret = {
                    'deal_status_org':deal_status1,
                    'deal_status_mod':deal_status2,
                    'msg':'Failed'
            }
            return ret
        
    """
    创建一个节点
    """
    def add_node(self, node_no, deal_type_no, deal_type_version, node_loc):
        """
        插入一个新的节点信息记录。
        如果 node_no 已存在，则不插入，返回 -1。
        否则插入，返回 0。
        """
        try:
            # 检查 node_no 是否已存在
            check_sql = "SELECT 1 FROM node_info WHERE node_no = ? LIMIT 1"
            self.c.execute(check_sql, (node_no,))
            if self.c.fetchone():
                logger.info(f"节点 {node_no} 已存在，不插入。")
                return -1  # 已存在
            node_live_time_last = int(time.time())
            # 插入新节点记录
            insert_sql = """
                INSERT INTO node_info (node_no, deal_type_no, deal_type_version, node_loc, node_live_time_last)
                VALUES (?, ?, ?, ?, ?)
            """
            self.c.execute(insert_sql, (node_no, deal_type_no, deal_type_version, node_loc, node_live_time_last))
            self.conn.commit()
            logger.info(f"成功插入节点：{node_no}")
            return 0  # 插入成功

        except Exception as e:
            logger.error(f"插入节点失败: {str(e)}")
            return -2  # 其他错误

    """
    删除一个节点
    """
    def remove_node(self, node_no):
        """
        删除一个节点记录。
        如果节点不存在则返回 -1，删除成功返回 0。
        """
        try:
            # 检查节点是否存在
            check_sql = "SELECT 1 FROM node_info WHERE node_no = ? LIMIT 1"
            self.c.execute(check_sql, (node_no,))
            if not self.c.fetchone():
                logger.info(f"节点 {node_no} 不存在，无法删除。")
                return -1  # 不存在

            # 执行删除操作
            delete_sql = "DELETE FROM node_info WHERE node_no = ?"
            self.c.execute(delete_sql, (node_no,))
            self.conn.commit()
            logger.info(f"成功删除节点：{node_no}")
            return 0  # 删除成功

        except Exception as e:
            logger.error(f"删除节点失败: {str(e)}")
            return -2  # 其他错误

    def __del__(self):
        self.conn.close()
        
    """
    更新一个节点
    """
    def update_node(self, node_no, deal_type_no, deal_type_version, node_loc):
        """
        插入一个新的节点信息记录。
        如果 node_no 已存在，则不插入，返回 -1。
        否则插入，返回 0。
        """
        # 如果输入的参数不是空, 那么就进行更新
        
        """
        根据传入字段更新节点，只更新不为 None 的字段。
        """

        try:
            fields = {
                "node_no": node_no,
                "deal_type_no": deal_type_no,
                "deal_type_version": deal_type_version,
                "node_loc": node_loc
            }

            # 过滤掉 None 的字段
            update_data = {k: v for k, v in fields.items() if v is not None}

            if not update_data:
                return 0  # 没有要更新的字段
            set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
            values = list(update_data.values())
            values.append(node_no)

            sql = f"UPDATE node_info SET {set_clause} WHERE node_no = ?"
            self.c.execute(sql, values)
            self.conn.commit()

            return 0

        except Exception as e:
            logger.error(f"更新节点失败: {e}")
            return -1

    




if __name__ == '__main__':
    sql = Sql()
    sql.add_query_by_type('666', 'yesskon', 'wrink')
    print(sql.handle_query_by_type(8081, 'wrink'))
    # sql.handle_query('80')
    # sql.add_query('1234')
    # sql.add_query('1235')
    # sql.add_query('1236')
    # sql.add_query('1237')
    
    # print(sql.handle_query(8081))
    # sql.update_ok('55')
    # print(sql.query_for_id('55'))
    # print(sql.query_for_ahead('889'))
