import sqlite3
import time
from src.dao.db import CDB
from src.utils.SysLogger import CSysLogger
logger = CSysLogger('taskDao')


class CTaskDao:
    """
    创建一条任务
    """
    def create_task(self, report_id: str, capability_id: str, params: dict, deal_port: str):
        conn = CDB.get_conn()
        c = conn.cursor()
        try:
            sql = "SELECT db_id, deal_status, start_time, end_time FROM Query WHERE report_id = ? and capability_id = ?"
            param_insert = [report_id, capability_id]
            now = int(time.time())
            cursor = c.execute(sql,param_insert)
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


            if nUpdateId == -1 : #表示需要插入新的数据
                sql = "SELECT db_id FROM Query order by db_id desc limit 1"
                num = 1
                cursor = c.execute(sql)
                for row in cursor:
                    num = row[0] + 1
                    break
                param_inert = [num, deal_port, capability_id, report_id, now, params]
                sql = "INSERT into Query VALUES(?,?,?,?,'ready',?,0,0,?,0,0,'{}','{}', '[-1, -1]')"#末尾两位：默认优先级1  run_num= 0
                logger.info(sql)
                c.execute(sql, param_inert)
                conn.commit()
            elif nUpdateId > -1 : # 更新数据
                param_update = [now,nUpdateId]
                sql = "UPDATE Query SET deal_status ='ready',node_no = 0 , ready_time = ?, start_time =0, end_time = 0 WHERE db_id = ?"
                c.execute(sql, param_update)
                conn.commit()
            return 0, '添加任务成功'
        except sqlite3.IntegrityError as e:
            print(str(e))
            return -1, '添加任务异常, 请联系管理员 - 错误: {}'.format(e)
        finally:
            if conn: conn.close()


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
    def handle(self, node_no: str, dev_mode: str):
        """
        核心任务轮询函数
        :param node_no: 节点编号
        :param dev_mode: 开发模式 ('debug' 或 'release')
        :return: (report_id, params, db_id, capability) 或 (None, None, None, None)
        """
        now = int(time.time())
        # 8分钟前：用于判定任务是否卡死（running 状态太久）
        starttime = now - 480 
        # 1分钟前：用于判定失败任务的重试间隔
        endtime = now - 60

        conn = CDB.get_conn()
        c = conn.cursor()

        try:
            # -------------------------------------------------
            # 1. 查找当前节点具备的所有能力 (capability_id)
            # -------------------------------------------------
            cap_sql = "SELECT capability_id FROM ds_node_capability WHERE node_no = ? AND node_bind_status = 1"
            c.execute(cap_sql, [node_no])
            cap_rows = c.fetchall()
            
            if not cap_rows:
                logger.debug(f"节点 {node_no} 未绑定任何能力，暂无任务。")
                return None, None, None, None
            
            # 将查出的能力转为列表，如 ['cp1', 'cp2']
            capabilities = [row[0] for row in cap_rows]
            # 构造 SQL 的 IN 子句占位符 (?, ?)
            placeholders = ', '.join(['?'] * len(capabilities))

            # -------------------------------------------------
            # 2. 查询 Query 表，寻找最匹配的任务
            # -------------------------------------------------
            # 排序逻辑：priority ASC (优先级高者先), ready_time ASC (早提交者先)
            # 这样即便你有 cp1, cp2, cp3，Query 表里谁最急就先出谁
            
            if "debug" == dev_mode:
                # Debug 模式：只关心明确指派给自己的任务
                query_sql = f"""
                    SELECT report_id, param, db_id, run_num, capability_id
                    FROM Query
                    WHERE node_no = ?
                    AND deal_status = 'ready'
                    ORDER BY priority ASC, ready_time ASC LIMIT 1
                """
                params = [node_no]
            else:
                # Release 模式：抢占逻辑
                # 优先级：1. 之前分给我但卡死/失败的任务  2. 没人要的公共任务
                query_sql = f"""
                    SELECT report_id, param, db_id, run_num, capability_id
                    FROM Query
                    WHERE capability_id IN ({placeholders})
                    AND (
                        -- 场景1：已经指派给我，但由于各种原因需要重做
                        (node_no = ? AND (
                            deal_status = 'ready' 
                            OR (deal_status = 'running' AND start_time < ?)
                            OR (deal_status = 'failed' AND run_num < 4 AND end_time < ?)
                        ))
                        OR 
                        -- 场景2：公共任务（无人认领）
                        ((node_no IS NULL OR node_no = '' OR node_no = '-1') AND deal_status = 'ready')
                    )
                    ORDER BY priority ASC, ready_time ASC LIMIT 1
                """
                # 参数填充
                params = capabilities + [node_no, starttime, endtime]

            c.execute(query_sql, params)
            row = c.fetchone()

            if not row:
                return None, None, None, None

            report_id, process_param, db_id, run_num, cap_id = row

            # -------------------------------------------------
            # 3. 核心：原子化更新 (抢任务锁)
            # -------------------------------------------------
            # 即使 SELECT 到了，更新时也要再次确认状态，防止被其他 node 抢走
            update_sql = """
                UPDATE Query
                SET node_no = ?, 
                    deal_status = 'running', 
                    start_time = ?, 
                    run_num = ?
                WHERE db_id = ? 
                AND (deal_status = 'ready' OR node_no = ? OR (deal_status = 'running' AND start_time < ?))
            """
            new_run_num = (run_num or 0) + 1
            c.execute(update_sql, [node_no, now, new_run_num, db_id, node_no, starttime])
            conn.commit()

            # 只有当数据库真正影响了行数，才算抢占成功
            if c.rowcount > 0:
                logger.info(f"节点 {node_no} - 成功领用任务 -{db_id}- (能力id: {cap_id})")
                return report_id, process_param, db_id, cap_id
            else:
                logger.warning(f"任务 {db_id} 刚刚被其他节点抢走。")
                return None, None, None, None

        except Exception as e:
            if conn: conn.rollback()
            logger.error(f"Handle 逻辑异常: {str(e)}")
            return None, None, None, None
        finally:
            if conn: conn.close()