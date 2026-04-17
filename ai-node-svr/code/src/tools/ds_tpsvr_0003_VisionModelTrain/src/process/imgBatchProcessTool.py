import cv2
import numpy as np
import os
from tqdm import tqdm
from src.features.common.imgbase import *



"""

{
    "FunDesc": "把数据从minio同步到本地",
    "ReqParam": {
        "dtype": "imgBatchProcTools",
        "local_dconn_name": "ds_pg_gpu_work_data", # 对于STORAGE_TYPE=local才需要指定
        "subfuncs": [
        {
            "funcname": "erode_img_mask",
            "params": {
                    "mask_dir": "AIDataManage/CskinWrinkle",
                    "kernel_size": 4
            }
        },
        ]
    }
}


"""

class CImgBatchProcessTool:
    def __init__(self, node_cfg,process_comm):
        self.node_cfg = node_cfg
        self.process_comm = process_comm
        self.dconn_name = self.node_cfg['cloud_storage_dconn_cfg']

    def StartTaskImgProcess(self, params):
        for subtask in params['subfuncs']:
            funcname = subtask['funcname']
            local_dconn_name = params['local_dconn_name']
            root_dir = self.node_cfg['cloud_storage_dconn_cfg'][local_dconn_name]['BUCKET_PATH']

            if funcname == 'erode_mask_dir':
                self.erode_mask_dir(root_dir, subtask['params'])
            else:
                print("未实现的函数: ", funcname)
                return None

    def erode_mask_dir(self, root_dir, params):
        """
        @description: 对二值掩膜图进行腐蚀操作, 可以把轮廓变小
        @params:
            root_dir: 要处理本地的根目录
            params: 处理函数的入参
        @return:
            
        """
        # 读取二值掩膜图（假设白色线条为255，背景为0）
        mask_dir = params['mask_dir']
        kernel_size = params.get('kernel_size', 4)

        root_dir = root_dir.rstrip('/')
        base_path = os.path.join(root_dir, mask_dir)

        # 收集所有 .png 文件路径
        mask_files = []
        for dirpath, _, filenames in os.walk(base_path):
            for f in filenames:
                if f.lower().endswith('.png'):
                    mask_files.append(os.path.join(dirpath, f))

        # tqdm 进度条
        for mask_abspath in tqdm(mask_files, desc="腐蚀掩膜中", ncols=80):
            try:
                self.erode_mask_file(mask_abspath, mask_abspath, kernel_size)
            except Exception as e:
                print(f"[WARN] {mask_abspath} 处理失败: {e}")


    def erode_mask_file(self, mask_abspath, mask_saved_path, kernel_size):
        """
        @description: 对二值掩膜图进行腐蚀操作, 可以把轮廓变小
        @params:
            root_dir: 要处理本地的根目录
            params: 处理函数的入参
        @return:
            
        """
        # 读取二值掩膜图（假设白色线条为255，背景为0）
        try:
            img_mask_alpha = cv2.imread(mask_abspath, cv2.IMREAD_UNCHANGED) # 把alpha通道也读取进来
            rgba = cv2.split(img_mask_alpha)
            r, g, b, a = rgba
        except Exception as e:
            print("打开透明掩膜失败e: ", e)
            return None

        img_mask = a
        img_mask = (img_mask > 10).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))   # 定义腐蚀核的形状和大小（控制“收缩”的程度）
        eroded = cv2.erode(img_mask, kernel, iterations=1)                                  # 腐蚀操作(变细)
        erodedRedMask = readMaskFromPng(eroded)                                        # 转回红色的png图
        cv2.imwrite(mask_saved_path, erodedRedMask)

