from flask import Blueprint, request, jsonify
from src.services.reportService import CReportService
from src.utils.SysLogger import CSysLogger
import json
reportBp = Blueprint('reportApi', __name__)
logger = CSysLogger('reportApi')


@reportBp.route('/ai-master-svr/update-task-status/', methods=['POST'])
def update_sql_status():
    """
    node报告任务状态
    ---
    tags:
        -   汇报模块
    parameters:
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 计算节点id
        -   name: report_id
            in: formData
            type: string
            required: true
            description: 任务报告id
        -   name: status
            in: formData
            type: string
            required: true
            description: 任务执行状态
        -   name: db_id
            in: formData
            type: string
            required: true
            description: 任务唯一编号id
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    logger.info('收到更新任务状态请求')
    nRet = -1
    res_dict = request.form.to_dict()
    node_no = res_dict['node_no']
    status = res_dict['status']
    report_id = res_dict['report_id']
    db_id = res_dict['db_id']

    logger.info('更新任务状态参数 - node_no: {}, report_id: {}, db_id: {}, status: {}'.format(node_no, report_id, db_id, status))

    nRet = CReportService.update_task_status(report_id, db_id, status)
    data = {
        'reportid': report_id,
        'db_id': db_id,
        'retmsg': nRet
    }
    logger.info('更新任务状态完成 - report_id: {}, db_id: {}, retmsg: {}'.format(report_id, db_id, nRet))
    return json.dumps(data)


@reportBp.route('/ai-master-svr/update-task-entire-progress/', methods=['POST'])
def update_sql_entire_progress():
    """
    node报告任务状态
    ---
    tags:
        -   汇报模块
    parameters:
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 计算节点id
        -   name: report_id
            in: formData
            type: string
            required: true
            description: 任务报告id
        -   name: progress
            in: formData
            type: string
            required: true
            description: 任务总体状态
        -   name: db_id
            in: formData
            type: string
            required: true
            description: 任务唯一编号id
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    logger.info('收到更新任务进度请求')
    nRet = -1
    res_dict = request.get_json()
    logger.debug('请求参数: {}'.format(res_dict))
    node_no = res_dict['node_no']
    progress = res_dict['progress']
    report_id = res_dict['report_id']
    db_id = res_dict['db_id']

    logger.info('更新任务进度参数 - node_no: {}, report_id: {}, db_id: {}, progress: {}'.format(node_no, report_id, db_id, progress))

    nRet = CReportService.update_task_progress(report_id, db_id, progress)
    data = {
        'reportid': report_id,
        'db_id': db_id,
        'retmsg': nRet
    }
    logger.info('更新任务进度完成 - report_id: {}, db_id: {}, retmsg: {}'.format(report_id, db_id, nRet))
    return json.dumps(data)


@reportBp.route('/ai-master-svr/report-node-live-status/', methods=['POST'])
def report_node_live_status():
    """
    node报告心跳
    ---
    tags:
        -   汇报模块
    parameters:
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 任务id
        -   name: node_op_status
            in: formData
            type: string
            required: true
            description: 任务运行状态描述 0=离线, 1=运行, 2=在线
        -   name: clientKey
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
    res_dict = request.form.to_dict()
    node_no = res_dict['node_no']
    node_op_status = res_dict['node_op_status']

    node_live_status = CReportService.report_node_live_status(node_no, node_op_status)
    if True == node_live_status:
        return jsonify({
            'status': 0,
            'msg':'report node live status for {} is succ'.format(node_no),
            'data': None
        })
    else:
        return jsonify({
            'status': -1,
            'msg':'report node live status for {} is failed'.format(node_no),
            'data': None
        })


@reportBp.route('/ai-master-svr/report-node-processing/', methods=['POST'])
def report_node_processing():
    """
    node报告计算进度
    ---
    tags:
        -   汇报模块
    parameters:
        -   name: report_id
            in: formData
            type: string
            required: true
            description: 任务id
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 计算节点id
        -   name: task_pocessing_val
            in: formData
            type: integer
            required: true
            description: 任务进度 0-100
        -   name: clientKey
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
    logger.info('收到节点计算进度报告请求')
    res_dict = request.get_json()
    report_id = res_dict['report_id']
    node_no = res_dict['node_no']
    task_info = res_dict['task_info']

    logger.info('节点计算进度报告参数 - report_id: {}, node_no: {}'.format(report_id, node_no))

    status, msg = CReportService.report_node_processing(report_id, node_no, task_info)
    if status == 0:
        logger.info('节点计算进度报告成功 - report_id: {}, node_no: {}'.format(report_id, node_no))
    else:
        logger.error('节点计算进度报告失败 - report_id: {}, node_no: {}'.format(report_id, node_no))

    return jsonify({
        'status': status,
        'msg': msg,
        'data': None
    })


@reportBp.route('/ai-master-svr/report-node-processing-batch/', methods=['POST'])
def report_node_processing_batch():
    """
    node报告计算进度(json模块)
    ---
    tags:
        -   汇报模块
    parameters:
        -   name: report_id
            in: formData
            type: string
            required: true
            description: 任务id
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 计算节点id
        -   name: clientKey
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
    logger.info('收到节点批量计算进度报告请求')
    res_dict = request.get_json()
    report_id = res_dict['report_id']
    node_no = res_dict['node_no']
    task_info_list = res_dict['task_info']

    logger.info('节点批量计算进度报告参数 - report_id: {}, node_no: {}, task_info_list长度: {}'.format(report_id, node_no, len(task_info_list) if isinstance(task_info_list, list) else 0))

    status, msg = CReportService.report_node_processing_batch(report_id, node_no, task_info_list)
    if status == 0:
        logger.info('节点批量计算进度报告成功 - report_id: {}, node_no: {}'.format(report_id, node_no))
    else:
        logger.error('节点批量计算进度报告失败 - report_id: {}, node_no: {}'.format(report_id, node_no))

    return jsonify({
        'status': status,
        'msg': msg,
        'data': None
    })


@reportBp.route('/ai-master-svr/query-task-processing/', methods=['POST'])
def query_task_processing():
    """
    master查询节点任务进度
    ---
    tags:
        -   汇报模块
    parameters:
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 计算节点id
        -   name: report_id
            in: formData
            type: string
            required: false
            description: 任务名称(可选)
        -   name: page_no
            in: formData
            type: integer
            required: false
            description: 页码
        -   name: page_size
            in: formData
            type: integer
            required: false
            description: 条数
        -   name: clientKey
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
    logger.info('收到查询节点任务进度请求')
    res_dict = request.form.to_dict()
    node_no = res_dict['node_no']
    try:
        report_id = res_dict['report_id']
    except Exception as e:
        report_id = ""

    try:
        page_no = int(res_dict['page_no'])
        page_size = int(res_dict['page_size'])
    except Exception as e:
        page_no = 1
        page_size = 50

    logger.info('查询节点任务进度参数 - node_no: {}, report_id: {}, page_no: {}, page_size: {}'.format(node_no, report_id, page_no, page_size))

    data = CReportService.query_task_processing(node_no, report_id, page_no, page_size)
    logger.info('查询节点任务进度完成 - node_no: {}, 数据数量: {}'.format(node_no, len(data) if data else 0))

    return jsonify({
        'status': 0,
        'msg': 'report processing for {} is succ'.format(node_no),
        'data': data
    })