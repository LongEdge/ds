from flask import jsonify
from typing import Any, Optional

class CResponse:
    def __init__(self, status: int = 0, msg: str = '', data: Optional[Any] = None):
        self.status = status
        self.msg = msg
        self.data = data

    def _to_dict(self):
        # 注意：在 Flask 中通常直接返回这个结果
        return jsonify({
            'status': self.status,
            'msg': self.msg,
            'data': self.data
        })

    @classmethod
    def succ(cls, data: Any = None, msg: str = 'success'):
        return cls(status=0, msg=msg, data=data)._to_dict()

    @classmethod
    def failed(cls, status: int = 1, msg: str = 'failed', data: Any = None):
        return cls(status=status, msg=msg, data=data)._to_dict()

    @classmethod
    def make(cls, res_dict: dict):
        """
        自适应判断：传入 Service 层返回的字典
        res_dict 格式预期: {'code': 0, 'msg': '...', 'data': ...}
        """
        code = res_dict.get('code', -1) # 取不到 code 默认为失败
        msg = res_dict.get('msg', '')
        data = res_dict.get('data', None)

        if code == 0:
            return cls.succ(data=data, msg=msg)
        
        # 如果 code 不是 0，则走失败逻辑
        return cls.failed(status=code, msg=msg, data=data)