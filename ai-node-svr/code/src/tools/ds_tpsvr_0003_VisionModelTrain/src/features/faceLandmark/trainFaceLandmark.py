"""
训练人脸关键点模型: 
trainFaceLandmarkDlib: DLIB版本(用于美容院的ipad客户端和服务端)
trainFaceLandmarkPytorch: Pytorch版本

"""

import os
import torch
import glob
import cv2
import numpy as np



class CTrainFaceLandmark:
    def __init__(self, node_cfg, process_comm, proc_modules_obj, progress_callback):
        self.node_cfg = node_cfg
        self.process_comm = process_comm
        self.proc_modules_obj = proc_modules_obj
        self.progress_callback = progress_callback


    """
    五官训练-DLIB版本
    """
    def trainFaceLandmarkDlib(self, cmd_param):
        pass

    
    """
    五官训练-Pytorch版本
    """
    def trainFaceLandmarkDlib(self, cmd_param):
        pass

    """
    五官预测-Pytorch版本
    """
    def predictFaceLandmarkPytorch(self, cmd_param):
        return self._predictFaceLandmarkPytorch(cmd_param['model'], 
                                                cmd_param['img_path'])



    def _predictFaceLandmarkPytorch(self, model, img_path):