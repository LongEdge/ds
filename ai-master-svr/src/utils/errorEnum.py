from enum import Enum

class CErrorEnum(Enum):
    """
    业务状态码枚举
    格式: (code, default_msg)
    """
    SUCCESS = (0, "操作成功")
    PARAM_ERROR = (400, "参数为空")
    
    # 节点相关 (1000-1999)
    NODE_NOT_FOUND = (1001, "节点不存在")
    CAPABILITY_NOT_FOUND = (1002, "能力不存在")
    NODE_ALREADY_EXISTS = (1003, "节点已存在，请勿重复注册")
    
    # 系统相关
    DATABASE_ERROR = (5000, "数据库操作失败")
    UNKNOWN_ERROR = (-1, "未知错误")

    def __init__(self, code, msg):
        self.code = code
        self.msg = msg