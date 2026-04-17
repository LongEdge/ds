from src.dao.gatewayDao import CGatewayDao
from src.services.baseService import CBaseService
from src.utils.SysLogger import CSysLogger
from src.utils.errorEnum import CErrorEnum
logger = CSysLogger('gatewayService')


class CGatewayService(CBaseService):
    def __init__(self):
        self.gatewayDao = CGatewayDao()

    def register_gateway_capability(self, 
                                    capability_id: str,
                                    capability_name: str,
                                    capability_version: str,
                                    capability_desc: str):

        insert_flag = self.gatewayDao.register_gateway_capability(capability_id,
                                                    capability_name,
                                                    capability_version,
                                                    capability_desc)
        return insert_flag
            
    def query_gateway_capability(self, page_size, page_no):
        return self.gatewayDao.query_gateway_capability(page_size, page_no)

    
    def delete_gateway_capability(self, capability_id):
        delete_flag = self.gatewayDao.delete_gateway_capability(capability_id)
        return delete_flag
    
    def update_gateway_capability(self, capability_id, capability_desc):
        
        update_flag = self.gatewayDao.update_gateway_capability(capability_id, capability_desc)
        return update_flag
    
    def update_gateway_capability_status(self, capability_id, capability_status):
        
        update_flag = self.gatewayDao.update_gateway_capability_status(capability_id, capability_status)
        return update_flag
