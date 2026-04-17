import oss2
import yaml
import os
import sys
from minio import Minio
from minio.error import S3Error
from minio.commonconfig import CopySource
from ..util.log import setup_custom_logger

logger = setup_custom_logger('MINIO')


class CMinioManager(object):

    def __init__(self, access_key, secret_key, bucket_name, end_point):
        self.ACCESS_KEY = access_key
        self.SECRET_KEY = secret_key
        self.END_POINT = end_point
        self.bucket_name = bucket_name

        self.minio_client = Minio(
            end_point,
            access_key=access_key,
            secret_key=secret_key,
            secure=False
        )

    def downloadFile(self, remote_path, local_path):
        """
        从mino上下载文件
        """
        try:
            logger.info("Downloading {} to {}".format(
                remote_path,
                local_path
            ))
            self.minio_client.fget_object(self.bucket_name, remote_path, local_path)
            return 1
        except (oss2.exceptions.ClientError, oss2.exceptions.NoSuchKey) as e:
            logger.error(e)
            return 0

    def uploadFile(self, remote_path, local_path):
        """
        上传文件到OSS
        """
        try:
            logger.info("Uploading {} to {}".format(
                remote_path,
                local_path
            ))
            self.minio_client.fput_object(self.bucket_name, remote_path, local_path)
            return 1
        except (oss2.exceptions.ClientError, oss2.exceptions.NoSuchKey) as e:
            logger.error(e)
            return 0
    
    def deleteFile(self, remote_file):
        """
        删除文件
        """
        try:
            self.minio_client.remove_object(self.bucket_name, remote_file)
            return 1
        except (oss2.exceptions.ClientError, oss2.exceptions.NoSuchKey) as e:
            logger.error(e)
            return 0
            
    # 在同一个bucket中移动目录
    def moveDirectory(self, src_dir, dst_dir):
        """
        将 MinIO 中指定目录下的所有对象移动到另一个目录。

        :param src_dir :源目录 DsDataCollection / CSKIN人脸 / wrinkle
        :param dst_dir :目标目录，如：DsDataCollection / CSKIN人脸2 / wrinkle
        """
        try:
            # 确保源目录和目标目录以斜杠结尾
            if not src_dir.endswith('/'):
                src_dir += '/'
            if not dst_dir.endswith('/'):
                dst_dir += '/'
            
            # 列出源目录中的所有对象
            objects = self.minio_client.list_objects(self.bucket_name, prefix=src_dir, recursive=True)
            
            for obj in objects:
                # 获取对象的完整路径
                object_name = obj.object_name
                # 构造目标路径
                target_object_name = object_name.replace(src_dir, dst_dir, 1)
                
                # 复制对象到目标路径
                self.minio_client.copy_object(
                    self.bucket_name,
                    target_object_name,
                    f"{self.bucket_name}/{object_name}"
                )
                
                # 删除源对象
                self.minio_client.remove_object(self.bucket_name, object_name)
            
            print(f"成功将目录 {src_dir} 移动到 {dst_dir}")
        
        except S3Error as e:
            print(f"发生错误: {e}")
    
    # 在同一个bucket中移动文件
    def moveFile(self, src_file, dst_file):
        """
        将 MinIO 中指定文件移动到目标文件位置。

        :param src_file: 源文件路径
        :param dst_file: 目标文件路径
        """
        print(f"源文件路径: {src_file}, 目标文件路径: {dst_file}")
        try:
            # 创建 CopySource 对象
            copy_source = CopySource(self.bucket_name, src_file)
            
            # 复制文件到目标路径
            self.minio_client.copy_object(
                self.bucket_name,
                dst_file,
                copy_source
            )
            
            # 删除源文件
            self.minio_client.remove_object(self.bucket_name, src_file)
            
            print(f"成功将文件 {src_file} 移动到 {dst_file}")
        
        except S3Error as e:
            print(f"发生错误: {e}")
    
    def listFiles(self,dir):
        """
        @param dir: 目标目录, 如： AIDataManage / CskinAlgoCollect / FaceDectation
        @return 
        [{
            ftype:D/F,
            name:'xxxx.jpg'
        }]
        """
        result = []
    
        try:
            # 列出指定目录下的所有对象
            objects = self.minio_client.list_objects(self.bucket_name, prefix=dir, recursive=False)
            
            for obj in objects:
                entry_info = {
                    'ftype': 'D' if obj.is_dir else 'F',
                    'name': os.path.basename(os.path.dirname(obj.object_name)) if obj.is_dir else os.path.basename(obj.object_name)
                }
                result.append(entry_info)
            # 按照文件名称排序
            result.sort(key=lambda x: x['name'])
            
        except S3Error as e:
            print(f"发生错误: {e}")
        
        return result
    
    def getFileNum(self,dir):
        """
        @param dir :指定的目录
        @return 
        {
            'dnum':3434, #目录的数量
            'fnum':33 # 文件的数量
        }
        """
        result = {
            'dnum':0, #目录的数量
            'fnum':0 # 文件的数量
        }
        try:
            # 列出指定目录下的所有对象
            objects = self.minio_client.list_objects(self.bucket_name, prefix=dir.strip("/")+"/", recursive=False)
            
            for obj in objects:
                if obj.is_dir :
                    result['dnum'] = result['dnum'] + 1
                else :
                    result['fnum'] = result['fnum'] + 1
        except S3Error as e:
            print(f"发生错误: {e}")
        
        return result
        
    # 检测minio中某个指定的文件是否存在
    def checkFileExist(self,file):
        """
        @param file :指定的文件
        @return 
        {
            'exist':True, #文件是否存在
        }
        """
        result = {
            'exist':False, #文件是否存在
        }
        try:
            # 返回文件的路径（不含文件名称)
            file_dir = os.path.dirname(file)
            # 列出指定目录下的所有对象
            objects = self.minio_client.list_objects(self.bucket_name, prefix=file_dir.strip("/")+"/", recursive=False)
            
            for obj in objects:
                if obj.is_dir :
                    result['exist'] = True
                else :
                    result['exist'] = True
                break
        except S3Error as e:
            print(f"发生错误: {e}")
        
        return result
