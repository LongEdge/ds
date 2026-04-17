import cv2
import os
import json
import numpy as np
from flask import render_template
from PIL import Image
from io import BytesIO
import base64
from .proc_comm import eStatusCode

class CDataMng():
    def __init__(self,proc_comm):
        self.proc_comm = proc_comm
        self.node_cfg = proc_comm.getNodeCfg()
        self.storage_cloud = proc_comm.getStorageCloudObj()
        self.conn_name  = self.node_cfg['dconn_name']
        
    
    # 根据输入的img_path, 从minio获取图片, 并返回base64编码
    def getImgbase64FromMinio(self,param):
        """
        @param conn_name: 连接名称
        @param img_path: 图片路径,在minio中除了bucket_name的完整路径
        @return: base64编码的图片
        """
        print(param)
        flag,retobj =  self.proc_comm.checkParamValid(param,['img_path'])
        if flag == False:
            return retobj
        img_path = param['img_path']
        if img_path.split('.')[1] not in 'jpg/png':
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'not image file [jpg/png]')

        remote_img_path = img_path.strip('/')
        local_img_filename = os.path.basename(remote_img_path)
        local_img_path = self.node_cfg['local_data_path'].strip('/')+ '/'+local_img_filename
        self.storage_cloud.downloadFile(self.conn_name,remote_img_path,local_img_path)
        if not os.path.exists(local_img_path):
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'download file failed')
        # 读取base64
        base64_data = ''
        try:  
            # 打开图像并按比例缩小到0.8倍
            with Image.open(local_img_path) as img:
                # 计算新尺寸
                new_img_width = int(img.width * 0.75)
                new_img_height = int(img.height * 0.75)
                print("getImgBase64FromMinio:",img.width,img.height)
                print("getImgBase64FromMinio:",new_img_width,new_img_height)
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

    #---------------------------HTML-------------------------------
    def htmlPreviewImg(self,param):
        """
        预览图像
        """
        print(param)
        try:
            template_path = 'previewImg.html'
            htmlcontent = render_template(template_path,**param)
        except Exception as e:
            print(f"模板渲染错误: {str(e)}")
        return htmlcontent

    #---------------------------私有函数-------------------------------
