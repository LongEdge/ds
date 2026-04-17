import time
from enum import Flag, auto
import uuid
import cv2
import os
import json
import numpy as np
from flask import request


class eStatusCode(Flag):
    SUCCESS = 0
    FAILED = -1
    PARAM_ERR = -2


class CProcessorComm():
    """
    Process 的一些公共功能
    """

    def __init__(self,node_cfg,storage_cloud):
        self.node_cfg = node_cfg
        self.storage_cloud = storage_cloud
        
    def getTokenFromURL(self):
        # 获取URL的head中的token
        token = request.headers.get('Authorization')
        if token == None:
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'token error')
        token = token.replace('Bearer ','')
        return token
    
    def getNodeCfg(self):
        return self.node_cfg
    
    def getStorageCloudObj(self):
        return self.storage_cloud
    

    def checkParamValid(self,param,paramlist):
        """
        @param param: 输入参数
        @param paramlist: 参数列表 ['id','users']
        @return:
        flag: True/False
        retjson: 错误的对象
        """
        msg = 'error param : '
        flag = True
        retjson = self.packRetJson(eStatusCode.SUCCESS)
        for paramitem in paramlist:
            if paramitem not in param:
                flag =  False
                msg  = msg + paramitem + ','
        if not flag:
            msg = msg.strip(',')
            retjson = self.packRetJson(eStatusCode.PARAM_ERR,[],msg)
        
        return flag,retjson

    # 打包返回json
    def packRetJson(self,code:eStatusCode,retdata=[],msg=''):

        """
        @param retdata: 返回数据
        @param code: 状态码,0=success -1=failed >0 错误码
        @param msg: 消息，如果没有输入，则根据eStatuCode的类型自动生成
        @return: json
        """
        # 把code从枚举类型eStatusCode转换成整数
        if msg == '':
            if code == eStatusCode.SUCCESS :
                msg = 'success'
            elif code == eStatusCode.FAILED:
                msg = 'failed'
            elif code == eStatusCode.PARAM_ERR:
                msg = 'param error'

        code = int(code.value)
        ret_json = {
            'code':code,
            'msg':msg,
            'data':retdata
        }
        return ret_json

    def submitLaeblRecord(self,param):
        """
        @param data_path: 数据路径
        @param client_id: 客户id
        @param tool: 工具名称
        @return: json
        """
        data_path=param['data_path']
        client_id=param['client_id']
        tool=param['tool']
        submit_time=time.time()

        data={
            'client_id':client_id,
            'tool':tool,
            'submit_time':submit_time,
            'data_path':data_path,
        }

        return self.packRetJson(eStatusCode.SUCCESS,data,'submit success')

    def getUserInfo(self,param):
        token=param['token']
        headers = {
        'Authorization': '',
        'clientid': 'e5cd7e4891bf95d1d19206ce24a7b32e'
                }
        headers['Authorization']='Bearer '+token

    def userLogin(self,param):
        """
        @param: username 用户名
        @param: password 密码
        """    

        #TODO:防止频繁请求
        pass

    def listDirs(self,param):
        pass



    #------- 任务编排 ----------

    def createNewTask(self,param):
        taskName=param['taskName']
        taskId = uuid.uuid5(uuid.NAMESPACE_DNS, taskName).hex
        token=self.getTokenFromURL()
        if token == None:
            return self.packRetJson(eStatusCode.FAILED,[],'No token in URL')
        

