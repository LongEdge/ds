# 模块索引

本文档包含 ds 分布式 AI 推理系统所有核心模块的详细技术分析报告。

---

## 📦 模块报告清单

### 基础架构层

| # | 模块名称 | 文件 | 报告链接 |
|---|---------|------|---------|
| 01 | Master 主服务 | `ai-master-svr/app.py` | [点击查看](modules/01_Master主服务.md) |
| 02 | 任务调度器 | `ai-master-svr/src/scheduler.py` | [点击查看](modules/02_任务调度器.md) |
| 03 | 任务 API 层 | `ai-master-svr/src/api/taskApi.py` | [点击查看](modules/03_任务API层.md) |
| 04 | 节点 API 层 | `ai-master-svr/src/api/nodeApi.py` | [点击查看](modules/04_节点API层.md) |
| 05 | 监控与报告 API | `monitorApi.py` / `reportApi.py` | [点击查看](modules/05_监控与报告API.md) |
| 06 | SQL 数据库层 | `ai-master-svr/src/dao/sql.py` | [点击查看](modules/06_SQL数据库层.md) |
| 07 | 消息中间件 | `broker/kafka_cli.py` / `mqttCli.py` | [点击查看](modules/07_消息中间件.md) |

### 节点端

| # | 模块名称 | 文件 | 报告链接 |
|---|---------|------|---------|
| 08 | 节点处理框架 | `ProcessFramework.py` | [点击查看](modules/08_节点处理框架.md) |
| 09 | 目标检测工具 | `ds_tdlab_0001_ImgObjRecognition` | [点击查看](modules/09_目标检测工具.md) |
| 10 | 模型训练工具 | `ds_tpsvr_0003_VisionModelTrain` | [点击查看](modules/10_模型训练工具.md) |
| 11 | 标注工具服务 | `ds_tsapp_0003_DsLabelToolSvr` | [点击查看](modules/11_标注工具服务.md) |
| 12 | 存储抽象层 | `src/conn/Storages.py` | [点击查看](modules/12_存储抽象层.md) |

---

## 🔗 快速导航

返回 [总目录](../README.md)

---
