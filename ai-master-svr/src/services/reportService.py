from src.dao.sql import Sql
from src.utils.SysLogger import CSysLogger

logger = CSysLogger('reportService')


class CReportService:
    @staticmethod
    def update_task_status(report_id, db_id, status):
        logger.info('CReportService.update_task_status - report_id: {}, db_id: {}, status: {}'.format(report_id, db_id, status))
        sql = Sql()
        nRet = sql.update_task_status(report_id, db_id, status)

        return nRet

    @staticmethod
    def update_task_progress(report_id, db_id, progress):
        sql = Sql()
        nRet = sql.update_task_progress(report_id, db_id, progress)
        return nRet

    @staticmethod
    def report_node_live_status(node_no, node_op_status):
        sql = Sql()
        node_live_status = sql.report_node_live_status(node_no, node_op_status)
        return node_live_status

    @staticmethod
    def report_node_processing(report_id, node_no, task_info):
        sql = Sql()
        sql.add_task_log(report_id, node_no, task_info)
        return 0, 'report processing for {} is succ'.format(report_id)

    @staticmethod
    def report_node_processing_batch(report_id, node_no, task_info_list):
        sql = Sql()
        sql.add_task_logs_batch(report_id, node_no, task_info_list)
        return 0, 'report processing for {} is succ'.format(report_id)

    @staticmethod
    def query_task_processing(node_no, report_id, page_no, page_size):
        sql = Sql()
        data = sql.query_task_log(node_no, report_id, page_no, page_size)
        return data