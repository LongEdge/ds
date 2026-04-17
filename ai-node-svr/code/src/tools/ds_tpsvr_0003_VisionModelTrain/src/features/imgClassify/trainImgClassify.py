# 图像分类模型训练
from curses import OK
from ntpath import exists
import os
import glob
import cv2
import numpy as np
import shutil
import time
import pynvml  # nvidia-ml-py3
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.utils.data import DataLoader, random_split
from torchvision import transforms
from PIL import Image
from tqdm import tqdm
from pathlib import Path
from src.features.imgClassify.module_unet import ImgClassifyDataset, UNet
import json

"""
请求格式：
{
    "FunDesc": "检查图像是否破损",
    "ReqParam": {
        "dtype": "imgclassityPreProcess",
        "folder_paths": [ 
                "/data_ware/work_data/dsImgRecognition/src-img/00000",
                # "/data_ware/work_data/DsImgRecognition/src-img/00001/"
                "/data_ware/work_data/dsImgRecognition/src-img/00001"
                ]
        }
}        

{
    "FunDesc": "图片分类模型训练——训练",
    "ReqParam": {
        "dtype": "classifytrainImgModuleByUnet",
        "train_img_dirs": [ 
            "/data_ware/work_data/dsImgRecognition/src-img/00000",
            "/data_ware/work_data/dsImgRecognition/src-img/00001"
            ], 
        "train_label_dirs":[
            "/data_ware/work_data/dsImgRecognition/img-recog/00000",
            "/data_ware/work_data/dsImgRecognition/img-recog/00001"],
        "train_model_dir": "/data_ware/work_data/dsImgRecognition/models", #模型存放地址
        "train_model_name": "01-2-1", # 模型名称 
        "train_img_size": 512, # 训练图片大小 a*a
        "train_batch_size": 4, # 批次大小，每轮训练的图片数量
        "train_epochs": 10, # 训练轮数
        "train_lr": 0.001, # 学习率
        "train_val_ratio": 0.1, #验证集大小
        "train_patience": 15, #连续 patience 轮没有提升 就强制结束训练
        "train_pretrain_path": None, #可选预训练模型地址
    }
}

{
    "FunDesc": "图片分类模型训练——预测",
    "ReqParam": {
        "dtype": "batchpredictByUnet",
        "predict_model_dir": "/data_ware/work_data/dsImgRecognition/models/", # 模型地址
        "predict_model_name": "unet_epoch50.pth", # 模型名称 模型完整地址=model_dir+model_name
        "predict_img_dirs": "/data_ware/work_data/dsImgRecognition/src-img/00002/", # 原图文件夹地址(支持多个文件夹)
        “predict_label_dirs": "data_ware/work_data/dsImgRecognition/img-recog/00002",
        "predict_classify_dir": "data_ware/work_data/dsImgRecognition/utils/classify_list.json",
        "predict_img_size": 512 # 训练图片大小 a*a
    }
}

"""

