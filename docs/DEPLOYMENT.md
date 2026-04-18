# DS 分布式 AI 推理系统 - 部署指南

> 版本：1.0.0 | 仓库：LongEdge/ds

---

## 📋 目录

1. [环境要求](#1-环境要求)
2. [快速部署](#2-快速部署)
3. [Master 服务部署](#3-master-服务部署)
4. [Node 节点部署](#4-node-节点部署)
5. [配置详解](#5-配置详解)
6. [存储配置](#6-存储配置)
7. [工具配置](#7-工具配置)
8. [验证测试](#8-验证测试)
9. [生产环境建议](#9-生产环境建议)

---

## 1. 环境要求

### 1.1 Python 环境

```bash
# 推荐 Python 3.8+
python --version  # >= 3.8

# 安装 pip
pip install --upgrade pip
```

### 1.2 系统依赖

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    git \
    vim

# CentOS/RHEL
sudo yum groupinstall -y "Development Tools"
sudo yum install -y \
    glibc-headers \
    glibc-devel \
    libuuid-devel \
    git
```

### 1.3 硬件建议

| 组件 | 最低配置 | 推荐配置 |
|-----|---------|---------|
| Master (CPU) | 2 核 | 4 核+ |
| Master (内存) | 4 GB | 8 GB+ |
| Node (CPU) | 4 核 | 8 核+ (GPU) |
| Node (内存) | 8 GB | 16 GB+ |
| Node (GPU) | - | NVIDIA GPU + CUDA 11.8+ |
| 磁盘 | 50 GB SSD | 200 GB+ SSD |

---

## 2. 快速部署

### 2.1 一键克隆 & 启动（开发模式）

```bash
# 克隆仓库
git clone https://github.com/LongEdge/ds.git
cd ds

# 方式一：Master + Node 合一部署（开发测试）
cd ai-master-svr
pip install -r requirements.txt
python app.py

# 方式二：分离部署（生产环境）
# 见下方详细部署
```

### 2.2 Docker 部署（推荐生产环境）

```bash
# 构建 Master 镜像
cd ai-master-svr
docker build -t ds-master:1.0.0 .

# 运行 Master 容器
docker run -d \
  --name ds-master \
  -p 8080:8080 \
  -v $(pwd)/config.yml:/app/config.yml \
  ds-master:1.0.0
```

---

## 3. Master 服务部署

### 3.1 目录结构

```
ai-master-svr/
├── app.py                  # 应用入口
├── config.yml              # 配置文件
├── gunicorn.conf.py        # Gunicorn 配置
├── requirements.txt        # Python 依赖
├── Dockerfile              # Docker 构建文件
├── setup.sh               # 安装脚本
├── release_run.sh         # 生产启动脚本
└── gunirelease_run.sh    # Gunicorn 启动脚本
```

### 3.2 安装依赖

```bash
cd ai-master-svr

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3.3 配置文件

创建/修改 `config.yml`：

```yaml
# 服务端口
port: 8080

# SQLite Web 服务端口（用于管理界面）
sqlite_port: 8001

# 版本号（必须与代码一致）
version: "1.0.0"

# 平台 API URL（获取模型类型列表）
plt_url: "http://your-platform-api.com"
```

### 3.4 启动方式

```bash
# 开发模式（直接运行）
python app.py

# 生产模式（Gunicorn 单进程）
gunicorn -c gunicorn.conf.py app:app

# 生产模式（Gunicorn 多进程）
bash release_run.sh

# Gunicorn 专用模式
bash gunirelease_run.sh
```

### 3.5 Gunicorn 配置

`gunicorn.conf.py` 关键配置：

```python
bind = "0.0.0.0:8080"
workers = 4  # 推荐: CPU核心数 * 2 + 1
worker_class = "sync"
timeout = 120
keepalive = 5

# 日志
accesslog = "-"
errorlog = "-"
loglevel = "info"
```

### 3.6 systemd 服务配置

创建 `/etc/systemd/system/ds-master.service`：

```ini
[Unit]
Description=DS Master Service
After=network.target

[Service]
Type=simple
User=dev
WorkingDirectory=/path/to/ds/ai-master-svr
ExecStart=/path/to/ds/ai-master-svr/venv/bin/gunicorn -c gunicorn.conf.py app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
# 启用服务
sudo systemctl daemon-reload
sudo systemctl enable ds-master
sudo systemctl start ds-master

# 查看状态
sudo systemctl status ds-master
```

---

## 4. Node 节点部署

### 4.1 目录结构

```
ai-node-svr/
└── code/src/
    ├── ProcessFramework.py   # 节点主框架
    ├── mqttCli.py            # MQTT 客户端（未使用）
    ├── Util.py               # 工具函数
    ├── SysLogger.py          # 日志
    └── tools/                # 可插拔工具
        ├── ds_tdlab_0001_ImgObjRecognition/
        ├── ds_tpsvr_0003_VisionModelTrain/
        └── ds_tsapp_0003_DsLabelToolSvr/
```

### 4.2 节点配置

创建 `node_config.json`：

```json
{
  "node_id": "node_001",
  "master_ip": "192.168.1.100",
  "master_port": 8080,
  "tool_name": "ds_tdlab_0001_ImgObjRecognition",
  "tool_id": "ds_tdlab_0001",
  "dconn_name": "default_minio",
  "local_data_path": "/tmp/ds_node_data",
  "log_level": "INFO"
}
```

### 4.3 启动节点

```bash
cd ai-node-svr/code/src

# 安装节点依赖（从 tools 的 requirements.txt）
pip install -r ../tools/ds_tdlab_0001_ImgObjRecognition/requirements.txt

# 启动节点
python ProcessFramework.py
```

### 4.4 多工具节点配置

一个节点可以支持多种工具，但同一时刻只运行一种：

```bash
# 启动目标检测工具节点
python ProcessFramework.py --tool ds_tdlab_0001_ImgObjRecognition

# 启动标注工具节点
python ProcessFramework.py --tool ds_tsapp_0003_DsLabelToolSvr
```

### 4.5 systemd 服务配置

创建 `/etc/systemd/system/ds-node.service`：

```ini
[Unit]
Description=DS Node Service
After=network.target

[Service]
Type=simple
User=dev
WorkingDirectory=/path/to/ds/ai-node-svr/code/src
ExecStart=/path/to/ds/ai-node-svr/code/src/venv/bin/python ProcessFramework.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 5. 配置详解

### 5.1 Master config.yml 完整配置

```yaml
# ========== 服务配置 ==========
port: 8080                    # Flask 服务端口
sqlite_port: 8001            # SQLite Web 管理端口
version: "1.0.0"             # 必须与代码版本匹配

# ========== 平台配置 ==========
plt_url: "http://platform-api.example.com"
# Master 会请求 {plt_url}/aiserver/serverModelType/open/list?tenantId=421461
# 获取可用的模型类型列表

# ========== 数据库配置 ==========
# 当前使用 SQLite (test.db)
# 生产环境建议切换到 MySQL/PostgreSQL

# ========== 调度配置 ==========
# scheduler:
#   prepare_interval: 0.2    # 任务准备轮询间隔（秒）
#   appoint_interval: 0.2   # 任务指派轮询间隔（秒）
#   update_interval: 5       # 模型类型更新间隔（秒）
#   monitor_interval: 2       # 节点监控间隔（秒）
```

### 5.2 节点配置完整参数

```json
{
  "node_id": "node_001",
  "master_ip": "192.168.1.100",
  "master_port": 8080,
  "tool_name": "ds_tdlab_0001_ImgObjRecognition",
  "tool_id": "ds_tdlab_0001",
  
  // 存储配置
  "dconn_name": "minio_conn_001",
  "wrinkle_remote_root_path": "/ai-label",
  
  // 本地配置
  "local_data_path": "/tmp/ds_node_data",
  "log_level": "INFO",
  
  // GPU 配置
  "cuda_visible_devices": "0",
  
  // 高级配置
  "task_timeout": 3600,
  "heartbeat_interval": 5,
  "progress_report_interval": 1
}
```

---

## 6. 存储配置

### 6.1 MinIO 配置

```yaml
# 平台 API 返回的连接信息格式
{
  "endpoint": "minio.example.com:9000",
  "accessKey": "your_access_key",
  "secretKey": "your_secret_key",
  "bucketName": "ds-data",
  "secure": false
}
```

### 6.2 阿里云 OSS 配置

```yaml
{
  "endpoint": "oss-cn-hangzhou.aliyuncs.com",
  "accessKeyId": "your_key_id",
  "accessKeySecret": "your_secret",
  "bucketName": "ds-bucket"
}
```

### 6.3 存储连接测试

```python
from conn.Storages import CStorages

storage = CStorages()

# 测试上传
storage.uploadFile(
    conn_name="minio_conn_001",
    local_path="/tmp/test.jpg",
    remote_path="/test/test.jpg"
)

# 测试下载
storage.downloadFile(
    conn_name="minio_conn_001",
    remote_path="/test/test.jpg",
    local_path="/tmp/downloaded.jpg"
)

# 测试列出文件
files = storage.listFiles(conn_name="minio_conn_001", remote_prefix="/test/")
print(files)
```

---

## 7. 工具配置

### 7.1 目标检测工具 (ImgObjRecognition)

`toolconfig.yml`:

```yaml
tool:
  name: ds_tdlab_0001_ImgObjRecognition
  id: ds_tdlab_0001
  version: 1.0.0
  description: 视频抽帧+图像分类+目标检测

models:
  classifier: yolov8x-cls.pt
  detector: yolov8n.pt
  
processing:
  frame_interval: 120      # 每隔多少帧处理一次
  similarity_threshold: 0.8  # SSIM 相似度阈值
  batch_size: 1

output:
  format: json
  save_images: true
  save_labels: true
```

### 7.2 模型训练工具 (VisionModelTrain)

`toolconfig.yml`:

```yaml
tool:
  name: ds_tpsvr_0003_VisionModelTrain
  id: ds_tpsvr_0003
  version: 1.0.0

training:
  model_type: unet
  batch_size: 8
  epochs: 100
  learning_rate: 0.001
  
dataset:
  train_split: 0.8
  val_split: 0.1
  test_split: 0.1
  
storage:
  conn_name: minio_conn_001
  remote_root: /vision-model-train
```

### 7.3 标注工具 (DsLabelToolSvr)

`toolconfig.yml`:

```yaml
tool:
  name: ds_tsapp_0003_DsLabelToolSvr
  id: ds_tsapp_0003
  version: 1.0.0
  type: web-service

server:
  host: 0.0.0.0
  port: 5000

storage:
  conn_name: minio_conn_001
  remote_root: /ai-label

wrinkle_types:
  - tear_through      # 泪沟纹
  - nasolabial_fold   # 法令纹
  - wrinkle_stripe     # 综合皱纹

image:
  zoom_ratio: 0.75    # 传输时缩放比例
  cache_size: 6000    # 缓存图片数量
```

---

## 8. 验证测试

### 8.1 Master 健康检查

```bash
# 检查服务是否启动
curl http://localhost:8080/

# 预期返回
{"message": "This is a ds-ai remote processing server"}
```

### 8.2 创建任务测试

```bash
curl -X POST http://localhost:8080/ai-master-svr/create-task/ \
  -F "report_id=test_001" \
  -F "capability_id=face_landmark" \
  -F "param={\"url\":\"http://example.com/image.jpg\"}" \
  -F "deal_port=8000"
```

### 8.3 查询任务列表

```bash
curl -X POST http://localhost:8080/ai-master-svr/getlist/ \
  -F "dealStatus=ready" \
  -F "page_no=1" \
  -F "page_size=10"
```

### 8.4 节点注册测试

```bash
curl -X POST http://localhost:8080/ai-master-svr/node/register/ \
  -F "node_no=test_node_001" \
  -F "deal_type_no=face_landmark" \
  -F "deal_type_version=1.0.0" \
  -F "node_loc=192.168.1.101"
```

### 8.5 节点请求任务测试

```bash
curl -X POST http://localhost:8080/ai-master-svr/handle/ \
  -F "node_no=test_node_001"
```

---

## 9. 生产环境建议

### 9.1 高可用部署

```
                    ┌─────────────────┐
                    │  负载均衡器     │
                    │ (Nginx/VIP)    │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐          ┌────▼────┐         ┌────▼────┐
   │ Master1 │          │ Master2 │         │ Master3 │
   │ (主)    │          │ (热备)  │         │ (冷备)  │
   └────┬────┘          └─────────┘         └─────────┘
        │
        └──────────────┬─────────────────────┘
                       │
              ┌────────▼────────┐
              │   数据库集群    │
              │ (MySQL/PG)     │
              └─────────────────┘
```

### 9.2 数据库迁移 (SQLite → MySQL)

```python
# 导出 SQLite 数据
sqlite3 test.db .dump > dump.sql

# 导入 MySQL
mysql -u root -p ds_database < dump.sql
```

### 9.3 监控与告警

```bash
# 监控 Master 存活
curl -f http://localhost:8080/ || alert "Master down!"

# 监控节点心跳（检查 last_heartbeat）
# 建议使用 Prometheus + Grafana
```

### 9.4 日志管理

```bash
# 使用 logrotate 轮转日志
cat /etc/logrotate.d/ds-master

/var/log/ds/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 644 dev dev
}
```

### 9.5 性能压测

```bash
# 使用 wrk 进行压力测试
wrk -t4 -c100 -d30s http://localhost:8080/ai-master-svr/getlist/

# 使用 locust 进行分布式压测
locust -f locustfile.py --headless -u 100 -r 10 -t 60s
```

---

## 附录：常见问题

| 问题 | 解决方案 |
|-----|---------|
| 任务一直处于 ready 状态 | 检查是否有节点注册，节点是否正常请求 handle |
| 节点无法连接 Master | 检查 master_ip/master_port 配置，防火墙是否放行 |
| 任务执行失败 | 查看节点日志，常见原因：模型文件缺失、存储连接失败 |
| SQLite 数据库锁 | 高并发场景建议迁移到 MySQL |
| 端口冲突 | 修改 config.yml 中的 port 和 sqlite_port |

---

*部署文档版本：1.0.0 | 最后更新：2026-04-18*
