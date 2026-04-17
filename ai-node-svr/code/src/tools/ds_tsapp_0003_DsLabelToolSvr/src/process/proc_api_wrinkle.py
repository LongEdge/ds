from email.mime import base
import os
from enum import Flag, auto
import json
import base64
from PIL import Image
from io import BytesIO
from datetime import datetime
import cv2
import uuid
import time
import threading
import numpy as np
from flask import Flask,render_template
from ..features.common.imgbase import *
from .proc_comm import eStatusCode

# 过度阶段，以后在DSOPEN中控制
# ACCESS_IDENTITY_PERMISSION = {
#     'GGMDS255':{'readgroup':['ALL'],'writegroup':['ALL'],'deletegroup':['ALL']},
#     'ABC123F87342':{'readgroup':['00000','00001'],'writegroup':['00001'],'deletegroup':[]},
#     'CSKIN':{'readgroup':['00026'],'writegroup':[],'deletegroup':[]},
# }

class CProcessorAPIWrinkle():
    def __init__(self,proc_comm):
        self.proc_comm = proc_comm
        self.node_cfg = proc_comm.getNodeCfg()
        self.storage_cloud = proc_comm.getStorageCloudObj()
        self.conn_name  = self.node_cfg['dconn_name']
        self.wrinkle_remote_root_path = self.node_cfg['wrinkle_remote_root_path']
        self.img_zoom_ratio = 0.75
        self.imgBase64Cache = [] #缓存图像的base64数据,缓存100张图像
        """
        {
            '<img_path>': {
                'src_img_width':new_img_width,
                'src_img_height':new_img_height,
                'base64_data':base64_data
                }
        }
        """
        self.imgBase64CacheSize = 6000 # 4000个数据，两个group的数据。
        self.cache_lock = threading.RLock()  # 添加互斥锁
    
    # 缓存图像的base64
    def saveImgBase64ToCache(self,img_path,img_base64_obj):
        with self.cache_lock:  # 加锁保护
            # 如果已经存在，则更新
            img_path_key = img_path.replace('/','_')
            img_base64_obj['img_path'] = img_path_key
            for img_obj in self.imgBase64Cache:
                if img_path_key in img_obj:
                    img_obj[img_path_key] = img_base64_obj
                    return

            # 不存在就添加
            if len(self.imgBase64Cache) >= self.imgBase64CacheSize:
                self.imgBase64Cache.pop(0)
            img_path_key = img_path.replace('/','_')
            self.imgBase64Cache.append({img_path_key:img_base64_obj})
    
    def getImgBase64FromCache(self,img_path):
        with self.cache_lock:  # 加锁保护
            img_path_key = img_path.replace('/','_')
            for img_obj in self.imgBase64Cache:
                if img_path_key in img_obj:
                    return img_obj[img_path_key]
            return None

    def deletePngCache(self,param):
        flag,retobj =  self.proc_comm.checkParamValid(param,['group_name'])
        if flag == False:
            return retobj
        group_name = param['group_name']
        with self.cache_lock:  # 加锁保护
            try:
                for cacheitem in self.imgBase64Cache:
                    first_key = next(iter(cacheitem.keys()))
                    if '_'+group_name+'_' in first_key and '.png' in first_key:
                        print('delete :111')
                        # 从缓存中删除
                        self.imgBase64Cache.remove(cacheitem)
            except Exception as e:
                return self.proc_comm.packRetJson(eStatusCode.FAILED,[],str(e))
        ret  = self.proc_comm.packRetJson(eStatusCode.SUCCESS,[])
        return ret

    # 删除指定的图像文件
    def deleteImgFromMinio(self,param):
        flag,retobj =  self.proc_comm.checkParamValid(param,['access_identity','group_name','img_path'])
        if flag == False:
            return retobj
        access_identity = param['access_identity']
        img_path = param['img_path']
        group_name = param['group_name']
        if img_path.split('.')[1] not in 'jpg/png':
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'not image file [jpg/png]')
        # 判断权限
        if self.checkAccessForGroupDir(access_identity,group_name)['Del'] == False:
            return self.proc_comm.packRetJson(eStatusCode.PARAM_ERR,[],'没有权限删除数据')
        # 删除数据 
        remote_img_path = self.wrinkle_remote_root_path.strip('/') + '/'+img_path.strip('/')
        try:
            self.storage_cloud.deleteFile(self.conn_name,remote_img_path)
        except Exception as e:
            print(e)
        
        return self.proc_comm.packRetJson(eStatusCode.SUCCESS,[],'success')

    # 获取文件目录列表
    def getImgDirLists(self,param):
        print(param)
        flag,retobj =  self.proc_comm.checkParamValid(param,['access_identity'])
        if flag == False:
            return retobj
        if 'filter_dirname' not in param:
            param['filter_dirname'] = ''
        filter_dirname = param['filter_dirname']
        access_identity = param['access_identity']

        ret_dirs = {'dirlist':[]}
        remote_img_dir_path = self.wrinkle_remote_root_path.strip('/')+'/src-img/'
        tmp_dirs = self.storage_cloud.listFiles(self.conn_name,remote_img_dir_path)
        for tmp_dir in tmp_dirs:
            if tmp_dir['ftype'] == 'D':
                group_name = tmp_dir['name']
                print(group_name)
                if self.checkAccessForGroupDir(access_identity,group_name)['Rd'] == False:
                    continue
                
                if (filter_dirname ==''): # 没有指筛选目录，返回所有目录
                    ret_dirs['dirlist'].append(group_name)
                elif (  filter_dirname in group_name ):
                    ret_dirs['dirlist'].append(group_name)
        ret  = self.proc_comm.packRetJson(eStatusCode.SUCCESS,ret_dirs)
        return ret
    
    def getImgFileLists(self,param):
        flag,retobj =  self.proc_comm.checkParamValid(param,['access_identity','group_name','wrinkle_type'])
        if flag == False:
            return retobj
        group_name = param['group_name']
        wrinkle_type = param['wrinkle_type']
        access_identity = param['access_identity']

        # 权限控制代码
        if self.checkAccessForGroupDir(access_identity,group_name)['Rd'] == False:
            return self.proc_comm.packRetJson(eStatusCode.PARAM_ERR,[],'没有权限访问该目录')

        remote_img_dir_path = self.wrinkle_remote_root_path.strip('/')+'/src-img/'+group_name+'/'
        remote_mask_dir_path = self.wrinkle_remote_root_path.strip('/')+'/'+wrinkle_type+'/'+group_name+'/src-mask/'
        imgfile_list = self.storage_cloud.listFiles(self.conn_name,remote_img_dir_path)
        maskfile_list = self.storage_cloud.listFiles(self.conn_name,remote_mask_dir_path)
        # 把所有的mask文件筛选出来
        maskfile_array = []
        txtfile_array = []
        for tmp_file in maskfile_list:
            if tmp_file['ftype'] == 'F':
                file_name = tmp_file['name']
                if file_name.split('.')[1] == 'png':
                    maskfile_array.append(file_name)
                elif file_name.split('.')[1] == 'txt':
                    txtfile_array.append(file_name)
        # 组织返回信息
        ret_files = {'filelist':[]}
        idx = 0
        for tmp_file in imgfile_list:
            if tmp_file['ftype'] == 'F':
                # imgfilename = tmp_file['name']
                
                imgfilename = group_name+"_{0:04d}".format(idx)+'.jpg'#+tmp_file['name'].split("-")[-1]
                idx += 1
                imgfilepath = '/src-img/'+group_name+'/'+tmp_file['name']
                maskfilename = tmp_file['name'].split('.')[0]+'.png'
                maskfilepath =  '/'+wrinkle_type+'/'+group_name+'/src-mask/'+maskfilename
                maskstatus = {}
                if maskfilename in maskfile_array:
                    maskstatus['have_mask'] = True
                    for txt in txtfile_array:
                        txtfilename,txttimestamp = self.parseTxtFilename(txt)
                        if txtfilename == maskfilename.split('.')[0]:
                            maskstatus['is_label'] = True
                            # 解析时间戳并格式化为年月日时分秒
                            try:
                                # 假设时间戳格式为YYYYMMDDHHMMSS（14位数字）
                                dt = datetime.strptime(txttimestamp, '%Y%m%d%H%M%S')
                                maskstatus['label_time'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                # 处理格式错误，保留原始值并添加错误标记
                                maskstatus['label_time'] = f"{txttimestamp} (格式错误)"
                            break
                else:
                    maskstatus['have_mask'] = False
                fileitem =  {
                    'imgname':imgfilename,
                    'imgpath':imgfilepath,
                    'maskpath':maskfilepath,
                    'maskstatus':maskstatus
                }
                ret_files['filelist'].append(fileitem)

        ret  = self.proc_comm.packRetJson(eStatusCode.SUCCESS,ret_files)

        # 对文件列表进行排序
        ret_files['filelist'].sort(key=lambda x: x['imgname'])

        # 开一个线程对ret_files中的数据加载到缓存中
        thread = threading.Thread(target=self.loadFilelistToCache, args=(ret_files,))
        thread.start()

        return ret

    


    # 把整个列表加载到缓存
    def loadFilelistToCache(self,ret_files):
        for tmp_file in ret_files['filelist']:
            
            img_path = tmp_file['imgpath']
            # 判断缓存中如果不存在则添加缓存
            if self.getImgBase64FromCache(img_path) == None:
                self.getCacheImgBase64FromMinio({'img_path':img_path})
                print('load img:',tmp_file['imgname'])
            else:
                print('exist img in cache:',tmp_file['imgname'])
            if (tmp_file['maskstatus']['have_mask'] == True):
                img_path = tmp_file['maskpath']
                if self.getImgBase64FromCache(img_path) == None:
                    self.getCacheImgBase64FromMinio({'img_path':img_path})
    
    def getWrinkleType(self):
        ret = {
            'wrinkle_type':[
                # {'name':'抬头纹','value':'forhead'},
                # {'name':'鱼尾纹','value':'crows_feet'},
                {'name':'泪沟纹','value':'tear_through'},
                {'name':'法令纹','value':'nasolabial_fold'},
                # {'name':'川字纹','value':'chuan_pattern'},
                {'name':'综合皱纹','value':'wrinkle_stripe'}
            ]
        }
        ret  = self.proc_comm.packRetJson(eStatusCode.SUCCESS,ret,'success')
        return ret

    def createPngBase64FromMinio(self,param):
        flag,retobj =  self.proc_comm.checkParamValid(param,['img_width','img_height'])
        if flag == False:
            return retobj
        
        # 创建一个空白的二值png  # 添加变量验证和类型转换
        try:
            # 确保维度为正整数
            img_height = int(param['img_height'])
            img_width = int(param['img_width'])
            if img_height <= 0 or img_width <= 0:
                return self.proc_comm.packRetJson(eStatusCode.FAILED,ret,'图像高度和宽度必须为正数')
            # 创建空白图像
            img = np.zeros((img_height, img_width,4), dtype=np.uint8)
            img[:, :, 3] = 0
            # 扩展为三维数组以满足OpenCV格式要求
            # img = np.expand_dims(img, axis=-1)
            # 使用PNG压缩编码图像
            # ret, buffer = cv2.imencode('.png', img)
            local_img_path = self.node_cfg['local_data_path'].strip('/')+'/'+str(uuid.uuid4())+'.png'
            cv2.imwrite(local_img_path,img)
            # if not ret:
                # return self.proc_comm.packRetJson(eStatusCode.FAILED, ret, "图像编码失败")
            #  从文件读取并且转成base64
            with open(local_img_path, "rb") as f:
                base64_data = base64.b64encode(f.read()).decode("utf-8")
                base64_data = 'data:image/png;base64,'+base64_data
            os.remove(local_img_path)
        except NameError as e:
            return self.proc_comm.packRetJson(eStatusCode.FAILED,ret,f"变量未定义: {str(e)}")
        except ValueError as e:
            return self.proc_comm.packRetJson(eStatusCode.FAILED,ret,f"无效的图像尺寸: {str(e)}")
        except Exception as e:
            return self.proc_comm.packRetJson(eStatusCode.FAILED,ret,f"创建png文件失败: {str(e)}")
        
        # # 编码为base64
        # base64_data = base64.b64encode(img).decode('utf-8')
        ret = {
            'base64_data':base64_data
        }
        return self.proc_comm.packRetJson(eStatusCode.SUCCESS,ret,'success')


    def saveImgBase64ToMinio(self,param):
        flag,retobj =  self.proc_comm.checkParamValid(param,['img_path','img_base64'])
        if flag == False:
            return retobj

        img_base64 = param['img_base64']
        img_path = param['img_path']
        
        remote_img_path = self.wrinkle_remote_root_path.strip('/') + '/'+img_path.strip('/')
        # 验证是否是png文件
        if remote_img_path.split('.')[1] not in 'png':
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'not png file')
        # 验证路径中是否有src-mask
        if 'src-mask' not in remote_img_path:
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'src-mask not in path')
        

        # 结果提交到dst-mask目录，防止原数据被覆盖掉了(这个写法稍微草率了点)
        # remote_img_path = remote_img_path.replace('src-mask','dst-mask') （暂时保存到src-mask中）

        local_img_filename = os.path.basename(remote_img_path)
        local_img_path = self.node_cfg['local_data_path'].strip('/')+ '/'+local_img_filename
        try:
            # 新代码（图像压缩后传出，收到后放大）
            # img_base64是img的base64编码格式，需要先解码
            if ',' in img_base64:
                img_base64 = img_base64.split(',')[1]
            # 解码base64编码的图片
            img_data = base64.b64decode(img_base64)
            # 打开图像并按比例放大 (长宽都除以0.8，即放大1.25倍)
            with Image.open(BytesIO(img_data)) as img:
                # 计算新尺寸
                new_img_width = int(img.width / self.img_zoom_ratio)
                new_img_height = int(img.height / self.img_zoom_ratio)
                # 把新的png图更新到缓存中
                img_obj = {
                    'src_img_width':img.width,
                    'src_img_height':img.height,
                    'base64_data':img_base64
                }
                self.saveImgBase64ToCache(img_path,img_obj)
                # 新的png上传minio
                print("saveImgBase64ToMinio:",img.width,img.height)
                print("saveImgBase64ToMinio:",new_img_width,new_img_height)
                # 放大图像，使用高质量缩放算法
                resized_img = img.resize((new_img_width, new_img_height), Image.Resampling.LANCZOS)
                
                # 保存处理后的图像到本地文件
                with open(local_img_path, "wb") as f:
                    # 获取图像格式
                    img_format = local_img_filename.split('.')[-1].upper()
                    resized_img.save(f, format=img_format)
            
                # 上传图像
                self.storage_cloud.uploadFile(self.conn_name, local_img_path, remote_img_path)
                os.remove(local_img_path)
                return self.proc_comm.packRetJson(eStatusCode.SUCCESS)
        except:
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'upload file failed')

    def getMaskBase64FromMinio(self,param):
        """
        @param conn_name: 连接名称
        @param img_path: 图片路径
        @return: base64编码的图片
        """
        flag,retobj =  self.proc_comm.checkParamValid(param,['img_path','img_width','img_height'])
        if flag == False:
            return retobj
        img_path = param['img_path']
        img_width = param['img_width']
        img_height = param['img_height']
        if img_path.split('.')[1] not in 'png':
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'not image file [ png]')
        remote_img_path = self.wrinkle_remote_root_path.strip('/') + '/'+img_path.strip('/')
        # 如果服务端png不存在则创建新的png返回
        if not self.storage_cloud.checkFileExist(self.conn_name,remote_img_path):
            return self.createPngBase64FromMinio({'img_width':img_width,'img_height':img_height})
        else:
            # 如果存在png则下载，返回base64
            local_img_filename = os.path.basename(remote_img_path)
            local_img_path = self.node_cfg['local_data_path'].strip('/')+ '/'+local_img_filename
            self.storage_cloud.downloadFile(self.conn_name,remote_img_path,local_img_path)
            if not os.path.exists(local_img_path):
                return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'download file failed')
            # 读取文件，得到大小
            try:
                img = cv2.imread(local_img_path,cv2.IMREAD_UNCHANGED)
                img_height, img_width = img.shape[:2]
            except:
                return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'resize img error')
            # 读取base64
            base64_data = ''
            try:  
                # 原来的代码(不压缩图)
                # with open(local_img_path, "rb") as f:
                #     base64_data = base64.b64encode(f.read()).decode("utf-8")
                #     if local_img_filename.split('.')[1] == 'png':
                #         base64_data = 'data:image/png;base64,'+base64_data

                # 新代码（进行图像压缩）
                with Image.open(local_img_path) as img:
                    # 计算新尺寸
                    new_img_width = int(img.width * self.img_zoom_ratio)
                    new_img_height = int(img.height * self.img_zoom_ratio)
                    # 按比例缩小图像，使用高质量缩放算法
                    resized_img = img.resize((new_img_width, new_img_height), Image.Resampling.LANCZOS)
                    
                    # 将缩放后的图像保存到内存缓冲区
                    buffer = BytesIO()
                    # 获取文件扩展名
                    img_format = local_img_filename.split('.')[1].upper()
                    if img_format == 'JPG':
                        img_format = 'JPEG'
                    resized_img.save(buffer, format=img_format)
                    
                    # 从缓冲区读取数据并转换为base64
                    base64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    # 设置base64前缀
                    base64_data = f'data:image/{img_format.lower()};base64,{base64_data}'
            except :
                os.remove(local_img_path)
                return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'convert img to base64 error')
            os.remove(local_img_path)

            ret = {
                'src_img_width':new_img_width,
                'src_img_height':new_img_height,
                'base64_data':base64_data
            }
            return self.proc_comm.packRetJson(eStatusCode.SUCCESS,ret,'success')

    def getCacheImgBase64FromMinio(self,param):
        flag,retobj =  self.proc_comm.checkParamValid(param,['img_path'])
        if flag == False:
            return retobj
        img_path = param['img_path']
        if img_path.split('.')[1] not in 'jpg/png':
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'not image file [jpg/png]')
        
        # 检验缓存中是否已经存在
        base64_data_ret = self.getImgBase64FromCache(img_path)
        if base64_data_ret:
            return self.proc_comm.packRetJson(eStatusCode.SUCCESS,[],'success')

        remote_img_path = self.wrinkle_remote_root_path.strip('/') + '/'+img_path.strip('/')
        local_img_filename = os.path.basename(remote_img_path)
        local_img_path = self.node_cfg['local_data_path'].strip('/')+ '/'+local_img_filename
        try:
            self.storage_cloud.downloadFile(self.conn_name,remote_img_path,local_img_path)
            if not os.path.exists(local_img_path):
                return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'download file failed')
        except:
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'download file failed')
        # 读取文件，得到大小
        try:
            img = cv2.imread(local_img_path,cv2.IMREAD_UNCHANGED)
            img_height, img_width = img.shape[:2]
        except:
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'resize img error')
        # 读取base64
        base64_data = ''
        try:  
            # 更新的缩小图像的代码
            # 打开图像并按比例缩小到0.8倍
            with Image.open(local_img_path) as img:
                # 计算新尺寸
                new_img_width = int(img.width * self.img_zoom_ratio)
                new_img_height = int(img.height * self.img_zoom_ratio)
                # 按比例缩小图像，使用高质量缩放算法
                resized_img = img.resize((new_img_width, new_img_height), Image.Resampling.LANCZOS)
                
                # 将缩放后的图像保存到内存缓冲区
                buffer = BytesIO()
                # 获取文件扩展名
                img_format = local_img_filename.split('.')[1].upper()
                if img_format == 'JPG':
                    img_format = 'JPEG'
                resized_img.save(buffer, format=img_format)
                
                # 从缓冲区读取数据并转换为base64
                base64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
                # 设置base64前缀
                base64_data = f'data:image/{img_format.lower()};base64,{base64_data}'
            os.remove(local_img_path)
        except :
            os.remove(local_img_path)
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'convert img to base64 error')
        ret = {
            'src_img_width':new_img_width,
            'src_img_height':new_img_height,
            'base64_data':base64_data
        }
        self.saveImgBase64ToCache(img_path,ret)
        return self.proc_comm.packRetJson(eStatusCode.SUCCESS,[],'success')

    def getImgBase64FromMinio(self,param):
        """
        @param conn_name: 连接名称
        @param img_path: 图片路径
        @return: base64编码的图片
        """
        print('getImgbase64',param)
        print('getImgbase64 1',time.time())
        # 打印时间戳
        flag,retobj =  self.proc_comm.checkParamValid(param,['img_path'])
        if flag == False:
            return retobj
        img_path = param['img_path']
        # 如果缓存中存在则直接取
        base64_data_ret = self.getImgBase64FromCache(img_path)
        if base64_data_ret:
            print('get imgbase64 from cache,img_path:',img_path)
            print('getImgbase64 3',time.time())
            return self.proc_comm.packRetJson(eStatusCode.SUCCESS,base64_data_ret,'success')

        # 如果缓存中不存在，则正常的下载文件并且转格式
        if img_path.split('.')[1] not in 'jpg/png':
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'not image file [jpg/png]')
        remote_img_path = self.wrinkle_remote_root_path.strip('/') + '/'+img_path.strip('/')
        local_img_filename = os.path.basename(remote_img_path)
        local_img_path = self.node_cfg['local_data_path'].strip('/')+ '/'+local_img_filename
        self.storage_cloud.downloadFile(self.conn_name,remote_img_path,local_img_path)
        if not os.path.exists(local_img_path):
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'download file failed')
        # 读取文件，得到大小
        try:
            img = cv2.imread(local_img_path,cv2.IMREAD_UNCHANGED)
            img_height, img_width = img.shape[:2]
        except:
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'resize img error')
        # 读取base64
        base64_data = ''
        try:  
            # 原来的代码
            # with open(local_img_path, "rb") as f:
            #     base64_data = base64.b64encode(f.read()).decode("utf-8")
            #     if local_img_filename.split('.')[1] == 'jpg':
            #         base64_data = 'data:image/jpg;base64,'+base64_data
            #     elif local_img_filename.split('.')[1] == 'png':
            #         base64_data = 'data:image/png;base64,'+base64_data
            # 更新的缩小图像的代码
            # 打开图像并按比例缩小到0.8倍
            with Image.open(local_img_path) as img:
                # 计算新尺寸
                new_img_width = int(img.width * self.img_zoom_ratio)
                new_img_height = int(img.height * self.img_zoom_ratio)
                # 按比例缩小图像，使用高质量缩放算法
                resized_img = img.resize((new_img_width, new_img_height), Image.Resampling.LANCZOS)
                
                # 将缩放后的图像保存到内存缓冲区
                buffer = BytesIO()
                # 获取文件扩展名
                img_format = local_img_filename.split('.')[1].upper()
                if img_format == 'JPG':
                    img_format = 'JPEG'
                resized_img.save(buffer, format=img_format)
                
                # 从缓冲区读取数据并转换为base64
                base64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
                # 设置base64前缀
                base64_data = f'data:image/{img_format.lower()};base64,{base64_data}'
        except :
            os.remove(local_img_path)
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'convert img to base64 error')
        os.remove(local_img_path)

        ret = {
            'src_img_width':new_img_width,
            'src_img_height':new_img_height,
            'base64_data':base64_data
        }
        print('getImgbase64 2',time.time())
        return self.proc_comm.packRetJson(eStatusCode.SUCCESS,ret,'success')
    

