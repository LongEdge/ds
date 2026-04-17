from flask import Blueprint, request, jsonify
from src.services.nodeService import CNodeService
from src.utils.SysLogger import CSysLogger
from src.utils.response import CResponse


nodeBp = Blueprint('nodeApi', __name__)
logger = CSysLogger('nodeApi')

nodeService = CNodeService()

@nodeBp.route('/ai-master-svr/register-node/', methods=['POST'])
def create_node():
    """
    master创建节点
    ---
    tags:
        -   节点模块
    parameters:
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 注册的节点编号
        -   name: deal_type_no
            in: formData
            type: string
            required: true
            description: 工具号(平台申请获得)
        -   name: deal_type_version
            in: formData
            type: string
            required: true
            description: 处理工具版本
        -   name: node_loc
            in: formData
            type: string
            required: true
            description: 节点部署的地理位置
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
    logger.info('收到创建节点请求')
    res_dict = request.form.to_dict()
    if 1 != 1:
        client_key = res_dict['client_key']
    node_no = res_dict['node_no']
    deal_type_no = res_dict['deal_type_no']
    deal_type_version = res_dict['deal_type_version']
    node_loc = res_dict['node_loc']

    logger.info('创建节点参数 - node_no: {}, deal_type_no: {}, deal_type_version: {}, node_loc: {}'.format(node_no, deal_type_no, deal_type_version, node_loc))

    isPass = True
    insert_flag = -1
    if isPass:
        insert_flag = CNodeService.create_node(node_no, deal_type_no, deal_type_version, node_loc)
        if insert_flag == 0:
            logger.info('创建节点成功 - node_no: {}'.format(node_no))
        else:
            logger.error('创建节点失败 - node_no: {}, insert_flag: {}'.format(node_no, insert_flag))
        
        return jsonify({
            'status': 0,
            'msg': 'create node {} is succ'.format(node_no),
            'data': {
                "insert_flag": insert_flag,
                "plt_url": ""
            }
        })
    else:
        logger.error('analysis api key error.')
        return jsonify({
            'status': -1,
            'msg': 'create node {} is failed, key is error'.format(node_no),
            'data': {
                "insert_flag": insert_flag,
                "plt_url": ""
            }
        })

@nodeBp.route('/ai-master-svr/del-node/', methods=['POST'])
def remove_node():
    """
    master删除节点
    ---
    tags:
        -   节点模块
    parameters:
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 注册的节点编号
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
    logger.info('收到删除节点请求')
    res_dict = request.form.to_dict()
    if 1 != 1:
        client_key = res_dict['clientKey']
    node_no = res_dict['node_no']
    
    logger.info('删除节点参数 - node_no: {}'.format(node_no))

    isPass = True
    insert_flag = -1
    if isPass:
        insert_flag = CNodeService.remove_node(node_no)
        if insert_flag == 0:
            logger.info('删除节点成功 - node_no: {}'.format(node_no))
        else:
            logger.error('删除节点失败 - node_no: {}, insert_flag: {}'.format(node_no, insert_flag))
        
        return jsonify({
            'status': 0,
            'msg': 'del node {} is succ'.format(node_no),
            'data': insert_flag
        })
    else:
        logger.error('analysis api key error.')
        return jsonify({
            'status': -1,
            'msg': 'del node {} is failed, key is error'.format(node_no),
            'data': insert_flag
        })


