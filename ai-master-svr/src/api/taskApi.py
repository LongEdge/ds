from flask import Blueprint, request, jsonify
from src.services.taskService import CTaskService
from src.utils.SysLogger import CSysLogger
from src.utils.response import CResponse


taskBp = Blueprint('taskApi', __name__)
logger = CSysLogger('taskApi')

taskService = CTaskService()
@taskBp.route('/ai-master-svr/create-task/', methods=['POST'])
def create_task():
    """
    master提交任务
    ---
    tags:
        -   任务模块
    parameters:
        -   name: report_id
            in: formData
            type: string
            required: true
            description: 任务id
        -   name: capability_id
            in: formData
            type: string
            required: true
            description: 哪种类型的任务
        -   name: param
            in: formData
            type: string
            required: true
            description: 提交的必要的数据参数, 例如数据url信息等
        -   name: deal_port
            in: formData
            type: string
            required: false
            description: 用哪个节点处理(你本地调试的Port)

    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    logger.info('收到创建任务请求')
    params = request.form.to_dict()
    logger.info('/ai-master-svr/create-task/ - {}'.format(params))

    report_id = params.get("report_id", None)
    capability_id = params.get("capability_id", None)
    deal_port = params.get("deal_port", None)
    param = params.get("param", None)

    res_dict = taskService.create_task(report_id, capability_id, param, deal_port)
    return CResponse.make(res_dict)



@taskBp.route('/ai-master-svr/batch-create-task/', methods=['POST'])
def batch_create_task():
    """
    master批量提交任务
    ---
    tags:
        -   任务模块
    parameters:
        -   name: report_ids
            in: formData
            type: string
            required: true
            description: 任务id
        -   name: deal_type_nos
            in: formData
            type: string
            required: true
            description: 用哪个工具处理
        -   name: params
            in: formData
            type: string
            required: true
            description: 提交的必要的数据参数, 例如数据url信息等
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    logger.info('收到批量创建任务请求')
    res_dict = request.form.to_dict()

    report_ids = request.json.loads(res_dict['report_ids'])
    deal_type_nos = request.json.loads(res_dict['deal_type_nos'])
    submit_params = request.json.loads(res_dict['params'])
    isPass = True

    logger.info('批量创建任务参数 - 任务数量: {}'.format(len(report_ids)))

    if isPass:
        status, msg = CTaskService.batch_create_task(report_ids, deal_type_nos, submit_params)
        if status == 0:
            logger.info('批量创建任务成功 - 任务数量: {}, msg: {}'.format(len(report_ids), msg))
        else:
            logger.error('批量创建任务失败 - msg: {}'.format(msg))
        return jsonify({
            'status': status,
            'msg': msg,
        })
    else:
        logger.error('analysis api key error.')
        return jsonify({
            'status': 0,
            'msg': 'request is failed, key is error',
        })


@taskBp.route('/ai-master-svr/prior-task/', methods=['POST'])
def prior_task():
    """
    master提升任务优先级为最高, 注意: 必须存在任务才有效
    ---
    tags:
        -   任务模块
    parameters:
        -   name: report_id
            in: formData
            type: string
            required: true
            description: 任务id
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    logger.info('收到提升任务优先级请求')
    res_dict = request.form.to_dict()

    report_id = res_dict['report_id']
    isPass = True

    logger.info('提升任务优先级参数 - report_id: {}'.format(report_id))

    if isPass:
        status, msg = CTaskService.prior_task(report_id)
        if status == 0:
            logger.info('提升任务优先级成功 - report_id: {}, msg: {}'.format(report_id, msg))
        else:
            logger.error('提升任务优先级失败 - report_id: {}, msg: {}'.format(report_id, msg))
        return jsonify({
            'status': status,
            'msg': msg,
        })
    else:
        logger.error('analysis api key error.')
        return jsonify({
            'status': -1,
            'msg': 'request for {} is failed, key is error'.format(report_id),
        })


@taskBp.route('/ai-master-svr/remove-task/', methods=['POST'])
def remove_task():
    """
    master删除任务
    ---
    tags:
        -   任务模块
    parameters:
        -   name: report_id
            in: formData
            type: string
            required: true
            description: 任务id
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    logger.info('收到删除任务请求')
    res_dict = request.form.to_dict()
    report_id = res_dict['report_id']
    isPass = True

    logger.info('删除任务参数 - report_id: {}'.format(report_id))

    if isPass:
        status, msg = CTaskService.remove_task(report_id)
        if status == 0:
            logger.info('删除任务成功 - report_id: {}, msg: {}'.format(report_id, msg))
        else:
            logger.error('删除任务失败 - report_id: {}, msg: {}'.format(report_id, msg))
        return jsonify({
            'status': status,
            'msg': msg,
        })
    else:
        logger.error('analysis api key error.')
        return jsonify({
            'status': -1,
            'msg': 'request for {} is failed, key is error'.format(report_id),
        })


