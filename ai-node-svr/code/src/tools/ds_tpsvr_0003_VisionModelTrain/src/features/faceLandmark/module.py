"""
训练人脸关键点模型: 
trainFaceLandmarkDlib: DLIB版本(用于美容院的ipad客户端和服务端)
trainFaceLandmarkPytorch: Pytorch版本

"""

import torch
import torch.nn as nn
import torchvision.models as models


class LandmarkModel(nn.Module):
    def __init__(self, num_landmarks=81):
        super(LandmarkModel, self).__init__()
        
        # 加载预训练的 ResNet18 模型
        self.resnet = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)  # 使用新的权重加载方式
        
        # 移除 ResNet 的最后一层 (全连接层)
        self.resnet = nn.Sequential(*list(self.resnet.children())[:-1])  # 移除fc层
        
        # 定义一个全连接层，输入大小来自 ResNet 的输出尺寸
        # 获取最后一个卷积层输出的尺寸
        self.fc1 = nn.Linear(self._get_fc_in_features(), 1024)  # 输入特征数是根据 resnet 输出特征的大小
        
        # 定义输出层，输出对应 68 个地标的 x, y 坐标
        self.fc2 = nn.Linear(1024, num_landmarks * 2)  # 输出 68 个地标，每个地标有 x 和 y 坐标

    def _get_fc_in_features(self):
        # 创建一个假的输入（例如 224x224 大小的 RGB 图像），并将其传递到 ResNet 中
        with torch.no_grad():
            dummy_input = torch.zeros(1, 3, 224, 224)  # 假设输入图像大小是 224x224
            output = self.resnet(dummy_input)
        return output.view(output.size(0), -1).size(1)  # 返回展平后的特征数量

    def forward(self, x):
        # 通过 ResNet 提取特征
        x = self.resnet(x)
        
        # 展平 ResNet 的输出
        x = x.view(x.size(0), -1)
        
        # 通过全连接层
        x = self.fc1(x)
        x = self.fc2(x)
        
        return x
