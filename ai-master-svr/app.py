import yaml
import logging
from flask import Flask
from flask import jsonify
from flasgger import Swagger
from src.utils.SysLogger import CSysLogger
from src.dao.sql import Sql
from src.scheduler import CScheduler
from src.dao import dbWeb


from src.api.taskApi import taskBp
from src.api.reportApi import reportBp
from src.api.monitorApi import monitorBp
from src.api.nodeApi import nodeBp
from src.api.gatewayApi import gatewayBp


VERSION = "1.0.0"
configs = None
app = Flask(__name__)
log = logging.getLogger('werkzeug')
# log.disabled = True

Swagger(app)
logger = CSysLogger('root')
with open('config.yml', 'r', encoding='utf-8') as f:
    configs = yaml.load(f, Loader=yaml.SafeLoader)
port = configs['port']
plt_url = configs['plt_url']
sqlite_port = configs['sqlite_port']

sql_monitor = Sql() # 给监控建立的连接
dbWeb = dbWeb.CDb(app, sqlite_port)
sql_task_appoint = Sql() # 给任务分配建立的连接

plt_app_url = plt_url.strip('/')+"/aiserver/serverModelType/open/list?tenantId=421461"
task_appoint = CScheduler(sql_task_appoint, plt_app_url)

app.register_blueprint(taskBp)
app.register_blueprint(reportBp)
app.register_blueprint(monitorBp)
app.register_blueprint(nodeBp)
app.register_blueprint(gatewayBp)



@app.route('/')
def index():
    return jsonify({
        'message': 'This is a ds-ai remote processing server'
    })


if __name__ == '__main__':
    version = configs['version']
    if version != VERSION:
        logger.error('version error. configs version is {}, but code version is {}'.format(version, VERSION))
        exit(-1)
    app.run(host='0.0.0.0', port=port)