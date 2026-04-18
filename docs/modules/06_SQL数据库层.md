# 06 - SQL 数据库层 (sql.py)

## 📋 概述

| 属性 | 值 |
|-----|-----|
| 文件 | `ai-master-svr/src/dao/sql.py` |
| 类 | `Sql` |
| 数据库 | SQLite (`test.db`) |
| 表 | Query, task_init, task_log_info, node_info |

---

## 🗄️ 数据库表结构

### Query 表（主任务表）
```sql
CREATE TABLE Query (
    node_no integer,           -- 执行节点编号 (NULL=未指派)
    report_id VARCHAR(255),    -- 任务唯一ID (UNIQUE)
    db_id integer,             -- 自增主键
    deal_type_no VARCHAR(?),   -- 任务/模型类型
    deal_status VARCHAR(25),   -- 状态: init/ready/running/ok/failed/killed
    ready_time integer,        -- 就绪时间戳
    start_time integer,        -- 开始执行时间戳
    end_time integer,          -- 结束时间戳
    param TEXT,                -- 任务参数 (JSON)
    priority INTEGER,          -- 优先级 (默认1, -1=最高)
    run_num INTEGER,            -- 运行次数 (超过4次不再重试)
    candidate_nodes TEXT,      -- 候选节点列表 (JSON)
    progress TEXT              -- 进度信息 (JSON)
)
```

### task_init 表（任务初始化信息）
```sql
CREATE TABLE task_init (
    db_id,
    report_id,
    task_type,
    task_info TEXT,           -- JSON 字符串
    is_appointment INTEGER     -- 0=未指派, 1=指派成功, 2=指派失败
)
```

### task_log_info 表（任务进度日志）
```sql
CREATE TABLE task_log_info (
    id INTEGER PRIMARY KEY,   -- 自增ID
    node_no integer,
    report_id VARCHAR(255),
    deal_time integer,        -- 处理时间戳
    task_info TEXT            -- JSON 字符串
)
```

---

## 🔍 核心方法详解

### `add_query_by_type()` — 添加/创建任务
**防重复逻辑**：
```
1. 查询是否已存在相同 report_id + deal_type_no 的任务
2. 判断逻辑：
   ├─ 如果状态是 ready/running（且开始时间<8分钟）→ 拒绝重复
   ├─ 如果 running 超过8分钟 → 允许重新计算
   ├─ 如果 ok 完成（在2分钟内）→ 拒绝（防止重复计算）
   └─ 如果 failed（超过2分钟）→ 允许重新计算
```

### `handle()` — 节点领取任务（核心）
**任务选择优先级**：
```
1. 【Debug模式】节点仅能领取绑定到自己的任务
   └ SELECT ... WHERE node_no = ? AND deal_status = 'ready'

2. 【发布模式】节点可领取公共任务
   2.1 优先：该节点之前失败/超时的任务
       └ WHERE node_no = ? AND (deal_status = 'running' AND start_time < 8分钟前)
                              OR (deal_status = 'failed' AND run_num < 4)
   
   2.2 其次：未指派的公共就绪任务
       └ WHERE (node_no IS NULL OR node_no = '' OR node_no = '-1') AND deal_status = 'ready'
```

### `auto_update_node_live_status_by_master()` — 更新节点存活状态
```sql
UPDATE node_info
SET node_live_status = 1  -- 1=离线
WHERE last_heartbeat < (当前时间 - 阈值)
```

---

## 📊 分页查询

```python
def query_task_log(self, node_no, report_id, page_no=1, page_size=50):
    # 计算偏移量
    offset = (page_no - 1) * page_size
    
    # 自动将 task_info JSON 反序列化
    for row in records:
        task_info = json.loads(row["task_info"])
        task_info["deal_time"] = row["deal_time"]  # 移入内部
```

---

## 🔄 批量操作优化

### `add_task_logs_batch()` — 高效批量插入进度
```python
# 使用 INSERT ... VALUES (...), (...), (...)
values_str = ", ".join([
    f"('{deal_type_no}', '{report_id}', {deal_time}, '{task_info_json}')"
    for task_info in task_info_list
])
sql = f"INSERT INTO task_log_info (...) VALUES {values_str}"
```
**性能提升**：N 条记录只需 1 次数据库写入

---

## ⚠️ 设计与性能问题

| 问题 | 影响 | 建议 |
|-----|------|------|
| SQLite 并发写锁 | 多节点同时上报进度会锁竞争 | 考虑换 PostgreSQL/MySQL |
| 无连接池 | 每次操作新建连接 | 引入 DBUtils |
| 候选节点存储为 JSON 字符串 | 查询效率低 | 拆分为关联表 |
| 进度日志无限增长 | 表数据膨胀 | 添加定期清理策略 |
| 无事务管理 | 部分操作失败不回滚 | 添加事务控制 |

---

## ⏱️ 时间常量

```python
NODE_SAVE_DAYS = 7 * 24 * 3600   # 离线节点默认保留7天
# 任务超时：8 分钟
# 防重复提交：2 分钟
# 最大重试次数：4 次
```