#  Wrinkle 数据训练
# 1、数据下载（syncFilesFromCloud2Local）：data/train_data/wrinkle 目录是从minio同步过来的数据 
# 2、数据整理（organize_dataset）：训练之前把数据整理到/tmp目录下 
# 3、训练（），训练模型放在 data/train_model下
# 4、预测（），预测结果放在 data/train_data/wrinkle/【皱纹类型】/【GroupName】/dst-mask目录下
# 5、数据上传（）
class CTrainImgClassify:
    # def __init__(self):
    def __init__(self, node_cfg, process_comm, proc_modules_obj, progress_callback):
        # self.node_cfg, self.process_comm
        self.node_cfg = node_cfg
        self.process_comm = process_comm
        self.proc_modules_obj = proc_modules_obj
        self.progress_callback = progress_callback

    def StartTaskTrainImgClassify(self,cmd_param):
        print("cmd_param: ", cmd_param)
        for subtask in cmd_param['subfuncs']:
            print("subtask: ", subtask)
            funcname = subtask['func_name']
            local_dconn_name = cmd_param['local_dconn_name']
            root_dir = self.node_cfg['cloud_storage_dconn_cfg'][local_dconn_name]['BUCKET_PATH']

            if funcname == 'erode_mask_dir':
                print("dir: ", dir(self.proc_modules_obj['imgbase']))
                self.proc_modules_obj['imgbase'].erode_mask_dir(root_dir, subtask['params'])  # 如果有些函数感觉可以通用, 可以写到featuers/common/imgbase文件内, 方便大家一起调用
            elif funcname == "dataPreProcess":
                self.dslabeldataPreProcess(subtask['params']) 
            elif funcname == "trainImgModuleByUnet":
                self.classifytrainImgModuleByUnet(subtask['params']) 
            elif funcname == "predictClassifyImgModuleByUnet":
                self.classifypredictByUnet(subtask['params']) 
            elif funcname == "predictBatchClassifyImgModuleByUnet"  :
                self.classifyBatchpredictByUnet (subtask['params'])  
                                      


    def getNodeCfg(self):
        return self.node_cfg
    
    def getStorageCloudObj(self):
        return self.storage_cloud

    def dslabeldataPreProcess(self,cmd_param):
        self.dataPreProcess(cmd_param['folder_paths']) 

    def classifytrainImgModuleByUnet(self,cmd_param):
        """
        @param  train_img_dirs  原图的文件夹地址列表，示例：["/data_ware/work_data/dsImgRecognition/src-img/00000", "/data_ware/work_data/dsImgRecognition/src-img/00001"]
        @param  train_label_dirs  标签的文件夹地址列表，示例：["/data_ware/work_data/dsImgRecognition/img-recog/00000", "/data_ware/work_data/dsImgRecognition/img-recog/00001"]
        @param  train_model_dir  模型存放地址，示例："/data_ware/work_data/dsImgRecognition/models"
        @param  train_model_name  模型名称，示例："01-2-1"
        @param  train_img_size  训练图片大小 a*a，示例：512
        @param  train_batch_size  批次大小，每轮训练的图片数量，示例：4
        @param  train_epochs  训练轮数，示例：10
        @param  train_lr  学习率，示例：0.001
        @param  train_val_ratio  验证集大小，示例：0.1
        @param  train_patience  连续 patience 轮没有提升就强制结束训练，示例：15
        @param  train_pretrain_path  可选预训练模型地址，示例：None
        """
        self.trainImgModuleByUnet(cmd_param['train_img_dirs'],
                            cmd_param['train_label_dirs'],
                            cmd_param['train_model_dir'],
                            cmd_param['train_model_name'],
                            cmd_param['train_map_dir'],
                            cmd_param['train_img_size'],
                            cmd_param['train_batch_size'],
                            cmd_param['train_epochs'],
                            cmd_param['train_lr'],
                            cmd_param['train_val_ratio'],
                            cmd_param['train_patience'],
                            cmd_param['train_pretrain_path']) 

    def classifybatchpredictByUnet(self,cmd_param):
        """
        @param  predict_model_dir  模型地址
        @param  predict_model_name  使用的模型名称
        @param  predict_img_dirs  需要预测的图片的文件夹地址
        @param  predict_label_dirs  标签输出地址
        @param  predict_img_size  图片压缩大小
        """
       
        self.batchpredictByUnet(cmd_param['predict_model_dir'],
                                cmd_param['predict_model_name'],
                                cmd_param['predict_img_dirs'],
                                cmd_param['predict_label_dirs'],
                                cmd_param['predict_img_size']) 

    def classifypredictByUnet(self,cmd_param):
        self.predict(
            cmd_param['model_path'],
            cmd_param['model_name'],
            cmd_param['img_path'],
            cmd_param['out_json_path'],
            cmd_param['img_size']
        )

    def classifyBatchpredictByUnet(self,cmd_param):
        self.batchPredict(cmd_param['model_path'],
                            cmd_param['model_name'],
                            cmd_param['img_dirs'],
                            cmd_param['out_json_dir'],
                            cmd_param['img_size'])

    def dataPreProcess(self, folder_paths):
        """
        检查多个文件夹内的 .jpg/.jpeg/.png 文件是否破损，
        发现损坏文件立即删除，并实时输出结果。
        参数:
            folder_paths: 文件夹路径列表，元素可以是 str 或 Path。
        返回:
            List[Path]: 已删除的损坏文件路径列表（空列表表示全部正常）。
        """
        folders = [Path(p) for p in folder_paths]
        deleted_files = []
        total_files = 0
        for folder in folders:
            if not folder.is_dir():
                print(f"[警告] 跳过无效路径：{folder}")
                continue
            print(f"\n--- 开始检查文件夹：{folder} ---")
            for ext in ("*.jpg", "*.jpeg", "*.png"):
                for file in folder.glob(ext):
                    total_files += 1
                    try:
                        img = cv2.imread(str(file))
                        if img is None:
                            raise ValueError("OpenCV 无法解码")
                        _ = img.shape  # 强制解码
                    except Exception:
                        print(f"[损坏并删除] {file}")
                        file.unlink(missing_ok=True)  # 立即删除
                        deleted_files.append(file)
        print(f"\n===== 检查完成 =====")
        print(f"共扫描 {total_files} 个文件，已删除 {len(deleted_files)} 个损坏文件。")
        return deleted_files

    def trainImgModuleByUnet(self,
                            image_dirs,
                            label_dirs,
                            model_dir,
                            model_name,
                            tmp_dir,
                            img_size=512,
                            batch_size=4,
                            epochs=200,
                            lr=1e-4,
                            val_ratio=0.1,
                            patience=15,
                            pretrain_path=None):
        # 选择最空闲的 GPU
        gpu_id = self._wait_and_pick_free_gpu(threshold=0.6, interval=30)
        device = torch.device(f'cuda:{gpu_id}')

        pathHead=image_dirs[0].rsplit('/',1)[0]
        os.makedirs(model_dir,exist_ok=True)

        # 1. 整理数据
        # tmp_data_dir = Path(tmp_dir) / "dataset"
        test = True
        if test:
            labels_dir  = Path(tmp_dir) / "labels.json"     
        else :
            labels_dir = self.ready_train_dataset(label_dirs, tmp_dir,pathHead)
        
        # 2. 划分训练/验证
        full_ds = ImgClassifyDataset(image_dirs,labels_dir, img_size)
        
        # 获取类别数
        num_classes = full_ds.num_classes
        print(f"检测到 {num_classes} 个类别: {full_ds.unique_codes}")
        
        val_len = int(len(full_ds) * val_ratio)
        train_len = len(full_ds) - val_len
        train_ds, val_ds = random_split(full_ds, [train_len, val_len])
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=4, pin_memory=True)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=4, pin_memory=True)

        # 3. 模型 - 修改为多分类
        model = UNet(n_channels=3, n_classes=num_classes).to(device)  # 关键修改

        # 可选：加载预训练权重（注意兼容性）
        if pretrain_path and Path(pretrain_path).exists():
            state = torch.load(pretrain_path, map_location=device)
            if isinstance(state, dict) and "model_state_dict" in state:
                state = state["model_state_dict"]
            
            # 检查预训练权重是否兼容
            try:
                model.load_state_dict(state, strict=True)
                print(f"成功加载预训练权重：{pretrain_path}")
            except:
                print(f"预训练权重不兼容，将从头训练")
        elif pretrain_path:
            print(f"未找到预训练文件：{pretrain_path}，将从头训练")

        # 修改损失函数为多分类交叉熵损失
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', patience=5, factor=0.5)
        
        best_accuracy = 0  # 改为使用准确率
        counter = 0

        # 4. 训练与验证
        for epoch in range(1, epochs + 1):
            # --- 训练 ---
            model.train()
            running_loss, running_correct, running_total = 0., 0, 0
            
            train_iter = tqdm(train_loader, desc=f'Train {epoch}/{epochs}')
            for imgs, labels in train_iter:  # 注意：现在是labels而不是masks
                imgs, labels = imgs.to(device), labels.to(device)
                
                # 前向传播
                outputs = model(imgs)  # [B, C, H, W]
                
                # 多分类需要调整输出形状
                if outputs.dim() == 4:  # 如果是分割输出 [B, C, H, W]
                    outputs = outputs.mean(dim=[2, 3])  # 全局平均池化 -> [B, C]
                
                loss = criterion(outputs, labels)
                
                # 反向传播
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                # 计算准确率
                _, predicted = torch.max(outputs.data, 1)
                running_total += labels.size(0)
                running_correct += (predicted == labels).sum().item()
                running_loss += loss.item()
                
                # 更新进度条
                train_iter.set_description(f'Train {epoch}/{epochs} Loss: {loss.item():.4f} Acc: {100.*running_correct/running_total:.2f}%')

            avg_loss = running_loss / len(train_loader)
            avg_accuracy = 100. * running_correct / running_total

            # --- 验证 ---
            model.eval()
            val_correct, val_total = 0, 0
            val_loss = 0.
            
            with torch.no_grad():
                for imgs, labels in val_loader:
                    imgs, labels = imgs.to(device), labels.to(device)
                    outputs = model(imgs)
                    
                    if outputs.dim() == 4:
                        outputs = outputs.mean(dim=[2, 3])
                    
                    loss = criterion(outputs, labels)
                    val_loss += loss.item()
                    
                    _, predicted = torch.max(outputs.data, 1)
                    val_total += labels.size(0)
                    val_correct += (predicted == labels).sum().item()
            
            val_accuracy = 100. * val_correct / val_total
            val_loss /= len(val_loader)
            scheduler.step(val_accuracy)

            print(f'Epoch {epoch:03d} | Train Loss: {avg_loss:.4f} | Train Acc: {avg_accuracy:.2f}% | '
                f'Val Loss: {val_loss:.4f} | Val Acc: {val_accuracy:.2f}% | '
                f'LR: {optimizer.param_groups[0]["lr"]:.2e}')
            # 早停 & 最佳模型
            if val_accuracy > best_accuracy:
                best_accuracy = val_accuracy
                counter = 0
                torch.save({
                    'model_state_dict': model.state_dict(),
                    'accuracy': best_accuracy,
                    'epoch': epoch,
                    'class_mapping': full_ds.code_to_idx  # 保存类别映射
                }, Path(model_dir) / f'{model_name}_best.pth')
            else:
                counter += 1
                if counter >= patience:
                    print(f'Early stop at epoch {epoch}')
                    break

            # 保存最新
            torch.save({
                'model_state_dict': model.state_dict(),
                'accuracy': val_accuracy,
                'epoch': epoch,
                'class_mapping': full_ds.code_to_idx
            }, Path(model_dir) / f'{model_name}_latest.pth')

        print(f'训练完成，最佳验证准确率: {best_accuracy:.2f}%')

        # 预测一张图片
   
    def predict(self,
                model_path,
                model_name,  # 传 "" 则保持原路径
                img_path,
                out_json_path,
                img_size=512):
        """
        @param model_path: 模型目录, 如: data/train_model
        @param model_name: 模型文件名, 如: wrinkle_unet_best.pth
        @param img_path: 输入图片路径
        @param out_json_path: 输出分类结果JSON路径
        """
        gpu_id = self._wait_and_pick_free_gpu(threshold=0.6, interval=30)
        device = torch.device(f'cuda:{gpu_id}')
        
        # 0. 拼接最终权重路径
        if model_name:  # 非空才拼接
            model_path = str(Path(model_path) / model_name)
        assert Path(model_path).exists(), f"模型文件不存在：{model_path}"
        
        # 1. 加载模型和类别映射
        checkpoint = torch.load(model_path, map_location=device, weights_only=True)
        
        # 获取类别映射
        if 'class_mapping' in checkpoint:
            class_mapping = checkpoint['class_mapping']
            idx_to_class = {idx: code for code, idx in class_mapping.items()}
            num_classes = len(class_mapping)
        else:
            # 如果没有保存类别映射，需要从其他地方获取或设置默认值
            raise ValueError("模型文件中未找到类别映射信息")
        
        # 创建模型（需要与训练时相同的结构）
        model = UNet(n_channels=3, n_classes=num_classes).to(device)
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()
        
        # 2. 读取并预处理图片（与训练时保持一致）
        img = cv2.imread(img_path)
        assert img is not None, f"无法读取图片：{img_path}"
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # 预处理转换（与训练时保持一致）
        transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((img_size, img_size), interpolation=Image.BILINEAR),
            transforms.ToTensor()
        ])
        
        img_resized = cv2.resize(img_rgb, (img_size, img_size))
        tensor = transform(img_resized).unsqueeze(0).float().to(device)
        
        # 3. 推理
        with torch.no_grad():
            output = model(tensor)
            
            # 处理输出形状（与训练时保持一致）
            if output.dim() == 4:  # [B, C, H, W]
                output = output.mean(dim=[2, 3])  # 全局平均池化 -> [B, C]
            
            # 获取预测结果
            probabilities = torch.softmax(output, dim=1)
            confidence, predicted_idx = torch.max(probabilities, 1)
        
        # 4. 解析结果
        predicted_class_idx = predicted_idx.item()
        confidence_score = confidence.item()
        
        # 将索引映射回原始类别代码
        predicted_class_code = idx_to_class.get(predicted_class_idx, "unknown")
        
        # 5. 保存结果到JSON
        result = {
            "image_path": img_path,
            "predicted_class": predicted_class_code,
            "confidence": round(confidence_score, 4),
            "class_index": predicted_class_idx,
            "all_probabilities": {
                idx_to_class.get(i, "unknown"): round(prob, 4) 
                for i, prob in enumerate(probabilities[0].cpu().numpy())
            }
        }
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(out_json_path) if os.path.dirname(out_json_path) else ".", exist_ok=True)
        
        with open(out_json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"分类预测完成：")
        print(f"  图片：{img_path}")
        print(f"  预测类别：{predicted_class_code}")
        print(f"  置信度：{confidence_score:.4f}")
        print(f"  结果保存至：{out_json_path}")

    def batchPredict(self,
                    model_path,
                    model_name,
                    img_dirs: list,
                    out_json_dir,
                    img_size=512):
        """
        批量预测函数
        """

        # GPU设置
        gpu_id = self._wait_and_pick_free_gpu(threshold=0.6, interval=30)
        device = torch.device(f'cuda:{gpu_id}')
        
        # 模型路径处理
        if model_name:
            model_path = str(Path(model_path) / model_name)
        assert Path(model_path).exists(), f"模型文件不存在：{model_path}"
        
        # 加载模型
        checkpoint = torch.load(model_path, map_location=device, weights_only=True)
        class_mapping = checkpoint['class_mapping']
        idx_to_class = {idx: code for code, idx in class_mapping.items()}
        num_classes = len(class_mapping)
        
        model = UNet(n_channels=3, n_classes=num_classes).to(device)
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()
        
        # 预处理

        transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor()
        ])
        
        # 创建输出目录
        Path(out_json_dir).mkdir(parents=True, exist_ok=True)
        
        # 批量预测
        for img_dir in img_dirs:
            img_dir_path = Path(img_dir)
            if not img_dir_path.exists():
                continue
                
            # 获取图片文件
            img_extensions = ['*.jpg', '*.jpeg', '*.png']
            img_paths = []
            for ext in img_extensions:
                img_paths.extend(img_dir_path.glob(f"**/{ext}"))
            
            if not img_paths:
                continue
                
            all_results = []
            
            for img_path in tqdm(img_paths, desc=f"预测 {img_dir_path.name}"):
                try:
                    img = cv2.imread(str(img_path))
                    if img is None:
                        continue
                        
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    img_resized = cv2.resize(img_rgb, (img_size, img_size))
                    tensor = transform(img_resized).unsqueeze(0).float().to(device)
                    
                    # 推理
                    with torch.no_grad():
                        output = model(tensor)
                        if output.dim() == 4:
                            output = output.mean(dim=[2, 3])
                        
                        probabilities = torch.softmax(output, dim=1)
                        confidence, predicted_idx = torch.max(probabilities, 1)
                    
                    predicted_class_code = idx_to_class.get(predicted_idx.item(), "unknown")
                    
                    result = {
                        "image_path": str(img_path),
                        "predicted_class": predicted_class_code,
                        "confidence": round(confidence.item(), 4),
                        "class_index": predicted_idx.item()
                    }
                    all_results.append(result)
                    
                except Exception:
                    continue
            
            # 保存结果
            if all_results:
                dir_name = img_dir_path.name or "predictions"
                output_json_path = Path(out_json_dir) / f"{dir_name}_predictions.json"
                
                final_result = {
                    "predictions": all_results,
                    "total_images": len(img_paths),
                    "successful_predictions": len(all_results)
                }
                
                with open(output_json_path, 'w', encoding='utf-8') as f:
                    json.dump(final_result, f, indent=2, ensure_ascii=False)
                
                print(f"完成 {dir_name}: {len(all_results)}/{len(img_paths)} 张图片")
        
        print("批量预测完成")
