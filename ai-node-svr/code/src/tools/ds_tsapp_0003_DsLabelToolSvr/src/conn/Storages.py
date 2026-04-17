import os
import sys
from os import mkdir
from ..util.log import setup_custom_logger
from ..conn.Url import UrlRequest
from ..conn.OSS import OSSManager
from ..conn.Minio import CMinioManager

logger = setup_custom_logger('OSS')

# 维护多个存储连接管理
class StoragesMng(object):

    def __init__(self, node_cfg):
        plt_url = node_cfg['plt_url']
        # 云存储对象，格式:
        # {
        #     'conn_name':'cskin',
        #     'conn_type':'oss/azure/minio',
        #     'storage_obj':[StorageMngObj]
        # }
        self.cloud_storage_pool = []
        # urlrequest 对象
        self.urlrequest = UrlRequest(node_cfg)
    
    # 从云存储下载图像
    def downloadFiles(self,dconn_name, download_files):
        """
        @param conn_name 连接的云存储名称
        @param download_files =  
                    [
                         {
                             'localfile':'leftwhite.jpg',
                             'remotefile':'/processedImg/leftwhite.jpg'
                         },
                         {
                             'localfile':'rightwhite.jpg',
                             'remotefile':'/processedImg/rightwhite.jpg'
                         }
                     ] 
        其他说明：下载文件的位置：self.local_file_path，在toolconfig.yml规定，
        """
        #根据名称获取连接信息
        cloud_obj = self.priv_get_storage_byname(dconn_name)

        # 文件下载
        for fileitem in download_files:
            remote_path = fileitem['remotefile']
            local_path =  fileitem['localfile']
            cloud_obj["conn_obj"].downloadFile(remote_path, local_path)

    def downloadFile(self,dconn_name, remote_file,local_file):
        #根据名称获取连接信息
        cloud_obj = self.priv_get_storage_byname(dconn_name)
        cloud_obj["conn_obj"].downloadFile(remote_file, local_file)
    
    # 检测文件是否存在
    def checkFileExist(self,conn_name,file):
        """
        @param file :指定的文件
        @return 
        {
            'exist':True, #文件是否存在
        }
        """
        cloud_obj = self.priv_get_storage_byname(conn_name)
        result = cloud_obj["conn_obj"].checkFileExist(file)
        return result
        
    # 从服务器上传文件到云存储
    def uploadFiles(self, dconn_name, upload_files):
        """
        @param conn_name 连接的云存储名称
        @param uploadfiles =  
                    [
                        {
                            'localfile':'leftwhite.jpg',
                            'remotefile':'/processedImg/leftwhite.jpg'
                        },
                        {
                            'localfile':'rightwhite.jpg',
                            'remotefile':'/processedImg/rightwhite.jpg'
                        }
                    ] 
        其他说明：下载文件的位置：self.local_file_path，在toolconfig.yml规定
        """
        #根据名称获取连接信息
        cloud_obj = self.priv_get_storage_byname(dconn_name)

        # 文件上传
        for fileitem in upload_files:
            remote_path = fileitem['remotefile']
            local_path =  fileitem['localfile']
            cloud_obj["conn_obj"].uploadFile(remote_path, local_path)

    def uploadFile(self, dconn_name, local_file,remote_file):
        #根据名称获取连接信息
        cloud_obj = self.priv_get_storage_byname(dconn_name)
        cloud_obj["conn_obj"].uploadFile(remote_file, local_file)

    def deleteFile(self, dconn_name, remote_file):
        #根据名称获取连接信息
        cloud_obj = self.priv_get_storage_byname(dconn_name)
        cloud_obj["conn_obj"].deleteFile(remote_file) 
    
    # 获取文件夹/文件的数量
    def getFileNum(self,conn_name,dir):
        """
        @param dir :指定的目录
        @return 
        {
            'dnum':3434, #目录的数量
            'fnum':33 # 文件的数量
        }
        """
        cloud_obj = self.priv_get_storage_byname(conn_name)
        result = cloud_obj["conn_obj"].getFileNum(dir)
        return result

    
    def listFiles(self,conn_name,dir):
        """
        @param dir: 目标目录, 如： AIDataManage / CskinAlgoCollect / FaceDectation
        @return 
        [{
            ftype:D/F,
            name:'xxxx.jpg'
        }]
        返回列表实现文件名排序
        """
        cloud_obj = self.priv_get_storage_byname(conn_name)
        result = cloud_obj["conn_obj"].listFiles(dir)
        return result

    # 在同一个云存储中移动目录
    def moveDirectory(self,conn_name,src_dir,dst_dir):
        """
        conn_name: 云存储名称(含bucketname信息)
        src_dir :源目录 DsDataCollection / CSKIN人脸 / wrinkle
        dst_dir :目标目录，如：DsDataCollection / CSKIN人脸2 / wrinkle
        """
        cloud_obj = self.priv_get_storage_byname(conn_name)
        cloud_obj["conn_obj"].moveDirectory(src_dir,dst_dir)

    # 在同一个bucket中移动文件
    def moveFile(self,conn_name, src_file, dst_file):
        """
        conn_name: 云存储名称(含bucketname信息)
        src_file :源文件 DsDataCollection / CSKIN人脸 / wrinkle/xxx.jpg
        dst_file :目标文件，如：DsDataCollection / CSKIN人脸2 / wrinkle/xxx.jpg
        """
        cloud_obj = self.priv_get_storage_byname(conn_name)
        cloud_obj["conn_obj"].moveFile(src_file,dst_file)

    
    # 获取存储对象
    def priv_get_storage_byname(self,conn_name):
        """
        @return 
        {
            'conn_name':conn_name,
            'conn_type':storageinfo['storage_type'],
            'bucket_name':storageinfo['bucket_name'],
            'storage_obj':storageinfo['storage_obj']
        }
        """
        #先查找该存储连接是否已经存在
        for conn_obj in self.cloud_storage_pool:
            if (conn_obj['conn_name'] == conn_name):
                return conn_obj
        #如果没有找到该对象
        conn_obj = None
        storageinfo = self.urlrequest.get_storage_info_byname(conn_name)
        
        if storageinfo != None or storageinfo == {}:
            if "oss" == storageinfo['STORAGE_TYPE']:
                conn_obj = {
                    "conn_name":conn_name,
                    'conn_type':storageinfo['STORAGE_TYPE'], #oss/minio/azure
                    'bucket_name':storageinfo['BUCKET_NAME'],
                    "conn_obj": OSSManager(
                        storageinfo['ALIYUN_ACCESS_KEY_ID'], 
                        storageinfo['ALIYUN_ACCESS_KEY_SECRET'], 
                        storageinfo['BUCKET_NAME'], 
                        # storageinfo['ALIYUN_EXTERNAL_END_POINT'] # 外网能用
                        storageinfo['ALIYUN_INTERNAL_END_POINT'] # 只在阿里内网能用
                    )
                }

                self.cloud_storage_pool.append(conn_obj)
            elif "minio" == storageinfo['STORAGE_TYPE']:
                conn_obj = {
                    "conn_name":conn_name,
                    "conn_type":storageinfo['STORAGE_TYPE'],
                    'bucket_name':storageinfo['BUCKET_NAME'],
                    "conn_obj": CMinioManager(
                        storageinfo['ACCESS_KEY'],
                        storageinfo['SECRET_KEY'],
                        storageinfo['BUCKET_NAME'],
                        storageinfo['END_POINT']
                    )
                }
                if (conn_obj != None):
                    self.cloud_storage_pool.append(conn_obj)
        return conn_obj