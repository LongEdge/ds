import sqlite3
import time
from src.dao.db import CDB
from src.utils.SysLogger import CSysLogger
logger = CSysLogger('gatewayDao')

class CGatewayDao:
    """
    注册网关能力
    """
    def register_gateway_capability(
        self, 
        capability_id, 
        capability_name, 
        capability_version, 
        capability_desc
    ):
        try:
            conn = CDB.get_conn()
            c = conn.cursor()
            sql = """
                INSERT INTO ds_gateway_capability
                (capability_id, capability_name, capability_version, capability_release_status, capability_desc)
                VALUES (?, ?, ?, -1, ?)
            """
            params = [capability_id, capability_name, capability_version, capability_desc]

            c.execute(sql, params)
            conn.commit()
            conn.close()
            
            return 0  # 成功

        except sqlite3.IntegrityError as e:
            logger.error(e)
            return -1
        
    """
    查询网关能力
    """
    def query_gateway_capability(self, page_size, page_no):
        try:
            conn = CDB.get_conn()
            c = conn.cursor()

            page_no = int(page_no)
            page_size = int(page_size)
            offset = (page_no - 1) * page_size

            # 统计总数
            count_sql = """
                SELECT COUNT(*) FROM ds_gateway_capability
            """

            # 分页查询
            sql = """
                SELECT capability_id, capability_name, capability_version, capability_release_status, capability_release_time, capability_desc
                FROM ds_gateway_capability
                ORDER BY capability_release_time DESC
                LIMIT ? OFFSET ?
            """

            # 查询总数
            c.execute(count_sql)
            total_count = c.fetchone()[0]
            total_page = (total_count + page_size - 1) // page_size

            # 查询分页数据
            logger.info(f"分页查询 SQL：{sql} | page_no={page_no}")
            c.execute(sql, (page_size, offset))
            records = c.fetchall()
            conn.close()

            columns = ["capability_id", "capability_name", "capability_version", "capability_release_status", "capability_release_time", "capability_desc"]
            new_records = []
            for row in records:
                item = dict(zip(columns, row))
                new_records.append(item)

            return {
                'records': new_records,
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
    删除网关能力
    """
    def delete_gateway_capability(self, capability_id):
        try:
            conn = CDB.get_conn()
            c = conn.cursor()

            sql = """
                DELETE FROM ds_gateway_capability
                WHERE capability_id = ?
            """

            logger.info(f"删除网关能力 SQL：{sql} | capability_id={capability_id}")
            c.execute(sql, (capability_id,))
            conn.commit()
            conn.close()

            return 0

        except Exception as e:
            logger.error(f"删除网关能力失败: {str(e)}")
            return -1

    """
    更新网关(仅描述)
    """
    def update_gateway_capability(self, capability_id, capability_desc):
        try:
            if capability_desc is None or capability_desc == "":
                return 0
        
            conn = CDB.get_conn()
            c = conn.cursor()
            sql = """
                UPDATE ds_gateway_capability
                SET capability_desc = ?
                WHERE capability_id = ?
            """

            logger.info(f"更新能力描述 SQL：{sql} | capability_id={capability_id}")

            c.execute(sql, (capability_desc, capability_id))
            conn.commit()
            conn.close()

            return 0

        except Exception as e:
            logger.error(f"更新能力描述失败: {str(e)}")
            return -1
        

    """
    更新网关状态
    """
    def update_gateway_capability_status(self, capability_id, capability_status):
        try:
            if capability_status is None or capability_status == "":
                return 0
        
            conn = CDB.get_conn()
            c = conn.cursor()
            sql = """
                UPDATE ds_gateway_capability
                SET capability_release_status = ?
                WHERE capability_id = ?
            """

            logger.info(f"更新能力描述 SQL：{sql} | capability_id={capability_id}")

            c.execute(sql, (capability_status, capability_id))
            conn.commit()
            conn.close()

            return 0

        except Exception as e:
            logger.error(f"更新能力描述失败: {str(e)}")
            return -1