@taskBp.route('/ai-master-svr/remove-all-task/', methods=['POST'])
def remove_all_task():
    """
    master删除所有的任务
    ---
    tags:
        -   任务模块
    parameters:
        -   name: client_key
            in: formData
            type: string
            required: false
            description: 提交密钥认证
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    logger.info('收到删除所有任务请求')
    res_dict = request.form.to_dict()
    if 1 != 1:
        client_key = res_dict['client_key']
    isPass = True

    if isPass:
        status, msg = CTaskService.remove_all_task()
        if status == 0:
            logger.info('删除所有任务成功 - msg: {}'.format(msg))
        else:
            logger.error('删除所有任务失败 - msg: {}'.format(msg))
        return jsonify({
            'status': status,
            'msg': msg,
        })
    else:
        logger.error('analysis api key error.')
        return jsonify({
            'status': -1,
            'msg': 'request for all task is failed, key is error',
        })


@taskBp.route('/ai-master-svr/handle/', methods=['POST'])
def handle_task():
    """
    node请求任务
    ---
    tags:
        -   任务模块
    parameters:
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 节点的唯一id
        -   name: dev_mode
            in: formData
            type: string
            required: false
            description: 节点是否为专用计算节点 -  空-是, debug-否 是的情况下, 只返回该节点的任务;反之不参与计算
            default: ""
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    params = request.form.to_dict()

    node_no = params.get('node_no', None)
    dev_mode = params.get('dev_mode', None)

    data = taskService.handle_task(node_no, dev_mode)

    return jsonify(data)


@taskBp.route('/ai-master-svr/getlist/', methods=['POST'])
def get_list_by_type():
    """
    master获得队列数据
    ---
    tags:
        -   任务模块
    parameters:
        -   name: dealStatus
            in: formData
            type: string
            required: false
            description: 任务id ready, running, ok, all
        -   name: page_no
            in: formData
            type: integer
            required: true
            description: 页码
        -   name: page_size
            in: formData
            type: integer
            required: true
            description: 条数
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    logger.info('收到获取任务列表请求')
    res_dict = request.form.to_dict()
    try:
        status = res_dict['dealStatus']
    except Exception as e:
        status = 'ready'

    try:
        page_no = int(res_dict['page_no'])
        page_size = int(res_dict['page_size'])
    except Exception as e:
        page_no = 1
        page_size = 20

    logger.info('获取任务列表参数 - status: {}, page_no: {}, page_size: {}'.format(status, page_no, page_size))

    retdata = CTaskService.get_task_list(status, page_no, page_size)
    if 0 != len(retdata):
        logger.info('获取任务列表成功 - 数量: {}'.format(len(retdata)))
        return jsonify({
           'status': 0,
           'msg': 'succ',
           'data': retdata,
        })
    else:
        logger.info('获取任务列表 - 无数据')
        return jsonify({
            'status': -1,
            'msg': 'failed',
            'data': None,
        })


@taskBp.route('/ai-master-svr/get-task-info/', methods=['POST'])
def get_task_info():
    """
    从master获得某一个报告id的全部信息
    ---
    tags:
        -   任务模块
    parameters:
        -   name: report_id
            in: formData
            type: string
            required: true
            description: 任务id
        -   name: client_key
            in: formData
            type: string
            required: false
            description: 提交密钥认证
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        401:
            description: 认证失败
        406:
            description: 参数名异常  
    """
    logger.info('收到获取任务信息请求')
    retdata = {
        'status': -1,
        'msg': 'failed',
        'data': {},
    }
    res_dict = request.form.to_dict()
    report_id = res_dict['report_id']

    logger.info('获取任务信息参数 - report_id: {}'.format(report_id))

    status = CTaskService.get_task_info(report_id)
    try:
        retdata['msg'] = 'succ'
        retdata['status'] = 0
        retdata['data'] = status
        logger.info('获取任务信息成功 - report_id: {}'.format(report_id))
        return jsonify(retdata)
    except Exception as e:
        logger.error('获取任务信息失败 - report_id: {}, error: {}'.format(report_id, str(e)))
        return jsonify(retdata)


@taskBp.route('/ai-master-svr/kill-task/', methods=['POST'])
def kill_task():
    """
    node终结某项任务
    ---
    tags:
        -   任务模块
    parameters:
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 节点id
        -   name: report_id
            in: formData
            type: string
            required: true
            description: 任务id
        -   name: db_id
            in: formData
            type: string
            required: true
            description: 任务数据库id
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    logger.info('收到终止任务请求')
    res_dict = request.form.to_dict()
    report_id = res_dict['report_id']
    node_no = res_dict['node_no']
    db_id = res_dict['db_id']

    logger.info('终止任务参数 - node_no: {}, report_id: {}, db_id: {}'.format(node_no, report_id, db_id))

    try:
        nRet = CTaskService.kill_task(report_id, db_id)
        logger.info('终止任务成功 - report_id: {}, db_id: {}'.format(report_id, db_id))
        return jsonify({
            'status': 0,
            'msg': '任务编号 {} 终止成功'.format(report_id),
            'data': None
        })
    except Exception as e:
        logger.error('终止任务失败 - report_id: {}, error: {}'.format(report_id, str(e)))
        return jsonify({
            'status': -1,
            'msg': '任务编号 {} 不存在, 终止失败'.format(report_id),
            'data': None
        })