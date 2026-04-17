import sqlite3
from src.dao.db import CDB
from src.utils.SysLogger import CSysLogger
logger = CSysLogger('nodeDao')


class CNodeDao:
    """
    建立节点与能力的绑定关系（插入记录）
    """
    def bind_node_capability(self, capability_id, node_no):
        conn = CDB.get_conn()
        c = conn.cursor()
        try:

            # 1. 第一步：查询当前记录的状态
            check_sql = "SELECT node_bind_status FROM ds_node_capability WHERE node_no = ? AND capability_id = ?"
            c.execute(check_sql, (node_no, capability_id))
            row = c.fetchone()

            # 情况 A：记录不存在
            if row is None:
                logger.warning(f"绑定失败：未找到 node_no={node_no}, cap_id={capability_id} 的记录")
                return -2, "绑定失败，该节点能力配置记录不存在"

            # 情况 B：记录存在，检查是否已经是绑定状态 (假设 1 为已绑定)
            current_status = row[0]
            if current_status == 1:
                logger.info(f"节点 {node_no} 已经是绑定状态，无需重复操作")
                return 0, "该能力已处于绑定状态"

            # 2. 第二步：执行更新
            update_sql = "UPDATE ds_node_capability SET node_bind_status = 1 WHERE node_no = ? AND capability_id = ?"
            c.execute(update_sql, (node_no, capability_id))
            conn.commit()
            
            return 0, "绑定成功"

        except Exception as e:
            if conn: conn.rollback() # 出错回滚
            logger.error(f"绑定操作异常: {str(e)}")
            return -1, f"系统异常: {str(e)}"
        finally:
            if conn: conn.close()
        

    """
    注册某个节点到对应的能力下
    """
    def register_node_capability(self, capability_id, node_no):
        try:
            conn = CDB.get_conn()
            c = conn.cursor()
            sql = """
                INSERT INTO ds_node_capability
                (capability_id, node_no)
                VALUES (?, ?)
            """
            params = [capability_id, node_no]

            c.execute(sql, params)
            conn.commit()
            conn.close()
            
            return 0, 'succ'  # 成功

        except sqlite3.IntegrityError as e:
            logger.error(e)
            return -1, '节点已存在'

    """
    查询此能力下的所有节点
    """
    def query_nodes_by_capability(self, capability_id, page_no, page_size):
        try:
            conn = CDB.get_conn()
            c = conn.cursor()

            page_no = int(page_no)
            page_size = int(page_size)
            offset = (page_no - 1) * page_size

            # 总数
            count_sql = """
                SELECT COUNT(*) FROM ds_node_capability
                WHERE capability_id = ?
            """

            # 分页数据
            sql = """
                SELECT node_cb_id, node_no, node_bind_status
                FROM ds_node_capability
                WHERE capability_id = ?
                ORDER BY node_cb_id DESC
                LIMIT ? OFFSET ?
            """

            # count
            c.execute(count_sql, (capability_id,))
            total_count = c.fetchone()[0]
            total_page = (total_count + page_size - 1) // page_size

            # data
            logger.info(f"查询节点 SQL：{sql} | capability_id={capability_id}, page_no={page_no}")
            c.execute(sql, (capability_id, page_size, offset))
            records = c.fetchall()

            conn.close()

            columns = ["node_cb_id", "node_no", "node_bind_status"]
            records = [dict(zip(columns, row)) for row in records]

            return {
                "records": records,
                "total_count": total_count,
                "total_page": total_page,
                "page_no": page_no
            }

        except Exception as e:
            logger.error(f"查询节点失败: {str(e)}")
            return {
                "records": [],
                "total_count": 0,
                "total_page": 0,
                "page_no": page_no
            }


    """
    删除节点绑定的能力
    """
    def unbind_node_capability(self, node_no, capability_id):
        try:
            conn = CDB.get_conn()
            c = conn.cursor()

            sql = """
                DELETE FROM ds_node_capability
                WHERE node_no = ?
                AND capability_id = ?
            """

            logger.info(f"删除节点能力 SQL：{sql} | node_no={node_no}, capability_id={capability_id}")

            c.execute(sql, (node_no, capability_id))
            conn.commit()
            conn.close()

            return 0

        except Exception as e:
            logger.error(f"删除节点能力失败: {str(e)}")
            return -1
        
    """
    节点是否存在
    """
    def exists_node(self, node_no):
        try:
            conn = CDB.get_conn()
            c = conn.cursor()

            sql = "SELECT 1 FROM node_info WHERE node_no = ? LIMIT 1"
            c.execute(sql, (node_no,))
            row = c.fetchone()

            conn.close()
            print("row: ", row[0])
            if row is None:
                return -1
            return 0

        except Exception as e:
            logger.error(f"{node_no} nodeDao.exists_node error! Error: {str(e)}")
            return -1
        

    """
    能力是否存在
    """
    def exists_node_capabiltiy(self, capability_id):
        try:
            conn = CDB.get_conn()
            c = conn.cursor()

            sql = "SELECT 1 FROM ds_gateway_capability WHERE capability_id = ? LIMIT 1"
            c.execute(sql, (capability_id,))
            row = c.fetchone()

            conn.close()
            if row is None:
                return -1
            return 0

        except Exception as e:
            logger.error(f"{capability_id} nodeDao.exists_node_capabiltiy error! Error: {str(e)}")
            return -1
        
    """
    能力发布状态更新, -1=待发布, 0=未发布, 1=已发布
    """
    def update_capability_release_status(self, capability_id, capability_release_status):
        try:
            # 可选：避免空更新
            if capability_release_status is None or capability_release_status == "":
                return 0

            conn = CDB.get_conn()
            c = conn.cursor()

            sql = """
                UPDATE ds_gateway_capability
                SET capability_release_status = ?
                WHERE capability_id = ?
            """

            logger.info(f"更新能力状态 SQL：{sql} | capability_id={capability_id}, capability_release_status={capability_release_status}")

            c.execute(sql, (capability_id, capability_release_status))
            conn.commit()
            conn.close()

            return 0

        except Exception as e:
            logger.error(f"更新节点状态失败: {str(e)}")
            return -1


    """
    更新节点(仅描述)
    """
    def update_node_capability(self, node_cb_id, node_no, node_bind_status):
        """
        根据 node_cb_id 更新 ds_node_capability 表中指定字段
        只有非 None 的字段才会更新
        """
        try:
            # 如果没有字段需要更新，直接返回
            if all(v is None for v in [node_no, node_bind_status]):
                return 0

            conn = CDB.get_conn()
            c = conn.cursor()

            # 动态拼接需要更新的字段
            update_fields = []
            params = []

            if node_no is not None:
                update_fields.append("node_no = ?")
                params.append(node_no)
            if node_bind_status is not None:
                update_fields.append("node_bind_status = ?")
                params.append(node_bind_status)

            sql = f"""
                UPDATE ds_node_capability
                SET {', '.join(update_fields)}
                WHERE node_cb_id = ?
            """
            params.append(node_cb_id)

            logger.info(f"更新节点能力 SQL: {sql} | params={params}")

            c.execute(sql, params)
            conn.commit()

            if c.rowcount == 0:
                logger.warning(f"未匹配到 node_cb_id={node_cb_id} 的记录")
                return 1  # 没有更新到数据

            return 0  # 成功

        except Exception as e:
            logger.error(f"更新节点能力失败: {str(e)}")
            return -1

        finally:
            conn.close()