# 03 - 任务 API 层 (taskApi.py)

## 📋 概述

| 属性 | 值 |
|-----|-----|
| 文件 | `ai-master-svr/src/api/taskApi.py` |
| Blueprint | `taskBp` |
| 前缀 | `/ai-master-svr/` |
| Service | `CTaskService` |

---

## 🌐 API 路由清单

### 1. `POST /ai-master-svr/create-task/`
**功能**：Master 创建新任务

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| report_id | string | ✅ | 任务唯一标识 |
| capability_id | string | ✅ | 任务类型（模型类型） |
| param | string | ✅ | 任务参数（JSON 字符串，如数据URL） |
| deal_port | string | ❌ | 指定处理节点端口（本地调试用） |

**返回**：
```json
{"status": 0, "msg": "添加任务成功"}
```

**业务逻辑** (`CTaskService.create_task`)：
```
1. taskDao.create_task(report_id, capability_id, params, deal_port)
2. 底层调用 sql.add_query_by_type()
   - 检查是否重复提交（2分钟内完成的任务不能重复）
   - 8分钟内 running 状态的任务不能重新插入
   - running 超过8分钟可重新计算
   - failed 超过2分钟可重新计算
```

---

### 2. `POST /ai-master-svr/batch-create-task/`
**功能**：批量创建任务

| 参数 | 类型 | 说明 |
|-----|------|------|
| report_ids | JSON Array | 任务ID列表 |
| deal_type_nos | JSON Array | 任务类型列表 |
| params | JSON Array | 参数列表（与上面一一对应） |

**示例请求**：
```json
{
  "report_ids": ["r001", "r002", "r003"],
  "deal_type_nos": ["face_landmark", "slim_wrinkle", "bold_wrinkle"],
  "params": [{"url": "xxx"}, {"url": "yyy"}, {"url": "zzz"}]
}
```

---

### 3. `POST /ai-master-svr/handle/`
**功能**：Node 节点向 Master **请求任务**（Node 主动拉取）

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| node_no | string | ✅ | 节点唯一ID |
| dev_mode | string | ❌ | `"debug"` = 仅处理绑定到该节点的任务；空 = 处理公共任务 |

**返回**：
```json
{
  "report_id": "xxx",
  "param": "{...}",
  "db_id": 123
}
```

**任务选择策略** (`sql.handle()`)：
```
1. 优先：绑定到当前节点的任务 (node_no = 请求节点)
2. 其次：该节点之前失败/超时未完成的任务
3. 最后：任意公共就绪任务
```

---

### 4. `POST /ai-master-svr/prior-task/`
**功能**：提升任务优先级为最高（priority = -1）

```json
// 请求
{"report_id": "xxx"}

// 响应
{"status": 0, "msg": "request for xxx is succ"}
```

---

### 5. `POST /ai-master-svr/remove-task/`
**功能**：删除指定任务

```json
// 请求
{"report_id": "xxx"}

// 响应
{"status": 0, "msg": "删除任务成功"}
```

---

### 6. `POST /ai-master-svr/remove-all-task/`
**功能**：清空所有任务（危险操作！）

> ⚠️ 无任何确认机制和权限校验

---

### 7. `POST /ai-master-svr/getlist/`
**功能**：分页获取任务列表

| 参数 | 类型 | 说明 |
|-----|------|------|
| dealStatus | string | 筛选状态：`ready`/`running`/`ok`/`failed`/全部 |
| page_no | int | 页码（从1开始） |
| page_size | int | 每页条数 |

---

### 8. `POST /ai-master-svr/get-task-info/`
**功能**：查询单个任务的完整信息

```json
// 请求
{"report_id": "xxx"}

// 响应
{
  "data": {
    "db_id": 1,
    "report_id": "xxx",
    "deal_status": "running",
    "node_no": 123,
    ...
  }
}
```

---

### 9. `POST /ai-master-svr/kill-task/`
**功能**：强制终止正在运行的任务

| 参数 | 说明 |
|-----|------|
| node_no | 节点ID |
| report_id | 任务ID |
| db_id | 数据库ID |

**实现**：调用 `sql.update_task_status(report_id, db_id, 'killed')`

---

## 🔐 权限控制现状

| API | 认证 | 风险 |
|-----|-----|------|
| create-task | ❌ 无 | 任何人都可创建任务 |
| batch-create-task | ❌ 无 | 批量创建无限制 |
| handle | ❌ 无 | 节点注册无验证 |
| kill-task | ❌ 无 | 可终止他人任务 |
| remove-all-task | ❌ 无 | **极度危险** |

> ⚠️ 生产环境必须添加 API Key 认证或 Token 验证

---

## 🔄 Service 层调用链

```
taskApi.py (Blueprint)
    ↓
CTaskService (taskService.py)
    ↓
CTaskDao / Sql (dao/sql.py)
    ↓
SQLite (test.db)
```

---

## 📊 任务状态机

```
                    ┌──────────────────────────────────────┐
                    │                                      │
                    ▼                                      │
init ──→ ready ──→ running ──→ ok                         │
                    │              │                        │
                    │              ↓                        │
                    │           failed                      │
                    │              │                        │
                    │    (run_num < 4 可重试)               │
                    │              │                        │
                    └──────────────┘                        │
                          ▲                                 │
                          │                                 │
                      (超过4次)                             │
                          │                                 │
                       killed ◀────────────────────────────┘
```

**状态说明**：
- `init`：初始化
- `ready`：就绪，等待节点领取
- `running`：节点执行中
- `ok`：成功完成
- `failed`：执行失败（可重试，最多4次）
- `killed`：被强制终止

---

## ⏱️ 时间约束（防重复提交）

| 场景 | 限制 |
|-----|------|
| ready/running 状态 | 不能重复创建 |
| running 超过 8 分钟 | 可重新计算 |
| ok 完成 2 分钟内 | 不能重复提交 |
| failed 超过 2 分钟 | 可重新计算 |
| failed 重试次数 | 最多 4 次 (`run_num < 4`) |
