from cProfile import label
import json
import os
import glob
import cv2
import torch
import torch.nn as nn
import torchvision.transforms as transforms
from torch.utils.data import Dataset
from PIL import Image

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

class ImgClassifyDataset(Dataset):
    def __init__(self, img_dirs, label_map_file, img_size=512):
        """
        img_dirs: 要训练的图片目录列表
        label_map_file: 包含所有图片路径和标签的映射文件
        """
        self.img_transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((img_size, img_size), interpolation=Image.BILINEAR),
            transforms.ToTensor()
        ])
        
        # 读取标签映射文件
        with open(label_map_file, 'r') as f:
            all_imgPath2label = json.load(f)
        
        # 过滤出在img_dirs中的图片路径
        self.imgPath2label = {}
        for img_path, label in all_imgPath2label.items():
            # 检查图片路径是否以img_dirs中的任何一个目录开头
            if any(img_path.startswith(img_dir) for img_dir in img_dirs):
                self.imgPath2label[img_path] = label
        
        self.img_paths = list(self.imgPath2label.keys())
        
        if len(self.img_paths) == 0:
            raise ValueError("在img_dirs中未找到任何图片路径")
        
        # 获取唯一的分类代码
        self.unique_codes = list(set(self.imgPath2label.values()))
        self.code_to_idx = {code: idx for idx, code in enumerate(self.unique_codes)}
        self.num_classes = len(self.unique_codes)
        
        print(f"数据集大小: {len(self.img_paths)}")
        print(f"类别数量: {self.num_classes}")

    def __len__(self):
        return len(self.img_paths)

    def __getitem__(self, idx):
        img_path = self.img_paths[idx]
        # 获取img
        img = cv2.imread(img_path)
        if img is None:
            raise ValueError(f"读取失败：{img_path}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = self.img_transform(img)

        # 获取code
        classifycode = self.imgPath2label[img_path]
        label = self.code_to_idx[classifycode]

        return img, label
