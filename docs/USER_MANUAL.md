# DS 分布式 AI 推理系统 - 用户手册

> 版本：1.0.0 | 仓库：LongEdge/ds

---

## 📋 目录

1. [系统简介](#1-系统简介)
2. [快速开始](#2-快速开始)
3. [任务管理](#3-任务管理)
4. [节点管理](#4-节点管理)
5. [存储管理](#5-存储管理)
6. [监控与日志](#6-监控与日志)
7. [故障排除](#7-故障排除)

---

## 1. 系统简介

DS 是一个**分布式 AI 视觉推理平台**，用户通过 HTTP API 与系统交互，完成以下操作：

| 功能 | 说明 |
|-----|------|
| 创建任务 | 提交图像/视频处理任务 |
| 管理节点 | 注册/注销计算节点 |
| 查询状态 | 查看任务进度和结果 |
| 终止任务 | 强制停止运行中的任务 |

### 1.1 核心概念

| 概念 | 说明 |
|-----|------|
| **Report ID** | 任务的唯一标识符，由调用方生成 |
| **Capability ID** | 任务类型，如 `face_landmark`、`slim_wrinkle` |
| **Node** | 执行任务的计算节点 |
| **Status** | 任务状态：`init` → `ready` → `running` → `ok`/`failed`/`killed` |

### 1.2 系统限制

| 限制项 | 值 | 说明 |
|-------|-----|------|
| 单任务最大执行时间 | 无明确上限 | 建议任务在 30 分钟内完成 |
| 任务失败重试次数 | 4 次 | 超过后不再重试 |
| 重复提交间隔 | 2 分钟 | 刚完成/失败的任务 2 分钟内不能重复提交 |
| 运行中任务重复提交 | 不允许 | 8 分钟内的 running 任务不可重复提交 |

---

## 2. 快速开始

### 2.1 快速创建任务

**Step 1：确认 Master 地址**

```bash
MASTER_URL="http://localhost:8080"
```

**Step 2：创建单个任务**

```bash
curl -X POST "${MASTER_URL}/ai-master-svr/create-task/" \
  -F "report_id=my_task_001" \
  -F "capability_id=face_landmark" \
  -F "param={\"image_url\":\"http://example.com/face.jpg\"}"
```

**预期响应**：
```json
{"status": 0, "msg": "添加任务成功"}
```

**Step 3：查询任务状态**

```bash
curl -X POST "${MASTER_URL}/ai-master-svr/get-task-info/" \
  -F "report_id=my_task_001"
```

**预期响应**：
```json
{
  "status": 0,
  "msg": "succ",
  "data": {
    "report_id": "my_task_001",
    "deal_status": "ready",
    "db_id": 1
  }
}
```

**Step 4：等待节点领取并执行（可通过定时查询观察状态变化）**

```bash
# 每 5 秒查询一次
watch -n 5 "curl -s -X POST '${MASTER_URL}/ai-master-svr/get-task-info/' -F 'report_id=my_task_001'"
```

---

### 2.2 批量创建任务

```bash
curl -X POST "${MASTER_URL}/ai-master-svr/batch-create-task/" \
  -H "Content-Type: application/json" \
  -d '{
    "report_ids": ["task_001", "task_002", "task_003"],
    "deal_type_nos": ["face_landmark", "slim_wrinkle", "bold_wrinkle"],
    "params": [
      {"url": "http://example.com/img1.jpg"},
      {"url": "http://example.com/img2.jpg"},
      {"url": "http://example.com/img3.jpg"}
    ]
  }'
```

---

### 2.3 提升任务优先级

紧急任务可以提升到最高优先级：

```bash
curl -X POST "${MASTER_URL}/ai-master-svr/prior-task/" \
  -F "report_id=my_task_001"
```

---

## 3. 任务管理

### 3.1 任务生命周期

```
init ──→ ready ──→ running ──→ ok
                  │              │
                  │              ↓
                  │           failed (可重试 4 次)
                  │              │
                  └──────────────┘
                  (run_num < 4)

任意时刻 ──→ killed (强制终止)
```

### 3.2 获取任务列表

```bash
# 获取所有就绪任务
curl -X POST "${MASTER_URL}/ai-master-svr/getlist/" \
  -F "dealStatus=ready" \
  -F "page_no=1" \
  -F "page_size=20"
```

**状态筛选选项**：
| dealStatus | 说明 |
|-----------|------|
| `ready` | 就绪，等待节点领取 |
| `running` | 正在执行 |
| `ok` | 已完成 |
| `failed` | 执行失败 |
| `killed` | 被终止 |
| `all` 或留空 | 所有状态 |

### 3.3 终止任务

```bash
curl -X POST "${MASTER_URL}/ai-master-svr/kill-task/" \
  -F "node_no=node_001" \
  -F "report_id=my_task_001" \
  -F "db_id=1"
```

> ⚠️ 终止后任务状态变为 `killed`，节点会收到信号并停止执行。

### 3.4 删除任务

```bash
# 删除单个任务
curl -X POST "${MASTER_URL}/ai-master-svr/remove-task/" \
  -F "report_id=my_task_001"

# 清空所有任务（⚠️危险⚠️）
curl -X POST "${MASTER_URL}/ai-master-svr/remove-all-task/"
```

---

## 4. 节点管理

### 4.1 注册节点

```bash
curl -X POST "${MASTER_URL}/ai-master-svr/node/register/" \
  -F "node_no=compute_node_001" \
  -F "deal_type_no=face_landmark" \
  -F "deal_type_version=1.0.0" \
  -F "node_loc=192.168.1.101:8000"
```

### 4.2 节点能力绑定

一个节点可以支持多种能力：

```bash
# 绑定能力
curl -X POST "${MASTER_URL}/ai-master-svr/node/bind-capability/" \
  -F "capability_id=face_landmark" \
  -F "node_no=compute_node_001"

# 解绑能力
curl -X POST "${MASTER_URL}/ai-master-svr/node/unbind-capability/" \
  -F "capability_id=face_landmark" \
  -F "node_no=compute_node_001"
```

### 4.3 查询节点

```bash
# 按能力查询节点
curl -X POST "${MASTER_URL}/ai-master-svr/node/query-by-capability/" \
  -F "capability_id=face_landmark" \
  -F "page_no=1" \
  -F "page_size=10"
```

### 4.4 注销节点

```bash
curl -X POST "${MASTER_URL}/ai-master-svr/node/remove/" \
  -F "node_no=compute_node_001"
```

---

## 5. 存储管理

### 5.1 存储连接配置

存储连接信息通过平台 API 动态获取，节点不需要硬编码存储凭据：

```
GET http://platform-api/aibase/dataServerConfig/getInfo/{conn_name}
```

**返回格式**：
```json
{
  "code": 200,
  "data": {
    "content": "{\"endpoint\":\"minio:9000\",\"accessKey\":\"xxx\",\"secretKey\":\"yyy\",\"bucketName\":\"ds-data\"}"
  }
}
```

### 5.2 支持的存储类型

| 类型 | 用途 | 配置名 |
|-----|------|-------|
| MinIO | S3 兼容对象存储 | minio_conn_xxx |
| 阿里云 OSS | 阿里云对象存储 | oss_conn_xxx |
| Azure Blob | 微软云存储 | azure_conn_xxx |
| 本地文件系统 | 开发/测试 | local |

### 5.3 数据目录结构

```
{storage_root}/
├── src-img/
│   └── {group_name}/
│       └── *.jpg           # 原始图片
├── tear_through/
│   └── {group_name}/
│       ├── src-mask/       # 原始遮罩
│       └── dst-mask/       # 标注结果
├── nasolabial_fold/
│   └── ...
└── wrinkle_stripe/
    └── ...
```

---

## 6. 监控与日志

### 6.1 查看任务日志

```bash
# 获取任务进度日志
curl -X POST "${MASTER_URL}/ai-master-svr/report-node-processing-batch/" \
  -F "report_id=my_task_001"
```

### 6.2 节点心跳状态

| node_op_status | 含义 |
|----------------|------|
| `1` | 繁忙（正在执行任务） |
| `2` | 空闲（等待任务） |

### 6.3 日志文件位置

| 组件 | 日志位置 | 说明 |
|-----|---------|------|
| Master | 标准输出 | Gunicorn 模式下输出到日志文件 |
| Node | 标准输出 | 由 ProcessFramework 输出 |
| 任务日志 | SQLite task_log_info 表 | 存储在数据库中 |

### 6.4 日志级别

Node 配置中可设置日志级别：

```json
{
  "log_level": "INFO",
  "log_level": "DEBUG"
}
```

---

## 7. 故障排除

### 7.1 常见问题

| 问题 | 可能原因 | 解决方案 |
|-----|---------|---------|
| 创建任务返回"记录已存在" | 相同 report_id 正在执行或刚完成 | 等待 2 分钟或使用新 report_id |
| 任务一直 ready | 无可用节点或节点能力不匹配 | 检查节点注册和能力绑定 |
| 节点无法连接 Master | IP/端口配置错误或防火墙 | 检查配置和防火墙规则 |
| 任务执行失败 | 模型缺失/存储连接失败/参数错误 | 查看节点日志 |
| SQLite 数据库报错 | 并发写入锁竞争 | 高并发时迁移到 MySQL |

### 7.2 调试命令

```bash
# 查看 Master 进程
ps aux | grep "gunicorn\|python.*app.py"

# 查看 Node 进程
ps aux | grep "ProcessFramework"

# 查看端口占用
netstat -tlnp | grep 8080

# 查看数据库内容
sqlite3 test.db "SELECT * FROM Query LIMIT 10;"

# 实时查看 Master 日志
tail -f /var/log/ds-master.log
```

### 7.3 健康检查脚本

```bash
#!/bin/bash
MASTER_URL="http://localhost:8080"

# 检查 Master 是否存活
if curl -sf "${MASTER_URL}/" > /dev/null 2>&1; then
    echo "✓ Master 服务正常"
else
    echo "✗ Master 服务异常"
    exit 1
fi

# 检查数据库
sqlite3 /path/to/test.db "SELECT COUNT(*) FROM Query;"

echo "✓ 健康检查完成"
```

---

*用户手册版本：1.0.0 | 最后更新：2026-04-18*
