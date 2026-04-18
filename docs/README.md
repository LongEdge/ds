# DS 分布式AI模型推理系统 - 完整技术文档

## 📦 项目概述

**ds** 是一个**分布式AI视觉模型推理系统**，采用 Master-Node 架构，支持多任务调度、节点管理、模型热加载、存储抽象等功能。系统主要用于 **AI图像相关任务**（目标检测、图像分类、人脸/皱纹检测、模型训练等）。

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         ai-master-svr                            │
│                      (主控服务 Flask)                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────┐ │
│  │ taskApi │  │nodeApi  │  │monitor  │  │reportApi│  │gateway │ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └────────┘ │
│        │            │            │            │            │      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                     Service Layer                            │ │
│  │  (taskService│nodeService│monitorService│reportService...) │ │
│  └─────────────────────────────────────────────────────────────┘ │
│        │            │            │            │                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      DAO Layer                               │ │
│  │       (sql.py│taskDao│nodeDao│gatewayDao│dbWeb)            │ │
│  └─────────────────────────────────────────────────────────────┘ │
│        │                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │   Kafka      │  │   MQTT       │  │  Scheduler (APScheduler)│  │
│  │  (消息队列)   │  │  (事件发布)   │  │   (定时任务分发)      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                    HTTP / MQTT 协议
                              │
┌─────────────────────────────────────────────────────────────────┐
│                         ai-node-svr                             │
│                      (计算节点服务)                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              ProcessFramework (多进程+多线程)               │ │
│  │   - node_process_worker: 主任务循环                          │ │
│  │   - node_heart_beat: 心跳上报                               │ │
│  │   - monitor_kill_signal: 终止信号监控                        │ │
│  │   - _read_progress_queue_thread: 进度读取                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│        │                                                         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Tools (可插拔工具)                         │ │
│  │  ┌─────────────────┐ ┌─────────────────┐ ┌──────────────────┐  │ │
│  │  │ImgObjRecognition│ │VisionModelTrain │ │ DsLabelToolSvr  │  │ │
│  │  │  (目标检测)     │ │   (模型训练)    │ │   (标注工具)    │  │ │
│  │  └─────────────────┘ └─────────────────┘ └──────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│        │                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │   MinIO      │  │   OSS        │  │   Azure Blob          │   │
│  │  (存储抽象)  │  │  (阿里云OSS)  │  │   (Azure存储)         │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 仓库结构

```
ds/
├── ai-master-svr/          # 主控服务
│   ├── app.py              # Flask 应用入口
│   ├── config.yml          # 配置文件
│   ├── gunicorn.conf.py    # Gunicorn 配置
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── setup.sh / release_run.sh / gunirelease_run.sh
│   └── src/
│       ├── api/            # REST API 蓝图
│       │   ├── taskApi.py       # 任务管理 API
│       │   ├── nodeApi.py       # 节点管理 API
│       │   ├── monitorApi.py    # 监控 API
│       │   ├── reportApi.py    # 报告 API
│       │   └── gatewayApi.py    # 网关 API
│       ├── services/       # 业务逻辑层
│       │   ├── taskService.py
│       │   ├── nodeService.py
│       │   ├── monitorService.py
│       │   ├── reportService.py
│       │   ├── gatewayService.py
│       │   └── baseService.py
│       ├── dao/            # 数据访问层
│       │   ├── sql.py           # SQL 底层封装
│       │   ├── taskDao.py
│       │   ├── nodeDao.py
│       │   ├── gatewayDao.py
│       │   ├── db.py
│       │   └── dbWeb.py
│       ├── broker/         # 消息中间件
│       │   ├── kafka_cli.py     # Kafka 生产者
│       │   ├── kafka_rec.py    # Kafka 消费者
│       │   └── mqttCli.py      # MQTT 客户端
│       ├── entity/
│       │   └── gatewayEntity.py
│       ├── scheduler.py    # 任务调度器
│       └── utils/
│           ├── SysLogger.py
│           ├── response.py
│           └── errorEnum.py
│
└── ai-node-svr/            # 计算节点
    └── code/src/
        ├── ProcessFramework.py  # 节点主框架
        ├── mqttCli.py           # MQTT 客户端
        ├── SysLogger.py
        ├── Util.py
        └── tools/
            ├── ds_tdlab_0001_ImgObjRecognition/   # 目标检测工具
            │   ├── App.py
            │   ├── toolconfig.yml
            │   └── requirements.txt
            ├── ds_tpsvr_0003_VisionModelTrain/     # 视觉模型训练工具
            │   ├── App.py
            │   ├── toolconfig.yml
            │   ├── requirements.txt
            │   └── src/
            │       ├── Process.py
            │       ├── configs/      # 模型配置
            │       ├── conn/          # 存储连接 (Local/Minio/OSS/RemoteLinux)
            │       ├── features/      # 训练特征模块
            │       │   ├── faceLandmark/
            │       │   ├── imgClassify/
            │       │   ├── imgWrinkle/
            │       │   └── videoTracking/
            │       ├── process/       # 处理流程
            │       ├── service/       # API服务
            │       └── util/
            └── ds_tsapp_0003_DsLabelToolSvr/       # 图像标注工具
                ├── App.py
                ├── toolconfig.yml
                ├── requirements.txt
                └── src/
                    ├── Process.py
                    ├── conn/          # 存储抽象
                    ├── features/      # 标注功能
                    │   └── common/ (imgbase.py, imgplus.py)
                    ├── process/       # 处理流程
                    │   ├── proc_api_wrinkle.py    # 皱纹标注
                    │   ├── proc_api_imgclassify.py # 图像分类
                    │   └── proc_api_datamng.py    # 数据管理
                    ├── templates/     # 前端HTML模板
                    └── util/
```