@nodeBp.route('/ai-master-svr/update-node/', methods=['POST'])
def update_node():
    """
    master更新节点
    ---
    tags:
        -   节点模块
    parameters:
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 注册的节点编号
        -   name: deal_type_no
            in: formData
            type: string
            required: false
            description: 工具号(平台申请获得)
        -   name: deal_type_version
            in: formData
            type: string
            required: false
            description: 处理工具版本
        -   name: node_loc
            in: formData
            type: string
            required: false
            description: 节点部署的地理位置
        -   name: node_sub_info
            in: formData
            type: string
            required: false
            description: 节点下级信息
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    logger.info('收到更新节点请求')
    res_dict = request.form.to_dict()
    node_no = res_dict.get('node_no', None)
    deal_type_no = res_dict.get('deal_type_no', None)
    deal_type_version = res_dict.get('deal_type_version', None)
    node_loc = res_dict.get('node_loc', None)
    node_sub_info = res_dict.get('node_sub_info', None)

    logger.info('更新节点参数 - node_no: {}, deal_type_no: {}, deal_type_version: {}, node_loc: {}'.format(node_no, deal_type_no, deal_type_version, node_loc))

    isPass = True
    insert_flag = -1
    if isPass:
        insert_flag = CNodeService.update_node(node_no, deal_type_no, deal_type_version, node_loc, node_sub_info)
        if insert_flag == 0:
            logger.info('更新节点成功 - node_no: {}'.format(node_no))
        else:
            logger.error('更新节点失败 - node_no: {}, insert_flag: {}'.format(node_no, insert_flag))
        
        return jsonify({
            'status': insert_flag,
            'msg': 'update node {} is succ'.format(node_no),
            'data': None
        })
    else:
        logger.error('analysis api key error.')
        return jsonify({
            'status': insert_flag,
            'msg': 'update node {} is failed, key is error'.format(node_no),
            'data': None
        })
    
@nodeBp.route('/ai-master-svr/bind-node-capability/', methods=['POST'])
def bind_node_capability():
    """
    双向绑定节点
    ---
    tags:
        -   节点能力模块
    parameters:
        -   name: capability_id
            in: formData
            type: string
            required: true
            description: 能力id
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 注册的节点编号
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    params = request.form.to_dict()
    logger.info('/ai-master-svr/bind-node-capability/ - {}'.format(params))
    capability_id = params.get("capability_id", None)
    node_no = params.get("node_no", None)

    res_dict = nodeService.bind_node_capability(capability_id, node_no)
    return CResponse.make(res_dict)



@nodeBp.route('/ai-master-svr/register-node-capability/', methods=['POST'])
def register_node_capability():
    """
    注册节点能力(比如可以皱纹预测、五官预测)
    状态: -1待测试, 0不可用, 1可用
    ---
    tags:
        -   节点能力模块
    parameters:
        -   name: capability_id
            in: formData
            type: string
            required: true
            description: 节点能力的编号
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 注册的节点编号
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    params = request.form.to_dict()
    logger.info('/ai-master-svr/register-node-capability/ - {}'.format(params))
    capability_id = params.get("capability_id", None)
    node_no = params.get("node_no", None)
    res_dict = nodeService.register_node_capability(capability_id, node_no)
    logger.info(res_dict)
    return CResponse.make(res_dict)



@nodeBp.route('/ai-master-svr/query-nodes-by-capability/', methods=['POST'])
def query_nodes_by_capability():
    """
    根据对应版本的能力查询所有的节点
    ---
    tags:
        -   节点能力模块
    parameters:
        -   name: capability_id
            in: formData
            type: string
            required: true
            description: 能力id
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
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    params = request.form.to_dict()
    logger.info('/ai-master-svr/query-nodes-by-capability/ - {}'.format(params))
    capability_id = params.get("capability_id", None)
    page_no = params.get("page_no", 1)
    page_size = params.get("page_size", 50)

    res_dict = nodeService.query_nodes_by_capability(capability_id, page_no, page_size)
    return CResponse.make(res_dict)



@nodeBp.route('/ai-master-svr/unbind-node-capability/', methods=['POST'])
def unbind_node_capability():
    """
    删除能力下的某个节点
    ---
    tags:
        -   节点能力模块
    parameters:
        -   name: capability_id
            in: formData
            type: string
            required: true
            description: 能力id
        -   name: node_no
            in: formData
            type: string
            required: true
            description: 节点id
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    params = request.form.to_dict()
    logger.info('/ai-master-svr/unbind-node-capability/ - {}'.format(params))
    capability_id = params.get("capability_id", None)
    node_no = params.get("node_no", None)

    res_dict = nodeService.unbind_node_capability(capability_id, node_no)
    return CResponse.make(res_dict)



@nodeBp.route('/ai-master-svr/update-node-capability/', methods=['POST'])
def update_node_capability():
    """
    更新能力下的某个节点的信息
    ---
    tags:
        -   节点能力模块
    parameters:
        -   name: node_cb_id
            in: formData
            type: string
            required: true
            description: 节点能力唯一id
        -   name: node_no
            in: formData
            type: string
            required: false
            description: 要修改的节点id
        -   name: node_bind_status
            in: formData
            type: string
            required: false
            description: 节点绑定的状态
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    params = request.form.to_dict()
    logger.info('/ai-master-svr/update-node-capability/ - {}'.format(params))
    node_cb_id = params.get("node_cb_id", None)
    node_no = params.get("node_no", None)
    node_bind_status = params.get("node_bind_status", None)

    res_dict = nodeService.update_node_capability(node_cb_id, node_no, node_bind_status)
    return CResponse.make(res_dict)
