from cProfile import label
import json
import os
import glob
import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.transforms as transforms
from torch.utils.data import Dataset
from pathlib import Path
import random


# -------------------- 兼容多类别的 U-Net --------------------
class DoubleConv(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        return self.conv(x)


class UNet(nn.Module):
    def __init__(self, n_channels=3, n_classes=1):
        super().__init__()
        self.n_classes = n_classes  # ① 保存类别数，供 forward 判断

        # 编码器
        self.inc   = DoubleConv(n_channels, 64)
        self.down1 = nn.Sequential(nn.MaxPool2d(2), DoubleConv(64, 128))
        self.down2 = nn.Sequential(nn.MaxPool2d(2), DoubleConv(128, 256))
        self.down3 = nn.Sequential(nn.MaxPool2d(2), DoubleConv(256, 512))
        self.down4 = nn.Sequential(nn.MaxPool2d(2), DoubleConv(512, 1024))

        # 解码器
        self.up1   = nn.ConvTranspose2d(1024, 512, 2, stride=2)
        self.conv1 = DoubleConv(1024, 512)
        self.up2   = nn.ConvTranspose2d(512, 256, 2, stride=2)
        self.conv2 = DoubleConv(512, 256)
        self.up3   = nn.ConvTranspose2d(256, 128, 2, stride=2)
        self.conv3 = DoubleConv(256, 128)
        self.up4   = nn.ConvTranspose2d(128, 64, 2, stride=2)
        self.conv4 = DoubleConv(128, 64)

        # ② 输出层：通道数 = 类别数
        self.outc  = nn.Conv2d(64, n_classes, 1)

    def forward(self, x):
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)
        x5 = self.down4(x4)

        x = self.conv1(torch.cat([self.up1(x5), x4], dim=1))
        x = self.conv2(torch.cat([self.up2(x), x3], dim=1))
        x = self.conv3(torch.cat([self.up3(x), x2], dim=1))
        x = self.conv4(torch.cat([self.up4(x), x1], dim=1))

        logits = self.outc(x)  # ③ 先拿到 raw logits

        # ④ 根据任务类型返回不同激活
        if self.n_classes == 1:
            return torch.sigmoid(logits)          # 二分类：0~1
        return logits                              # 多分类：交给 CrossEntropyLoss
# -------------------- 数据集 --------------------
"""
dataset/
 ├── images/
 │   ├── 0001.jpg
 │   ├── 0002.jpg
 │   └── ...
 └── masks/
     ├── 0001.png
     ├── 0002.png
     └── ...
png:0=背景，255=皱纹
"""

# 这是细纹滑块512*512的写法
class WrinkleDatasetSlim512SavedImg(Dataset):
    def __init__(self, img_dir, mask_dir, patch_size=512, augment=True):
        self.patch_size = patch_size
        self.samples_img = sorted([os.path.abspath(os.path.join(img_dir, f)) for f in os.listdir(img_dir)])
        self.samples_mask = sorted([os.path.abspath(os.path.join(mask_dir, f)) for f in os.listdir(mask_dir)])
        assert len(self.samples_img) == len(self.samples_mask), "图像与掩膜数量不一致"


    def __len__(self):
        return len(self.samples_img)

    def __getitem__(self, idx):
        img_patch = cv2.imread(self.samples_img[idx])
        mask_patch = cv2.imread(self.samples_mask[idx], cv2.IMREAD_GRAYSCALE)

        # mask_patch = (mask_patch > 10).astype(np.uint8) * 255 # 可能不需要

        img_tensor = torch.from_numpy(img_patch/255.).permute(2,0,1).float()
        mask_tensor = torch.from_numpy(mask_patch/255.).unsqueeze(0).float()

        return img_tensor, mask_tensor
    

# 这是粗纹直接resize的写法-保存为图片
class WrinkleDatasetNasolabialResized1024SaveImg(Dataset):
    def __init__(self, img_dir, mask_dir, patch_size=1024, augment=True):
        self.patch_size = patch_size
        self.samples_img = sorted([os.path.abspath(os.path.join(img_dir, f)) for f in os.listdir(img_dir)])
        self.samples_mask = sorted([os.path.abspath(os.path.join(mask_dir, f)) for f in os.listdir(mask_dir)])
        assert len(self.samples_img) == len(self.samples_mask), "图像与掩膜数量不一致"

    def __len__(self):
        return len(self.samples_img)

    def __getitem__(self, idx):
        img_patch = cv2.imread(self.samples_img[idx])
        mask_patch = cv2.imread(self.samples_mask[idx], cv2.IMREAD_GRAYSCALE)

        mask_patch = (mask_patch > 10).astype(np.uint8) * 255

        img_tensor = torch.from_numpy(img_patch/255.).permute(2,0,1).float()
        mask_tensor = torch.from_numpy(mask_patch/255.).unsqueeze(0).float()

        return img_tensor, mask_tensor