import json
import os
import sys
import yaml
import shutil
from .conn.Storages import StoragesMng
from .process.proc_comm import CProcessorComm
from .process.proc_api_datamng import CDataMng
from .process.proc_api_wrinkle import CProcessorAPIWrinkle
from .process.proc_api_imgclassify import CProcessorAPIImgClassify

class CProcessor(object):
    '''
    This is a Processor class that takes in a OSS and a resultSender
    and handles the sequence. Basically, a manager.
    '''

    def __init__(self, node_cfg, progress_callback):
        super(CProcessor, self).__init__()
        # 节点配置
        self.node_cfg = node_cfg
        self.progress_callback = progress_callback
        # 进行配置文件的处理
        self.node_cfg['local_data_path'] = os.path.join(self.node_cfg['tmp_data'], self.node_cfg['local_data_path'])
        self.node_cfg['local_model_path'] = os.path.join(self.node_cfg['persist_data'],self.node_cfg['local_model_path'])

        self.storage_cloud = StoragesMng(self.node_cfg)
        self.proc_comm = CProcessorComm(node_cfg,self.storage_cloud)

        self.api_wrinkle = CProcessorAPIWrinkle(self.proc_comm)
        self.api_imgclassify = CProcessorAPIImgClassify(self.proc_comm)
        self.api_datamng = CDataMng(self.proc_comm)

        if os.path.exists(self.node_cfg['local_data_path']):
            shutil.rmtree(self.node_cfg['local_data_path'])
        os.makedirs(self.node_cfg['local_data_path'])

    def ProcessTask(self, param):
        pass
    
    # 工具的api接口的总控制函数
    def ProcessAPI(self,apitype,apimodule,apiclass, apimethod, param):
        if      apitype == 'api':
            if      apimodule == 'wrinkle': # 皱纹标签
                if      apiclass ==          'filemng': # 文件管理
                    if      apimethod ==                    'listimgdirs': # 列出图像目录
                        res = self.api_wrinkle.getImgDirLists(param)
                    elif    apimethod ==                   'listimgfiles': # 列出图像文件  
                        res = self.api_wrinkle.getImgFileLists(param)
                    elif    apimethod ==                   'getwrinkletype': # 获取图像类型：法令纹、抬头纹、泪沟等
                        res = self.api_wrinkle.getWrinkleType()
                    elif    apimethod ==                   'cacheimgbase64': # 获取图像内容
                        res = self.api_wrinkle.getCacheImgBase64FromMinio(param)
                    elif    apimethod ==                   'getimgbase64': # 缓存图像内容
                        res = self.api_wrinkle.getImgBase64FromMinio(param)
                    elif    apimethod ==                   'getmaskbase64': # 获取mask图像内容
                        res = self.api_wrinkle.getMaskBase64FromMinio(param)
                    elif    apimethod ==                   'saveimgbase64': # 保存图像内容
                        res = self.api_wrinkle.saveImgBase64ToMinio(param)
                    elif      apimethod ==                   'deleteimg': # 删除图像内容
                        res = self.api_wrinkle.deleteImgFromMinio(param)
                    elif      apimethod ==                   'deletepngcache': # 删除png缓存
                        res = self.api_wrinkle.deletePngCache(param)
                elif    apiclass ==          'label': # 标签管理
                    if      apimethod ==                    'index': # 首页
                        res = self.api_wrinkle.htmlWrinkleLabel(param,'photoRemark.html')
                    elif      apimethod ==                    'localindex': # 首页
                        res = self.api_wrinkle.htmlWrinkleLabel(param,'photoRemark_local.html')
            elif    apimodule == 'imgclassify': # 图像分类
                if      apiclass ==          'filemng': # 文件管理
                    if      apimethod ==                    'listimgdirs': # 列出图像目录
                        res=self.api_imgclassify.getImgDirLists(param)
                    elif    apimethod ==                    'getimgbase64': # 获取图像base64
                        res=self.api_imgclassify.getImgBase64(param)
                    elif    apimethod ==                    'listimgfiles': # 列出图像文件
                        res=self.api_imgclassify.getImgFileLists(param)
                    elif    apimethod ==                    'getworkcount':
                        res=self.api_imgclassify.getWorkCount(param)    
                elif    apiclass ==          'label': # 标签管理
                    if      apimethod ==                    'getimglabel': # 获取标签
                        res=self.api_imgclassify.getImgLabel(param)
                    elif    apimethod ==                    'updateimglabel': # 更新图像分类标签
                        res=self.api_imgclassify.updateImgLabel(param)
                    elif    apimethod ==                    'addclassify': # 添加分类
                        res=self.api_imgclassify.addClassify(param)
                    elif    apimethod ==                    'getclassify': # 获取分类
                        res=self.api_imgclassify.getClassify(param)
                    elif    apimethod ==                    'getnewtask': # 获取新任务
                        res=self.api_imgclassify.getNewTask(param)
                    elif    apimethod ==                    'getlasttask': # 获取上一个任务
                        res=self.api_imgclassify.getLastTask(param)
                    elif    apimethod ==                    'getnexttask': # 获取下一个任务
                        res=self.api_imgclassify.getNextTask(param)
                elif    apiclass ==             'predict':#预测
                    if      apimethod ==                    'getpredgroup': # 获取预测组的信息
                        res=self.api_imgclassify.getPredGroup(param)
                    elif      apimethod ==                    'predGroup':
                        res=self.api_imgclassify.predGroup(param)
                    elif    apimethod ==                    'correctCode': # 修正分类
                        res=self.api_imgclassify.correctCode(param)    


            elif    apimodule == 'comm': # 图像通用
                if      apiclass ==          'img'  :
                    if      apimethod ==                   'getimgbase64': # 保存图像内容
                        res = self.api_datamng.getImgbase64FromMinio(param)
                    elif      apimethod ==                   'create-png-base64': # 保存图像内容
                        res = self.api_wrinkle.createPngBase64FromMinio(param)
        elif    apitype == 'html':
            if      apimodule == 'label': # 打标签的页面
                if      apiclass ==          'wrinkle': # 皱纹
                    if      apimethod ==                    'index': # 首页
                        res = self.api_wrinkle.htmlWrinkleLabel(param, 'photoRemark.html')
                    elif     apimethod ==                    'test': # 首页
                        res = self.api_wrinkle.htmlWrinkleTest(param)
                elif      apiclass ==          'datamng': # 皱纹
                    if      apimethod ==                    'previewimg': # 单独的图像预览页面
                        res = self.api_datamng.htmlPreviewImg(param)   
                elif      apiclass ==          'imgclassify': # 图像分类
                    if    apimethod==                        'remark': # 图像分类
                        res = self.api_imgclassify.getHtmlClassify(param,'photoClassify.html') 
                    if      apimethod ==                    'loginRemark': # 首页
                        res = self.api_imgclassify.getHtmlClassify(param,'login.html')
        return res
