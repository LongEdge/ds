from flask import Blueprint, request, jsonify
from src.services.monitorService import CMonitorService
from src.utils.SysLogger import CSysLogger

monitorBp = Blueprint('monitorApi', __name__)
logger = CSysLogger('monitorApi')


@monitorBp.route('/ai-master-svr/get-master-live/', methods=['POST'])
def get_master_live():
    """
    master服务连通性
    ---
    tags:
        -   监控模块
    parameters:
        -   name: master_ip
            in: formData
            type: string  
            required: true
            description: master的ip
        -   name: master_no
            in: formData
            type: string
            required: true
            description: master的端口
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
    try:
        master_ip = res_dict['master_ip']
        master_no = res_dict['master_no']
        status, msg, delay_time = CMonitorService.get_master_live(master_ip, master_no)
        
        return jsonify({
            'status': status,
            'msg': msg,
            'data': {
                'delay_time': delay_time
            }
        })
    except Exception as e:
        return jsonify({
            'status': -1,
            'msg': 'connet to {}:{} is failed, e: {}'.format(master_ip, master_no, e),
            'data': {
                    'delay_time': -1
                }
        })


@monitorBp.route('/ai-master-svr/get-master-info/', methods=['POST'])
def get_master_info():
    """
    master服务基本信息
    ---
    tags:
        -   监控模块
    parameters:
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
    master_info = CMonitorService.get_master_info()
    if "" == master_info:
        return jsonify({
           'status': -1,
           'msg': 'failed',
           'data': master_info
        })
    else:
        return jsonify({
            'status': 0,
            'msg': 'succ',
            'data': master_info
        })


@monitorBp.route('/ai-master-svr/get-node-info-by-master/', methods=['POST'])
def get_node_info_by_master():
    """
    master获取所有的节点相关信息, 是否运行等
    ---
    tags:
        -   监控模块
    parameters:
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
    res_dict = request.form.to_dict()
    try:
        page_no = int(res_dict['page_no'])
        page_size = int(res_dict['page_size'])
    except Exception as e:
        page_no = 1
        page_size = 10


    data = CMonitorService.get_node_info_by_master(page_no, page_size)
    if 0 != len(data):
        return jsonify({
           'status': 0,
           'msg': 'succ',
           'data': data,
        })
    else:
        logger.info('获取节点信息 - 无数据')
        return jsonify({
            'status': -1,
            'msg': 'failed',
            'data': None,
        })