from src.dao.sql import Sql
from src.dao.taskDao import CTaskDao
from src.services.baseService import CBaseService
from src.utils.SysLogger import CSysLogger
import json

logger = CSysLogger('taskService')

class CTaskService(CBaseService):

    def __init__(self):
        self.taskDao = CTaskDao()

    def create_task(self, report_id, capability_id, params, deal_port):
        res_dict = self.init_res()
        insert_code, msg = self.taskDao.create_task(report_id, capability_id, params, deal_port)
        res_dict['code'] = insert_code
        res_dict['msg'] = msg

        return res_dict
    

    def handle_task(self, node_no, dev_mode):

        report_id, process_param, db_id, cap_id = self.taskDao.handle(node_no, dev_mode)
        data = {
            'report_id': report_id,
            'param': process_param,
            'db_id': db_id,
        }
        return data

    @staticmethod
    def create_task_info(report_id, task_type, task_info):
        logger.info('TaskService.create_task_info - report_id: {}, task_type: {}'.format(report_id, task_type))
        sql = Sql()
        add_code, msg = sql.add_task_info(report_id, task_type, task_info)
        if add_code == 0:
            logger.info('TaskService.create_task_info 成功 - report_id: {}'.format(report_id))
        else:
            logger.error('TaskService.create_task_info 失败 - report_id: {}, msg: {}'.format(report_id, msg))
        return add_code, msg

    @staticmethod
    def batch_create_task(report_ids, deal_type_nos, submit_params):
        logger.info('TaskService.batch_create_task - 任务数量: {}'.format(len(report_ids)))
        for report_id, deal_type_no, submit_param in zip(report_ids, deal_type_nos, submit_params):
            sql = Sql()
            sql.add_query_by_type(report_id, deal_type_no, json.dumps(submit_param))
        logger.info('TaskService.batch_create_task 完成 - 任务数量: {}'.format(len(report_ids)))
        return 0, 'request is succ'

    @staticmethod
    def prior_task(report_id):
        logger.info('TaskService.prior_task - report_id: {}'.format(report_id))
        sql = Sql()
        sql.prior_add_query(report_id)
        logger.info('TaskService.prior_task 成功 - report_id: {}'.format(report_id))
        return 0, 'request for {} is succ'.format(report_id)

    @staticmethod
    def remove_task(report_id):
        logger.info('TaskService.remove_task - report_id: {}'.format(report_id))
        sql = Sql()
        sql.remove_task(report_id)
        logger.info('TaskService.remove_task 成功 - report_id: {}'.format(report_id))
        return 0, 'request for {} is succ'.format(report_id)

    @staticmethod
    def remove_all_task():
        logger.info('TaskService.remove_all_task - 删除所有任务')
        sql = Sql()
        sql.remove_all_task()
        logger.info('TaskService.remove_all_task 完成')
        return 0, 'request for all task is succ'

    @staticmethod
    def get_task_list(status, page_no, page_size):
        logger.info('TaskService.get_task_list - status: {}, page_no: {}, page_size: {}'.format(status, page_no, page_size))
        sql = Sql()
        retdata = sql.get_list_by_status(status, page_no, page_size)
        logger.info('TaskService.get_task_list 完成 - 返回数量: {}'.format(len(retdata) if retdata else 0))
        return retdata

    @staticmethod
    def get_task_info(report_id):
        logger.info('TaskService.get_task_info - report_id: {}'.format(report_id))
        sql = Sql()
        status = sql.get_task_info(report_id)
        if status:
            logger.info('TaskService.get_task_info 成功 - report_id: {}'.format(report_id))
        else:
            logger.error('TaskService.get_task_info 失败 - report_id: {}'.format(report_id))
        return status

    @staticmethod
    def kill_task(report_id, db_id):
        logger.info('TaskService.kill_task - report_id: {}, db_id: {}'.format(report_id, db_id))
        sql = Sql()
        nRet = sql.update_task_status(report_id, db_id, 'killed')
        if nRet == 0:
            logger.info('TaskService.kill_task 成功 - report_id: {}, db_id: {}'.format(report_id, db_id))
        else:
            logger.error('TaskService.kill_task 失败 - report_id: {}, db_id: {}'.format(report_id, db_id))
        return nRet