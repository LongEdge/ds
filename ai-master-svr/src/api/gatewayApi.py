from flask import Blueprint, request
from src.services.gatewayService import CGatewayService
from src.utils.SysLogger import CSysLogger
from src.utils.response import CResponse


gatewayBp = Blueprint('gatewayApi', __name__)
logger = CSysLogger('gatewayApi')

gatewayService = CGatewayService()

@gatewayBp.route('/ai-master-svr/register-gateway-capability/', methods=['POST'])
def register_gateway_capability():
    """
    注册网关能力
    能力发布状态, -1=待发布, 0=未发布, 1=已发布
    ---
    tags:
        -   网关能力模块
    parameters:
        -   name: capability_id
            in: formData
            type: string
            required: true
            description: 能力id
        -   name: capability_name
            in: formData
            type: string
            required: true
            description: 能力名称
        -   name: capability_version
            in: formData
            type: string
            required: true
            description: 能力版本
        -   name: capability_desc
            in: formData
            type: string
            required: false
            description: 能力描述
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    params = request.form.to_dict()
    logger.info("/ai-master-svr/register-gateway-capability/ - {}".format(params))
    capability_id = params.get("capability_id", None)
    capability_name = params.get("capability_name", None)
    capability_version = params.get("capability_version", None)
    capability_desc = params.get("capability_desc", None)

    insert_flag = gatewayService.register_gateway_capability(capability_id,
                                                    capability_name,
                                                    capability_version,
                                                    capability_desc
                                                    )
    if 0 == insert_flag:
        return CResponse.succ(msg='网关能力注册成功',
                                data=None)
    else:
        return CResponse.succ(msg='网关能力注册失败',
                                data=None)


@gatewayBp.route('/ai-master-svr/query-gateway-capability/', methods=['POST'])
def query_gateway_capability():
    """
    查询网关所有的能力
    ---
    tags:
        -   网关能力模块
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
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    params = request.form.to_dict()
    logger.info("/ai-master-svr/query-gateway-capability/ - {}".format(params))
    page_no = int(params.get("page_no", 1))
    page_size = int(params.get("page_size", 50))

    data = gatewayService.query_gateway_capability(page_size, 
                                                page_no)
    return CResponse.succ(msg='查询成功',
                        data=data)


@gatewayBp.route('/ai-master-svr/delete-gateway-capability/', methods=['POST'])
def delete_gateway_capability():
    """
    删除网关能力
    ---
    tags:
        -   网关能力模块
    parameters:
        -   name: capability_id
            in: formData
            type: string
            required: true
            description: 能力id
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    params = request.form.to_dict()
    logger.info("/ai-master-svr/delete-gateway-capability/ - {}".format(params))
    capability_id = params.get("capability_id", None)
    delete_flag = gatewayService.delete_gateway_capability(capability_id)
    if delete_flag == 0:
        return CResponse.succ(msg='删除成功',
                            data=None)
    else:
        return CResponse.succ(msg='删除成功',
                            data=None)



@gatewayBp.route('/ai-master-svr/update-gateway-capability/', methods=['POST'])
def update_gateway_capability():
    """
    更新网关能力
    ---
    tags:
        -   网关能力模块
    parameters:
        -   name: capability_id
            in: formData
            type: string
            required: true
            description: 能力id
        -   name: capability_desc
            in: formData
            type: string
            required: true
            description: 能力描述
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    params = request.form.to_dict()
    logger.info("/ai-master-svr/update-gateway-capability/ - {}".format(params))
    capability_id = params.get("capability_id", None)
    capability_desc = params.get("capability_desc", None)
    update_flag = gatewayService.update_gateway_capability(capability_id, 
                                                           capability_desc)
    if update_flag == 0:
        return CResponse.succ(msg='更新成功',
                            data=None)
    else:
        return CResponse.succ(msg='更新失败',
                            data=None)
    

@gatewayBp.route('/ai-master-svr/update-gateway-capability-status/', methods=['POST'])
def update_gateway_capability_status():
    """
    更新网关能力状态
    能力发布状态更新, -1=待发布, 0=未发布, 1=已发布
    ---
    tags:
        -   网关能力模块
    parameters:
        -   name: capability_id
            in: formData
            type: string
            required: true
            description: 能力id
        -   name: capability_status
            in: formData
            type: string
            required: true
            description: 能力状态
    responses:
        500:
            description: 失败返回
        200:
            description: 成功返回
        406:
            description: 参数名异常  
    """
    params = request.form.to_dict()
    logger.info("/ai-master-svr/update-gateway-capability-status/ - {}".format(params))
    capability_id = params.get("capability_id", None)
    capability_status = params.get("capability_status", None)
    update_flag = gatewayService.update_gateway_capability_status(capability_id, 
                                                           capability_status)
    if update_flag == 0:
        return CResponse.succ(msg='更新成功',
                            data=None)
    else:
        return CResponse.succ(msg='更新失败',
                            data=None)
