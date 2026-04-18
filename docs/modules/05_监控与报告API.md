# 05 - 监控与报告 API

## 📋 概述

包含两个 Blueprint：
- `monitorBp` → `ai-master-svr/src/api/monitorApi.py`
- `reportBp` → `ai-master-svr/src/api/reportApi.py`

---

## 📊 Monitor API (monitorApi.py)

### 核心功能：节点存活监控

| API | 方法 | 功能 |
|-----|------|------|
| `/ai-master-svr/report-node-live-status/` | POST | 节点上报心跳 |
| `/ai-master-svr/report-node-processing-batch/` | POST | 节点批量上报任务进度 |
| `/ai-master-svr/update-task-entire-progress/` | POST | 更新任务整体进度 |

---

### 1. `POST /ai-master-svr/report-node-live-status/`
**功能**：节点心跳上报（**由 Node 节点定时调用**）

| 参数 | 说明 |
|-----|------|
| node_no | 节点ID |
| node_op_status | 节点状态：`1`=繁忙, `2`=空闲 |

**调用频率**：Node 端每 **5 秒** 调用一次

```python
# Node 端调用 (ProcessFramework.py)
requests.post(url, data={'node_no': node_id, 'node_op_status': self.live_status}, timeout=4)
```

---

### 2. `POST /ai-master-svr/report-node-processing-batch/`
**功能**：批量上报任务进度

```json
{
  "report_id": "xxx",
  "node_no": "node_001",
  "task_info": [
    {"deal_percent": 10, "deal_time": 1234567890, "deal_msg": "加载模型"},
    {"deal_percent": 50, "deal_time": 1234567891, "deal_msg": "处理中"}
  ]
}
```

**特点**：
- 高频调用（**每秒**上报一次）
- 进度存储在 `task_log_info` 表
- 使用**批量插入**优化性能

---

### 3. `POST /ai-master-svr/update-task-entire-progress/`
**功能**：更新任务整体进度（用于训练等长任务）

---

## 📝 Report API (reportApi.py)

### 核心功能：任务报告生成与查询

| API | 方法 | 功能 |
|-----|------|------|
| `/ai-master-svr/report-node-live-status/` | POST | （同 Monitor，可能重复定义） |
| `/get-report/` | POST | 获取任务报告 |
| `/get-progress/` | POST | 获取任务进度 |

---

### 进度查询分页
```python
def query_task_log(self, node_no, report_id, page_no=1, page_size=50):
    """
    分页查询任务日志
    - 按 deal_time 倒序
    - 自动将 task_info JSON 字符串反序列化为字典
    - 把 deal_time 移入 task_info 内部
    """
```

---

## 🔄 Node → Master 上报链路

```
Node (ProcessFramework)
    │
    ├─ node_heart_beat() [每 5 秒]
    │   └─ POST /report-node-live-status/
    │       └─ 更新节点 last_heartbeat 时间
    │
    ├─ node_task_processing() [每 1 秒]
    │   └─ POST /report-node-processing-batch/
    │       └─ 批量写入 task_log_info
    │
    └─ node_task_entire_processing() [每 1 秒]
        └─ POST /update-task-entire-progress/
            └─ 更新任务整体进度
```

---

## ⚠️ 监控问题

| 问题 | 影响 |
|-----|------|
| Master 无法主动探测 Node 存活 | 依赖 Node 心跳上报，Node 崩溃可能无法及时发现 |
| 心跳超时阈值未明确 | 不确定多久没心跳算作离线 |
| 进度上报频率高 | 高频写入可能成为性能瓶颈 |
| 无告警机制 | 任务失败后无人知晓 |