#---------------------------HTML-------------------------------
    def htmlWrinkleLabel(self,param,htmlname):
        print(param)
        # token = self.getTokenFromURL()

        try:
            template_path = htmlname
            htmlcontent = render_template(template_path,**param)
        except Exception as e:
            print(f"模板渲染错误: {str(e)}")
        return htmlcontent
    
    def htmlWrinkleTest(self,param):
        print(param)
        try:
            template_path = 'test.html'
            htmlcontent = render_template(template_path,**param)
            print(htmlcontent)
        except Exception as e:
            print(f"模板渲染错误: {str(e)}")
        return htmlcontent

#---------------------------私有函数-------------------------------
    # txt文件的格式：文件名_[时间戳].txt,从文件名称中解析内容:文件名、时间
    def parseTxtFilename(self,filename):
        """
        @param filename 文件名_[时间戳].txt
        @return: 文件名、时间戳
        """
        filename = filename.split('.')[0]  # 移除文件扩展名
        # 只分割第一个下划线，保留后续下划线
        parts = filename.rsplit('_', 1)
        # 处理没有下划线或只有一个部分的情况
        if len(parts) >= 2:
            return parts[0], parts[1]
        else:
            # 返回文件名本身和空字符串（或根据业务需求调整默认值）
            return parts[0], ''
    
    # 验证某个GroupName是否在访问范围内
    def checkAccessForGroupDir(self,access_identity,group_name):
        """
        验证某个GroupName是否在访问范围内
        @access_identity 访问身份
        @group_name 目录名称
        @return True/False
        """
        flagRead = False
        flagWrite = False
        flagDelete = False
        with open('/data_ware/account_mng/mark_account.txt', 'r', encoding='utf-8') as f:
            ACCESS_IDENTITY_PERMISSION = json.loads(f.read())
        if access_identity not in ACCESS_IDENTITY_PERMISSION:
            return {'Rd':False,'Wt':False,'Del':False}
        access_dirname_list = ACCESS_IDENTITY_PERMISSION[access_identity]
        print(access_dirname_list)
        if group_name  in access_dirname_list['readgroup'] or access_dirname_list['readgroup']==['ALL']:
            flagRead = True
        if group_name  in access_dirname_list['writegroup'] or access_dirname_list['writegroup']==['ALL']:
            flagWrite = True
        if group_name  in access_dirname_list['deletegroup'] or access_dirname_list['deletegroup']==['ALL']:
            flagDelete = True
        
        return {'Rd':flagRead,'Wt':flagWrite,'Del':flagDelete}

    def getTokenFromURL(self):
        # 获取URL的head中的token
        token = request.headers.get('Authorization')
        if token == None:
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'token error')
        token = token.replace('Bearer ','')
        return token