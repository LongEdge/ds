# 01 - Master 主服务 (app.py)

## 📋 概述

| 属性 | 值 |
|-----|-----|
| 文件 | `ai-master-svr/app.py` |
| 类型 | Flask 应用入口 |
| 框架 | Flask + Gunicorn + APScheduler |
| 依赖 | Flask, flasgger(Swagger), yaml, APScheduler |

---

## 🏗️ 架构设计

### 启动流程

```
app.py 启动
    │
    ├─ 1. 加载 config.yml 配置
    │
    ├─ 2. 初始化 SQLite 连接 (Sql, dbWeb)
    │
    ├─ 3. 初始化 CScheduler 调度器
    │       └─ 内部启动 BackgroundScheduler
    │           └─ 每 2 秒执行 monitor_node_info()
    │
    ├─ 4. 注册 5 个 Blueprint API 路由
    │       ├─ taskBp      (任务管理)
    │       ├─ reportBp    (报告)
    │       ├─ monitorBp  (监控)
    │       ├─ nodeBp     (节点)
    │       └─ gatewayBp   (网关)
    │
    ├─ 5. 版本校验 (config.yml 的 version 必须等于代码 VERSION = "1.0.0")
    │
    └─ 6. app.run(host='0.0.0.0', port=配置端口)
```

---

## 🔧 核心组件

### 1. 配置加载
```python
with open('config.yml', 'r', encoding='utf-8') as f:
    configs = yaml.load(f, Loader=yaml.SafeLoader)
port = configs['port']
plt_url = configs['plt_url']
sqlite_port = configs['sqlite_port']
version = configs['version']
```

### 2. 数据库连接
```python
sql_monitor = Sql()                    # 监控用连接
dbWeb = CDb(app, sqlite_port)          # Web版SQLite
sql_task_appoint = Sql()               # 任务分配用连接
```

### 3. 调度器初始化
```python
plt_app_url = plt_url.strip('/') + "/aiserver/serverModelType/open/list?tenantId=421461"
task_appoint = CScheduler(sql_task_appoint, plt_app_url)
```
> `CScheduler` 初始化时会调用 `auto_scheduler()`，启动 `BackgroundScheduler`，每 2 秒执行 `monitor_node_info()` 进行节点状态监控。

### 4. Blueprint 注册
```python
app.register_blueprint(taskBp)      # /ai-master-svr/create-task/
app.register_blueprint(reportBp)
app.register_blueprint(monitorBp)
app.register_blueprint(nodeBp)
app.register_blueprint(gatewayBp)
```

---

## 🌐 API 路由汇总

所有 API 前缀：`/ai-master-svr/`

| 路由 | 方法 | Blueprint | 功能 |
|-----|------|-----------|------|
| `/` | GET | (root) | 健康检查，返回 `{"message": "This is a ds-ai remote processing server"}` |
| `/ai-master-svr/create-task/` | POST | taskBp | 创建任务 |
| `/ai-master-svr/batch-create-task/` | POST | taskBp | 批量创建任务 |
| `/ai-master-svr/handle/` | POST | taskBp | 节点请求任务 |
| `/ai-master-svr/getlist/` | POST | taskBp | 获取任务列表 |
| `/ai-master-svr/kill-task/` | POST | taskBp | 终止任务 |

---

## ⚠️ 关键设计点

### 1. 版本校验
```python
if version != VERSION:
    logger.error('version error. configs version is {}, but code version is {}'.format(version, VERSION))
    exit(-1)
```
- 配置文件中的 `version` 必须与代码中 `VERSION = "1.0.0"` 匹配才能启动
- **这是为防止配置与代码不匹配导致的问题**

### 2. SQLite 多连接
- `sql_monitor` → 监控节点状态
- `sql_task_appoint` → 任务指派
- `dbWeb` → Web 查询接口

### 3. 定时任务（Scheduler）
- **当前激活**：`monitor_node_info()` — 每 2 秒更新节点存活状态、删除无效节点、清理无效任务
- **已注释禁用**：`auto_prepare_task()`、`auto_appoint_task()`、`auto_update_model_type()` — 原本用于任务队列自动分发

### 4. Swagger 集成
```python
Swagger(app)  # 启用 Swagger API 文档
```

---

## 🔄 与 Scheduler 的关系

`app.py` 创建的 `CScheduler` 实例 `task_appoint` 是**全局单例**，其 `BackgroundScheduler` 在后台线程运行：

```
CScheduler.auto_scheduler()
    └─ BackgroundScheduler (每 2 秒)
        └─ monitor_node_info()
            ├─ sql_monitor.auto_update_node_live_status_by_master()  # 更新节点状态
            ├─ sql_monitor.auto_del_invaild_node()                   # 删除无效节点
            └─ sql_monitor.auto_clean_invalid_task()                 # 清理无效任务
```

---

## 📦 依赖

```
flask>=2.0
flasgger>=0.9.5
pyyaml>=5.0
apscheduler>=3.0
requests>=2.25
```

---

## 🎯 扩展建议

1. **版本校验太严格** — 可改为 Warning 而非直接 Exit
2. **SQLite 并发** — 多连接共享同一文件，并发写入可能存在锁竞争
3. **Scheduler 未完全启用** — `auto_prepare_task` 和 `auto_appoint_task` 被注释，如需自动任务分发需启用
4. **无认证中间件** — API 层级无权限校验，生产环境需添加