---

## 🔑 核心模块列表

| # | 模块名称 | 文件路径 | 类型 | 功能描述 |
|---|---------|---------|------|---------|
| 1 | Master主服务 | `ai-master-svr/app.py` | 服务入口 | Flask应用初始化、蓝图注册、配置加载 |
| 2 | 任务调度器 | `ai-master-svr/src/scheduler.py` | 调度引擎 | 任务分发队列、自动指派、节点监控 |
| 3 | 任务API | `ai-master-svr/src/api/taskApi.py` | API | 任务CRUD、节点领取、任务终止 |
| 4 | 节点API | `ai-master-svr/src/api/nodeApi.py` | API | 节点注册、注销、能力绑定 |
| 5 | 监控API | `ai-master-svr/src/api/monitorApi.py` | API | 节点状态监控 |
| 6 | 报告API | `ai-master-svr/src/api/reportApi.py` | API | 任务报告生成与查询 |
| 7 | 网关API | `ai-master-svr/src/api/gatewayApi.py` | API | 外部网关接入 |
| 8 | 任务服务 | `ai-master-svr/src/services/taskService.py` | Service | 任务业务逻辑 |
| 9 | 节点服务 | `ai-master-svr/src/services/nodeService.py` | Service | 节点业务逻辑 |
| 10 | SQL底层 | `ai-master-svr/src/dao/sql.py` | DAO | SQLite操作、任务查询、任务分发逻辑 |
| 11 | Kafka生产者 | `ai-master-svr/src/broker/kafka_cli.py` | Broker | 消息写入Kafka |
| 12 | MQTT客户端 | `ai-master-svr/src/broker/mqttCli.py` | Broker | MQTT消息订阅/发布 |
| 13 | 节点处理框架 | `ai-node-svr/code/src/ProcessFramework.py` | Node框架 | 多进程任务执行、进度上报、信号处理 |
| 14 | 目标检测工具 | `ds_tdlab_0001_ImgObjRecognition/App.py` | Tool | YOLO视频抽帧+分类+检测 |
| 15 | 模型训练工具 | `ds_tpsvr_0003_VisionModelTrain/App.py` | Tool | 视觉模型训练框架 |
| 16 | 标注工具服务 | `ds_tsapp_0003_DsLabelToolSvr/App.py` | Tool | 图像标注Web服务 |
| 17 | 皱纹标注处理 | `ds_tsapp_0003_DsLabelToolSvr/src/process/proc_api_wrinkle.py` | Processor | 皱纹标注核心算法 |
| 18 | 存储抽象层 | `ds_tpsvr_0003_VisionModelTrain/src/conn/Storages.py` | Storage | Local/Minio/OSS多存储统一接口 |

---

## 🔌 通信协议

| 协议 | 用途 | 方向 |
|-----|------|------|
| **HTTP REST** | 节点向Master请求任务、上报状态 | Node → Master |
| **MQTT** | 事件发布订阅、进度推送 | Master ↔ Node |
| **Kafka** | 批量消息队列、日志收集 | Master 内/外部 |
| **WebSocket** | 实时进度推送（部分工具） | Node → Frontend |

---

## 📊 数据表结构（SQLite）

### Query 表（主任务表）
```sql
CREATE TABLE Query (
    node_no integer,           -- 执行节点编号
    report_id VARCHAR(255),    -- 任务/报告唯一ID
    db_id integer,              -- 数据库自增ID
    deal_status varchar(25),     -- 任务状态: init/ready/running/ok/failed/killed
    ready_time integer,         -- 就绪时间戳
    start_time integer,         -- 开始执行时间戳
    end_time integer,           -- 结束时间戳
    ...
)
```

### task_init 表（任务初始化）
```sql
CREATE TABLE task_init (
    db_id, report_id, task_type, task_info, is_appointment
)
```

### task_log_info 表（任务进度日志）
```sql
CREATE TABLE task_log_info (
    node_no, report_id, deal_time, task_info
)
```

---

## ⚙️ 配置说明

配置文件：`ai-master-svr/config.yml`

```yaml
port: 8080                    # 服务端口
sqlite_port: 8001             # SQLite Web服务端口
plt_url: "http://xxx/..."      # 平台API URL（获取模型类型列表）
version: "1.0.0"               # 版本号（与代码版本匹配才启动）
```

---

## 🚀 运行模式

### Master 服务
```bash
# 开发模式
python app.py

# 生产模式 (Gunicorn)
gunicorn -c gunicorn.conf.py app:app

# 或使用封装脚本
bash release_run.sh
bash gunirelease_run.sh
```

### Node 节点
```bash
# 节点通过 ProcessFramework 独立运行
# 配置 master_ip 和 master_port 连接 Master
python ProcessFramework.py
```

---

## 📄 各模块详细报告

- [01_Master主服务.md](modules/01_Master主服务.md)
- [02_任务调度器.md](modules/02_任务调度器.md)
- [03_任务API层.md](modules/03_任务API层.md)
- [04_节点API层.md](modules/04_节点API层.md)
- [05_监控与报告API.md](modules/05_监控与报告API.md)
- [06_SQL数据库层.md](modules/06_SQL数据库层.md)
- [07_消息中间件.md](modules/07_消息中间件.md)
- [08_节点处理框架.md](modules/08_节点处理框架.md)
- [09_目标检测工具.md](modules/09_目标检测工具.md)
- [10_模型训练工具.md](modules/10_模型训练工具.md)
- [11_标注工具服务.md](modules/11_标注工具服务.md)
- [12_存储抽象层.md](modules/12_存储抽象层.md)