# -------------------------------------------------
# 1. 阻塞直到有空余 GPU，返回最空闲卡物理编号
 # -------------------------------------------------
    def _wait_and_pick_free_gpu(self,threshold=0.6, interval=30):
        """阻塞直到检测到有空余 GPU（显存占用 < threshold），返回最空闲那张卡的物理编号"""
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count == 0:
            raise RuntimeError("未检测到任何 NVIDIA GPU")

        while True:
            best_id, best_free = None, 1.1
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                ratio = info.used / info.total
                if ratio < threshold and ratio < best_free:
                    best_id, best_free = i, ratio

            if best_id is not None:
                pynvml.nvmlShutdown()
                print(f"[GPU] 选择最空闲卡：{best_id}，显存占用 {best_free*100:.1f}%")
                return best_id

            print(f"[GPU] 所有卡显存占用均≥{threshold*100:.0f}%，{interval}s 后重试…")
            time.sleep(interval)

    def clear_jsons(self,label_dirs):
        """
        整理所有目录下的json文件，将所有条目整理到一起
        """


    def ready_train_dataset(self, label_dirs,output_dir,pathHead):
        """
        将多组标签目录整理到 output_dir/labels 
        不再检查可读性或尺寸一致性，仅按文件名匹配后拷贝。
        也就是说,output_dir/labels_output/00000.json
        返回一个字典{img_path:classifycode}
        """
        # 统一为 list[Path]
        # label_dirs  = [Path(label_dirs)]  if isinstance(label_dirs,  (str, Path)) else [Path(d) for d in label_dirs]
        json_files = list(Path(label_dirs).glob('*.json'))

        labels_out  = Path(output_dir) / "labels.json"
        labels_out.parent.mkdir(parents=True, exist_ok=True)

        integrated_map={}

        for label_path in tqdm(json_files):
            with open (label_path,"r") as f:
                data=json.load(f) #data是数组，每个元素是一个字典，每个字典有imgname和classifycode
                for item in data:
                    integrated_map[pathHead.rstrip('/')+'/'+label_path.name.split('.')[0]+'/' + item['imgname']] = item['classifycode']

        with open (labels_out,"w") as f:
            json.dump(integrated_map,f,indent=4)

        print(f"整理完成，存储到{labels_out}")

        return labels_out
