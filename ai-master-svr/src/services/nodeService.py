from src.dao.sql import Sql
from src.dao.nodeDao import CNodeDao
from src.services.baseService import CBaseService
from src.utils.SysLogger import CSysLogger
from src.utils.errorEnum import CErrorEnum

logger = CSysLogger('CNodeService')


class CNodeService(CBaseService):
    def __init__(self):
        self.nodeDao = CNodeDao()


    @staticmethod
    def create_node(node_no, deal_type_no, deal_type_version, node_loc):
        logger.info('nodeService.create_node - node_no: {}, deal_type_no: {}, deal_type_version: {}, node_loc: {}'.format(node_no, deal_type_no, deal_type_version, node_loc))
        sql = Sql()
        insert_flag = sql.add_node(node_no, deal_type_no, deal_type_version, node_loc)
        if insert_flag == 0:
            logger.info('nodeService.create_node 成功 - node_no: {}'.format(node_no))
        else:
            logger.error('nodeService.create_node 失败 - node_no: {}, insert_flag: {}'.format(node_no, insert_flag))
        return insert_flag

    @staticmethod
    def remove_node(node_no):
        logger.info('nodeService.remove_node - node_no: {}'.format(node_no))
        sql = Sql()
        insert_flag = sql.remove_node(node_no)
        if insert_flag == 0:
            logger.info('nodeService.remove_node 成功 - node_no: {}'.format(node_no))
        else:
            logger.error('nodeService.remove_node 失败 - node_no: {}, insert_flag: {}'.format(node_no, insert_flag))
        return insert_flag

    @staticmethod
    def update_node(node_no, deal_type_no, deal_type_version, node_loc):
        logger.info('nodeService.update_node - node_no: {}, deal_type_no: {}, deal_type_version: {}, node_loc: {}'.format(node_no, deal_type_no, deal_type_version, node_loc))
        sql = Sql()
        insert_flag = sql.update_node(node_no, deal_type_no, deal_type_version, node_loc)
        if insert_flag == 0:
            logger.info('nodeService.update_node 成功 - node_no: {}'.format(node_no))
        else:
            logger.error('nodeService.update_node 失败 - node_no: {}, insert_flag: {}'.format(node_no, insert_flag))
        return insert_flag
    

    def bind_node_capability(self, capability_id, node_no: str) -> dict:
        res_dict = self.init_res()
        # 1. 查询capability_id是否存在
        is_exist_capability = self.nodeDao.exists_node_capabiltiy(capability_id)
        if is_exist_capability != 0:
            res_dict['code'] = CErrorEnum.CAPABILITY_NOT_FOUND.code
            res_dict['msg'] = CErrorEnum.CAPABILITY_NOT_FOUND.msg
            return res_dict
        
        # 2. 查询node_no是否存在
        is_exist_nodeno = self.nodeDao.exists_node(node_no)
        if is_exist_nodeno != 0:
            res_dict['code'] = CErrorEnum.NODE_NOT_FOUND.code
            res_dict['msg'] = CErrorEnum.NODE_NOT_FOUND.msg
            return res_dict

        # 3. 尝试绑定
        bind_flag, msg = self.nodeDao.bind_node_capability(capability_id, node_no)
        res_dict['code'] = bind_flag
        res_dict['msg'] = msg

        return res_dict

    def register_node_capability(self, capability_id, node_no):
        res_dict = self.init_res()

        # 1. 如果能力id有误, 就拒绝插入
        exists_node_capability_flag = self.nodeDao.exists_node_capabiltiy(capability_id)
        logger.info("exists_node_capability_flag: {}".format(exists_node_capability_flag))
        if -1 == exists_node_capability_flag:
            res_dict['code'] = CErrorEnum.CAPABILITY_NOT_FOUND.code
            res_dict['msg'] = '注册节点能力失败, 注册的能力{}不存在, 请联系管理员'.format(capability_id)
            return res_dict


        # 2. 如果node_info表不存在, 就拒绝插入表
        exists_node_flag = self.nodeDao.exists_node(node_no)
        logger.info("exists_node_flag: {}".format(exists_node_flag))
        if -1 == exists_node_flag:
            res_dict['code'] = CErrorEnum.NODE_NOT_FOUND.code
            res_dict['msg'] = '注册节点能力失败, {}节点不存在, 请联系管理员'.format(node_no)
            return res_dict

        insert_flag, msg = self.nodeDao.register_node_capability(capability_id, node_no)
        if 0 == insert_flag:
            logger.info("注册成功")
            res_dict['code'] = 0
            res_dict['msg'] = '{}注册节点能力成功'.format(node_no)
        else:
            res_dict['code'] = CErrorEnum.NODE_ALREADY_EXISTS.code
            res_dict['msg'] = CErrorEnum.NODE_ALREADY_EXISTS.msg

        return res_dict


    def query_nodes_by_capability(self, capability_id, page_no, page_size):
        res_dict = self.init_res()
        query_data = self.nodeDao.query_nodes_by_capability(capability_id, page_no, page_size)
        res_dict['code'] = 0
        res_dict['msg'] = "查询{}能力下的所有节点成功".format(capability_id)
        res_dict['data'] = query_data
        return res_dict
    
    def unbind_node_capability(self, capability_id, node_no):
        res_dict = self.init_res()
        if node_no == None or capability_id == None:
            res_dict['code'] = CErrorEnum.PARAM_ERROR.code
            res_dict['msg'] = CErrorEnum.PARAM_ERROR.msg
            return res_dict
        
        # 查询节点能力
        try:
            unbind_flag = self.nodeDao.unbind_node_capability(node_no, capability_id)
            if unbind_flag == 0:
                logger.info('nodeService.unbind_node_capability 成功 - node_no: {}'.format(node_no))
                res_dict['code'] = 0
                res_dict['msg'] = 'unbind node {} is succ'.format(node_no)
            else:
                logger.error('nodeService.unbind_node_capability 失败 - node_no: {}, unbind_flag: {}'.format(node_no, unbind_flag))
        except Exception as e:
                res_dict['msg'] = 'unbind node {} is failed - [{}]'.format(node_no, e)
                logger.error('nodeService.unbind_node_capability 失败 - node_no: {}, unbind_flag: {}'.format(node_no, unbind_flag))

        return res_dict
        

    def update_node_capability(self, node_cb_id, node_no, node_bind_status):

        res_dict = self.init_res()
        if node_cb_id == None:
            res_dict['msg'] = 'node_cb_id is {}'.format(node_cb_id)
            return res_dict
        
        try:
            unbind_flag = self.nodeDao.update_node_capability(node_cb_id, node_no, node_bind_status)
            if unbind_flag == 0:
                logger.info('nodeService.update_node_capability 成功 - node_no: {}'.format(node_no))
                res_dict['msg'] = 'nodeService.update_node_capability 成功 - node_no: {}'.format(node_no)
            else:
                logger.error('nodeService.update_node_capability 失败 - node_no: {}, unbind_flag: {}'.format(node_no, unbind_flag))
                res_dict['msg'] = 'nodeService.update_node_capability 失败 - node_no: {}, unbind_flag: {}'.format(node_no, unbind_flag)

        except Exception as e:
                logger.error('nodeService.update_node_capability 失败, node: {} - {}'.format(node_no, e))
                res_dict['msg'] = 'nodeService.update_node_capability 失败, node: {} - {}'.format(node_no, e)

            
        return res_dict

    

