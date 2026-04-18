# DS 分布式 AI 推理系统 - 开发指南

> 版本：1.0.0 | 仓库：LongEdge/ds

---

## 📋 目录

1. [开发环境搭建](#1-开发环境搭建)
2. [代码结构](#2-代码结构)
3. [新增工具开发](#3-新增工具开发)
4. [新增存储后端](#4-新增存储后端)
5. [API 扩展](#5-api-扩展)
6. [测试](#6-测试)
7. [代码规范](#7-代码规范)

---

## 1. 开发环境搭建

### 1.1 环境要求

```bash
# Python 3.8+
python --version

# Node.js (可选，前端开发)
node --version
```

### 1.2 克隆并安装

```bash
git clone https://github.com/LongEdge/ds.git
cd ds

# Master 依赖
cd ai-master-svr
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Node 依赖 (示例工具)
cd ../ai-node-svr/code/src/tools/ds_tdlab_0001_ImgObjRecognition
pip install -r requirements.txt
```

### 1.3 开发工具

```bash
# 代码格式化
pip install black isort

# 静态检查
pip install pylint flake8 mypy

# 测试
pip install pytest pytest-cov
```

---

## 2. 代码结构

```
ds/
├── ai-master-svr/           # 主控服务
│   ├── app.py              # Flask 入口
│   ├── config.yml          # 配置
│   ├── gunicorn.conf.py   # Gunicorn 配置
│   └── src/
│       ├── api/            # API 蓝图 (Flask Blueprint)
│       ├── services/       # 业务逻辑
│       ├── dao/            # 数据访问
│       ├── broker/         # 消息中间件
│       ├── entity/         # 实体类
│       ├── scheduler.py    # 调度器
│       └── utils/          # 工具类
│
└── ai-node-svr/            # 计算节点
    └── code/src/
        ├── ProcessFramework.py  # 节点主框架
        ├── mqttCli.py          # MQTT 客户端
        ├── Util.py             # 工具函数
        ├── SysLogger.py        # 日志
        └── tools/              # 可插拔工具
            ├── ds_tdlab_0001_ImgObjRecognition/
            ├── ds_tpsvr_0003_VisionModelTrain/
            └── ds_tsapp_0003_DsLabelToolSvr/
```

---

## 3. 新增工具开发

### 3.1 工具目录结构

```
tools/
└── ds_yourtool_xxx/
    ├── App.py              # 主类 (必须)
    ├── toolconfig.yml      # 工具配置
    ├── requirements.txt    # Python 依赖
    └── src/                # 源码 (可选)
        ├── process/
        ├── features/
        └── util/
```

### 3.2 App.py 模板

```python
import sys
sys.path.append('./')
sys.path.append("src/tools/ds_yourtool_xxx/")

from src.Process import CProcessor

class CApp:
    def __init__(self, node_cfg, progress_callback):
        """
        初始化工具
        @param node_cfg: 节点配置 (dict)
        @param progress_callback: 进度回调函数
        """
        self.node_cfg = node_cfg
        self.progress_callback = progress_callback
        
        # 创建处理器
        self.processor = CProcessor(self.node_cfg, self.progress_callback)
    
    def ProcessTask(self, param):
        """
        处理单个任务
        @param param: 任务参数字典
        """
        # TODO: 实现你的处理逻辑
        self.progress_callback(10, "开始处理...")
        
        # 执行处理
        result = self.processor.Process(param)
        
        self.progress_callback(100, "处理完成", "ok")
        return result
    
    def Cleanup(self):
        """清理资源"""
        pass

    def GetTaskReport(self):
        """获取任务报告"""
        pass

    def GetTaskFinalReport(self):
        """获取最终报告"""
        pass

    def onClose(self):
        """工具关闭时的回调"""
        print(f'{self.node_cfg["tool_id"]} 工具退出')
```

### 3.3 进度回调规范

```python
def progress_callback(deal_percent, deal_msg, deal_status=None, func_callback=None):
    """
    进度回调函数
    
    @param deal_percent: 处理进度 (-2 ~ 100)
                           -2: 准备中
                           0-99: 处理中
                           100: 成功完成
                           -1: 处理失败
    @param deal_msg: 状态说明信息
    @param deal_status: 状态标识
                           None: 普通进度消息
                           "ok": 成功完成
                           "failed": 处理失败
                           "killed": 被终止
    @param func_callback: 额外回调函数
    """
    self.progress_callback_queue.put({
        "deal_percent": deal_percent,
        "deal_time": time.time(),
        "deal_msg": deal_msg,
        "status": deal_status
    })
```

### 3.4 toolconfig.yml 示例

```yaml
tool:
  name: ds_yourtool_xxx
  id: ds_yourtool_xxx
  version: 1.0.0
  description: 你的工具描述

models:
  # 模型配置
  model_path: /path/to/model.pt
  input_size: [224, 224]
  
processing:
  batch_size: 8
  num_workers: 4

storage:
  conn_name: default_conn
  remote_root: /your-tool
```

### 3.5 工具注册

```python
# 在 ProcessFramework.py 中加载工具
tool_class = loadPyFile('App', 'CApp', 'src.tools.{}'.format(node_cfg['tool_name']))
tool_ins = tool_class(node_cfg, progress_callback)
```

**工具名称必须与 `tool_name` 配置匹配：**
```json
{
  "tool_name": "ds_yourtool_xxx"
}
```

---

## 4. 新增存储后端

### 4.1 实现存储类

创建 `ai-node-svr/code/src/conn/YourStorage.py`：

```python
import os

class CYourStorage:
    def __init__(self, conn_info):
        """
        初始化存储客户端
        @param conn_info: 连接配置字典
        """
        self.conn_info = conn_info
        self._init_client()
    
    def _init_client(self):
        """初始化存储客户端"""
        # TODO: 根据 conn_info 初始化你的存储客户端
        pass
    
    def uploadFile(self, local_path, remote_path):
        """上传文件"""
        # TODO: 实现上传逻辑
        pass
    
    def downloadFile(self, remote_path, local_path):
        """下载文件"""
        # TODO: 实现下载逻辑
        pass
    
    def listFiles(self, remote_prefix):
        """列出文件"""
        # TODO: 实现列表逻辑
        # 返回格式: [{'name': 'file.txt', 'ftype': 'F'}, {'name': 'dir/', 'ftype': 'D'}]
        return []
    
    def deleteFile(self, remote_path):
        """删除文件"""
        # TODO: 实现删除逻辑
        pass
    
    def checkFileExist(self, remote_path):
        """检查文件是否存在"""
        # TODO: 实现检查逻辑
        return False
```

### 4.2 注册到 Storages 调度器

修改 `conn/Storages.py`：

```python
from .YourStorage import CYourStorage

class CStorages:
    def uploadFile(self, conn_name, local_path, remote_path):
        conn_info = self.get_conn_info(conn_name)
        conn_type = conn_info.get('type', 'local')
        
        # 添加新的存储类型
        if conn_type == 'your_storage':
            if not hasattr(self, '_your_storage'):
                self._your_storage = CYourStorage(conn_info)
            return self._your_storage.uploadFile(local_path, remote_path)
        
        # ... 其他存储类型
```

---

## 5. API 扩展

### 5.1 新增 API Blueprint

创建 `src/api/myApi.py`：

```python
from flask import Blueprint, request, jsonify
from src.utils.SysLogger import CSysLogger
from src.utils.response import CResponse

myBp = Blueprint('myApi', __name__)
logger = CSysLogger('myApi')

@myBp.route('/ai-master-svr/my-action/', methods=['POST'])
def my_action():
    """
    我的自定义 API
    ---
    tags:
      - 自定义模块
    parameters:
      - name: param1
        in: formData
        type: string
        required: true
        description: 参数1
    responses:
      200:
        description: 成功
    """
    params = request.form.to_dict()
    logger.info(f'收到请求: {params}')
    
    # TODO: 实现业务逻辑
    
    return CResponse.make({'code': 0, 'msg': 'success'})
```

### 5.2 注册 Blueprint

在 `app.py` 中注册：

```python
from src.api.myApi import myBp

app.register_blueprint(myBp)
```

### 5.3 添加 Service 层

创建 `src/services/myService.py`：

```python
from src.services.baseService import CBaseService

class CMyService(CBaseService):
    def __init__(self):
        self.init_res()
    
    def my_method(self, param):
        """业务方法"""
        result = {'code': 0, 'data': {}}
        # TODO: 实现业务逻辑
        return result
```

---

## 6. 测试

### 6.1 单元测试

```bash
# 创建测试文件
mkdir -p tests

# 运行测试
pytest tests/ -v

# 带覆盖率
pytest tests/ --cov=src --cov-report=html
```

### 6.2 测试示例

创建 `tests/test_task_api.py`：

```python
import pytest
import sys
sys.path.insert(0, '../ai-master-svr')

from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health_check(client):
    """测试健康检查"""
    response = client.get('/')
    assert response.status_code == 200
    assert b'ds-ai' in response.data

def test_create_task(client):
    """测试创建任务"""
    response = client.post('/ai-master-svr/create-task/', data={
        'report_id': 'test_001',
        'capability_id': 'face_landmark',
        'param': '{"url": "http://example.com/test.jpg"}'
    })
    assert response.status_code == 200
```

### 6.3 集成测试

```bash
# 启动 Master 和 Node
# 然后运行集成测试
pytest tests/integration/ -v
```

---

## 7. 代码规范

### 7.1 命名规范

| 类型 | 规范 | 示例 |
|-----|------|------|
| 类名 | PascalCase | `CScheduler`, `CTaskService` |
| 方法名 | snake_case | `create_task`, `handle_node` |
| 变量名 | snake_case | `node_cfg`, `report_id` |
| 常量 | UPPER_SNAKE | `MAXSIZE_QUEUE`, `NODE_SAVE_DAYS` |
| 文件名 | snake_case | `task_api.py`, `base_service.py` |
| Blueprint | snake_case | `taskBp`, `nodeBp` |

### 7.2 日志规范

```python
from src.utils.SysLogger import CSysLogger

logger = CSysLogger(__name__)

# 使用示例
logger.info(f'操作成功 - id: {some_id}')
logger.error(f'操作失败 - error: {str(e)}')
logger.warn(f'警告信息 - status: {status}')
```

### 7.3 响应格式规范

```python
from src.utils.response import CResponse

# 成功响应
return CResponse.make({'code': 0, 'msg': 'success', 'data': {...}})

# 错误响应
return CResponse.make({'code': -1, 'msg': 'error message', 'data': None})
```

### 7.4 SQL 规范

```python
# 使用参数化查询，防止 SQL 注入
sql = "SELECT * FROM Query WHERE report_id = ?"
cursor.execute(sql, (report_id,))

# 批量操作使用事务
try:
    for item in items:
        self.c.execute("INSERT INTO ... VALUES(?,?)", item)
    self.conn.commit()
except Exception as e:
    self.conn.rollback()
    raise
```

### 7.5 Git 提交规范

```
feat: 新功能
fix: 修复 bug
docs: 文档更新
refactor: 代码重构
perf: 性能优化
test: 测试相关
chore: 构建/工具更新
```

**示例**：
```
feat(task): 添加批量任务创建接口

新增 /batch-create-task/ API，支持批量创建任务
- 支持最多 1000 个任务批量提交
- 失败任务独立返回，不影响其他任务
```

---

## 附录：常用脚本

### 数据库初始化

```bash
sqlite3 test.db << 'EOF'
CREATE TABLE IF NOT EXISTS Query (
    node_no integer,
    report_id VARCHAR(255),
    db_id integer PRIMARY KEY,
    deal_status varchar(25),
    ready_time integer,
    start_time integer,
    end_time integer
);

CREATE TABLE IF NOT EXISTS task_init (
    db_id integer,
    report_id VARCHAR(255),
    task_type VARCHAR(255),
    task_info TEXT,
    is_appointment integer
);
EOF
```

---

*开发指南版本：1.0.0 | 最后更新：2026-04-18*
