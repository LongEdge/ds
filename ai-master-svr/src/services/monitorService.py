from src.dao.sql import Sql
from src.utils.SysLogger import CSysLogger
import socket
import time

logger = CSysLogger('monitorService')


class CMonitorService:
    @staticmethod
    def get_master_live(master_ip, master_no):
        try:
            master_no = int(master_no)
            timeout = 5
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            conn_time = time.time()
            sock.connect((master_ip, master_no))
            delay_time = (time.time() - conn_time) * 1000
            return 0, 'connet to {}:{} is succ'.format(master_ip, master_no), int(delay_time)
        except Exception as e:
            return -1, 'connet to {}:{} is failed, e: {}'.format(master_ip, master_no, e), -1

    @staticmethod
    def get_master_info():
        sql = Sql()
        master_info = sql.get_master_info()
        return master_info

    @staticmethod
    def get_node_info_by_master(page_no, page_size):
        sql = Sql()
        data = sql.get_node_info_by_master(page_no, page_size)
        return data