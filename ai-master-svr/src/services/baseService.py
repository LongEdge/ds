class CBaseService:
    @staticmethod
    def init_res():
        """
        service层统一构造
        """
        return {
            'msg': '',
            'data': None,
            'code': -1  # -1异常, 0正常
        }