import os
import torch
import glob
import cv2
import numpy as np
from torch import nn
from torch.utils.data import DataLoader
from tqdm import tqdm
from enum import Flag, auto
import shutil
import sys
import signal
import importlib
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # 指向 my_project/
from ..features.module_unet import WrinkleDataset, UNet, WrinkleDatasetFlip, WrinkleDatasetNasolabial
from ..features.common.imgbase import *


class eWrinkleType(Flag):
    NASOLABIAL_FOLD = auto()
    TEAR_THROUGH = auto()


#  Wrinkle 数据训练
# 1、数据下载（syncFilesFromCloud2Local）：data/train_data/wrinkle 目录是从minio同步过来的数据
# 2、数据整理（organize_dataset）：训练之前把数据整理到/tmp目录下
# 3、训练（），训练模型放在 data/train_model下
# 4、预测（），预测结果放在 data/train_data/wrinkle/【皱纹类型】/【GroupName】/dst-mask目录下
# 5、数据上传（）
class CWrinkleImgTrain:
    # def __init__(self):
    def __init__(self, process_comm):
        self.node_cfg = process_comm.getNodeCfg()
        self.tool_module_obj = process_comm.getToolModuleObj()
        self.storage_cloud = process_comm.getStorageCloudObj()
        self.proc_comm = process_comm

    def data_preprocess(self, folder_paths):
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

    def ready_train_dataset(self, image_dirs, mask_dirs, output_dir):
        """
        将多组图像/标签目录整理到 output_dir/images 与 output_dir/masks。
        不再检查可读性或尺寸一致性，仅按文件名匹配后成对拷贝。
        image_dirs / mask_dirs 支持 list / str / Path。
        """
        # 统一为 list[Path]
        image_dirs = [Path(image_dirs)] if isinstance(image_dirs, (str, Path)) else [Path(d) for d in image_dirs]
        mask_dirs = [Path(mask_dirs)] if isinstance(mask_dirs, (str, Path)) else [Path(d) for d in mask_dirs]

        if len(image_dirs) != len(mask_dirs):
            raise ValueError("image_dirs 与 mask_dirs 数量必须相同！")

        images_out = Path(output_dir) / "images"
        masks_out = Path(output_dir) / "masks"
        images_out.mkdir(parents=True, exist_ok=True)
        masks_out.mkdir(parents=True, exist_ok=True)

        copied = 0
        for img_dir, mask_dir in zip(image_dirs, mask_dirs):
            for mask_file in mask_dir.glob("*.png"):
                img_file = img_dir / f"{mask_file.stem}.jpg"
                if not img_file.exists():
                    continue  # 没有对应图片就跳过
                shutil.copy2(img_file, images_out / img_file.name)
                shutil.copy2(mask_file, masks_out / mask_file.name)
                copied += 1

        print(f"[ready_train_dataset] 整理完成：{copied} 对")
        return str(images_out), str(masks_out)

    # -------------------- 训练函数 --------------------
    def dice_loss(self, pred, target):
        smooth = 1e-5
        pred = pred.view(-1)
        target = target.view(-1)
        intersection = (pred * target).sum()
        return 1 - (2. * intersection + smooth) / (pred.sum() + target.sum() + smooth)

    def trainImgModuleByUnet(self,
                             image_dirs,
                             mask_dirs,
                             model_dir,
                             model_name,
                             tmp_dir,
                             img_size=512,
                             batch_size=4,
                             epochs=50,
                             lr=1e-4,
                             device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')):
        """
        端到端：先整理数据 → 再训练 U-Net

        参数
        ----
        image_dirs : list[str] | str   原图目录或目录列表
        mask_dirs  : list[str] | str   掩码目录或目录列表
        model_dir  : str               模型保存根目录
        model_name : str               模型文件前缀
        tmp_root   : str               临时数据根目录（整理后的 images/masks 放在这里）
        其余参数与先前一致
        """
        torch.cuda.empty_cache()
        torch.cuda.set_device(0)
        # 1) 统一整理数据
        tmp_data_dir = Path(tmp_dir) / f"dataset"
        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        images_dir, masks_dir = self.ready_train_dataset(
            image_dirs, mask_dirs, str(tmp_data_dir)
        )

        # 2) 构造数据集 & 加载器
        train_ds = WrinkleDatasetFlip(images_dir, masks_dir, img_size)
        train_loader = DataLoader(train_ds,
                                  batch_size=batch_size,
                                  shuffle=True,
                                  num_workers=4,
                                  pin_memory=True)

        # 3) 模型 & 优化器
        if "single_gpu" == "single_gpu":
            model = UNet().to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        bce = torch.nn.BCELoss()

        # 4) 训练循环
        for epoch in range(epochs):
            model.train()
            epoch_loss = 0
            for imgs, masks in tqdm(train_loader, desc=f'Epoch {epoch + 1}/{epochs}'):
                imgs, masks = imgs.to(device), masks.to(device)
                preds = model(imgs)
                loss = bce(preds, masks) + self.dice_loss(preds, masks)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()

            print(f'Epoch {epoch + 1} | Loss: {epoch_loss / len(train_loader):.4f}')
            # 5) 每 10 个 epoch 保存一次
            # if (epoch + 1) % 10 == 0:
            if 1 == 1:
                save_path = Path(model_dir) / f"{model_name}_epoch{epoch + 1}.pth"
                save_path.parent.mkdir(parents=True, exist_ok=True)
                torch.save(model.state_dict(), save_path)

    # 这是训练皱纹迭代的写法，请看下面的法令纹(粗纹)和鱼尾纹(细纹)的写法
    def trainImgModuleByUnetIterator(self,
                                     image_dirs,
                                     mask_dirs,
                                     model_dir,
                                     model_name,
                                     model_pretrain_path=None,
                                     model_checkpoint_path=None,
                                     tmp_dir="./tmp",
                                     img_size=512,
                                     batch_size=4,
                                     epochs=50,
                                     lr=1e-4,
                                     device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')):
        """
        支持断点续训（优先加载 checkpoint，其次加载预训练权重）
        """

        torch.cuda.empty_cache()
        torch.cuda.set_device(1)

        # 1) 数据准备
        tmp_data_dir = Path(tmp_dir) / "dataset"
        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        images_dir, masks_dir = self.ready_train_dataset(image_dirs, mask_dirs, str(tmp_data_dir))

        train_ds = WrinkleDatasetFlip(images_dir, masks_dir, img_size)
        train_loader = DataLoader(train_ds,
                                  batch_size=batch_size,
                                  shuffle=True,
                                  num_workers=1,
                                  pin_memory=True)

        # 2) 模型、优化器、损失
        model = UNet().to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        bce = torch.nn.BCELoss()

        start_epoch = 0

        # 3) 优先加载 checkpoint
        if model_checkpoint_path and Path(model_checkpoint_path).exists():
            checkpoint = torch.load(model_checkpoint_path, map_location=device)
            model.load_state_dict(checkpoint["model_state_dict"])
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            start_epoch = checkpoint["epoch"] + 1
            print(f"[Resume] 从 {model_checkpoint_path} 恢复，继续训练 Epoch {start_epoch}/{epochs}")

        # 4) 否则加载预训练权重
        elif model_pretrain_path and Path(model_pretrain_path).exists():
            if "bubaoliu_youhuaqi" != "bubaoliu_youhuaqi":
                state = torch.load(model_pretrain_path, map_location=device)
                if isinstance(state, dict) and "model_state_dict" in state:
                    state = state["model_state_dict"]
                model.load_state_dict(state)
                print(f"[Init] 从预训练权重 {model_pretrain_path} 加载模型")
            if "baoliu_youhuaqi" == "baoliu_youhuaqi":  # 保留优化器-迭代训练应该需要的
                checkpoint = torch.load(model_checkpoint_path, map_location=device)
                model.load_state_dict(checkpoint["model_state_dict"])
                optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
                start_epoch = checkpoint["epoch"] + 1
                print(f"[Resume] 从 {model_checkpoint_path} 恢复，继续训练 Epoch {start_epoch}/{epochs}")

        # 中断保存
        interrupted = False

        def handle_interrupt(sig, frame):
            nonlocal interrupted
            interrupted = True
            print("\n[Warning] 检测到中断信号，保存当前进度后退出...")

        signal.signal(signal.SIGINT, handle_interrupt)

        # 5) 训练循环
        for epoch in range(start_epoch, epochs):
            model.train()
            epoch_loss = 0.0

            for imgs, masks in tqdm(train_loader, desc=f"Epoch {epoch + 1}/{epochs}"):
                imgs, masks = imgs.to(device), masks.to(device)
                preds = model(imgs)
                loss = bce(preds, masks) + self.dice_loss(preds, masks)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()

            print(f"Epoch {epoch + 1} | Loss: {epoch_loss / len(train_loader):.4f}")

            # 6) 保存 checkpoint（只保存最后一次）
            latest_ckpt = Path(model_checkpoint_path)
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict()
            }, latest_ckpt)
            print(f"[Save] 最新 checkpoint 保存到: {latest_ckpt}")

            # 7) 每5轮保存一个模型到model_dir
            if (epoch + 1) % 5 == 0:  # epoch 从 0 开始，所以加1更直观
                model_save_dir = Path(model_dir)
                model_save_dir.mkdir(parents=True, exist_ok=True)

                save_path = model_save_dir / f"{model_name}_epoch{epoch + 1}.pth"
                torch.save({
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict()
                }, save_path)
                print(f"[Save] checkpoint 保存到: {save_path}")

            # 如果被 Ctrl+C 触发中断，直接退出
            if interrupted:
                break

        print("[Done] 训练结束")

    # 这里先把数据集部分改掉, 变成动态加载
    def trainImgModuleByUnetIteratorYuweiwen(self,
                                             image_dirs,
                                             mask_dirs,
                                             model_dir,
                                             model_name,
                                             model_pretrain_path=None,
                                             model_checkpoint_path=None,
                                             model_dataset_name="WrinkleDatasetFlip",
                                             tmp_dir="./tmp",
                                             img_size=512,
                                             batch_size=4,
                                             epochs=50,
                                             lr=1e-4,
                                             device=torch.device('cuda' if torch.cuda.is_available() else 'cpu'),
                                             gpu_id=1):
        """
        支持断点续训（优先加载 checkpoint，其次加载预训练权重）
        """

        torch.cuda.empty_cache()
        torch.cuda.set_device(gpu_id)

        # 1) 数据准备
        tmp_data_dir = Path(tmp_dir) / "dataset"
        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        tmp_model_pretrain_path = Path(os.path.dirname(model_pretrain_path))
        tmp_model_pretrain_path.mkdir(parents=True, exist_ok=True)
        tmp_model_checkpoint_path = Path(os.path.dirname(model_checkpoint_path))
        tmp_model_checkpoint_path.mkdir(parents=True, exist_ok=True)

        images_dir, masks_dir = self.ready_train_dataset(image_dirs, mask_dirs, str(tmp_data_dir))

        # train_ds = WrinkleDatasetFlip(images_dir, masks_dir, img_size) # WrinkleDatasetNasolabial , 从配置文件动态导入
        module = importlib.import_module("features.module_unet")  # 动态加载
        train_ds = getattr(module, model_dataset_name)
        train_ds = train_ds(images_dir, masks_dir, img_size)

        train_loader = DataLoader(train_ds,
                                  batch_size=batch_size,
                                  shuffle=True,
                                  num_workers=1,
                                  pin_memory=True)

        # 2) 模型、优化器、损失
        model = UNet().to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        bce = torch.nn.BCELoss()

        start_epoch = 0

        # 3) 优先加载 checkpoint
        if model_checkpoint_path and Path(model_checkpoint_path).exists():
            checkpoint = torch.load(model_checkpoint_path, map_location=device)
            model.load_state_dict(checkpoint["model_state_dict"])
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            start_epoch = checkpoint["epoch"] + 1
            print(f"[Resume] 从 {model_checkpoint_path} 恢复，继续训练 Epoch {start_epoch}/{epochs}")

        # 4) 否则加载预训练权重
        elif model_pretrain_path and Path(model_pretrain_path).exists():
            if "bubaoliu_youhuaqi" != "bubaoliu_youhuaqi":
                state = torch.load(model_pretrain_path, map_location=device)
                if isinstance(state, dict) and "model_state_dict" in state:
                    state = state["model_state_dict"]
                model.load_state_dict(state)
                print(f"[Init] 从预训练权重 {model_pretrain_path} 加载模型")
            if "baoliu_youhuaqi" == "baoliu_youhuaqi":  # 保留优化器-迭代训练应该需要的
                checkpoint = torch.load(model_checkpoint_path, map_location=device)
                model.load_state_dict(checkpoint["model_state_dict"])
                optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
                start_epoch = checkpoint["epoch"] + 1
                print(f"[Resume] 从 {model_checkpoint_path} 恢复，继续训练 Epoch {start_epoch}/{epochs}")

        # 中断保存
        interrupted = False

        def handle_interrupt(sig, frame):
            nonlocal interrupted
            interrupted = True
            print("\n[Warning] 检测到中断信号，保存当前进度后退出...")

        signal.signal(signal.SIGINT, handle_interrupt)

        # 5) 训练循环
        for epoch in range(start_epoch, epochs):
            model.train()
            epoch_loss = 0.0

            for imgs, masks in tqdm(train_loader, desc=f"Epoch {epoch + 1}/{epochs}"):
                imgs, masks = imgs.to(device), masks.to(device)
                preds = model(imgs)
                loss = bce(preds, masks) + self.dice_loss(preds, masks)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()

            print(f"Epoch {epoch + 1} | Loss: {epoch_loss / len(train_loader):.4f}")

            # 6) 保存 checkpoint（只保存最后一次）
            latest_ckpt = Path(model_checkpoint_path)
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict()
            }, latest_ckpt)
            print(f"[Save] 最新 checkpoint 保存到: {latest_ckpt}")

            # 7) 每5轮保存一个模型到model_dir
            if (epoch + 1) % 5 == 0:  # epoch 从 0 开始，所以加1更直观
                model_save_dir = Path(model_dir)
                model_save_dir.mkdir(parents=True, exist_ok=True)

                save_path = model_save_dir / f"{model_name}_epoch{epoch + 1}.pth"
                torch.save({
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict()
                }, save_path)
                print(f"[Save] checkpoint 保存到: {save_path}")

            # 如果被 Ctrl+C 触发中断，直接退出
            if interrupted:
                break

        print("[Done] 训练结束")

    # 这里先把数据集部分改掉, 变成动态加载
    def trainImgModuleByUnetIteratorFalingwen(self,
                                              image_dirs,
                                              mask_dirs,
                                              model_dir,
                                              model_name,
                                              model_pretrain_path=None,
                                              model_checkpoint_path=None,
                                              model_dataset_name="WrinkleDatasetFlip",
                                              tmp_dir="./tmp",
                                              img_size=512,
                                              batch_size=4,
                                              epochs=50,
                                              lr=1e-4,
                                              device=torch.device('cuda' if torch.cuda.is_available() else 'cpu'),
                                              gpu_id=1):
        """
        支持断点续训（优先加载 checkpoint，其次加载预训练权重）
        """

        torch.cuda.empty_cache()
        torch.cuda.set_device(gpu_id)

        # 1) 数据准备
        tmp_data_dir = Path(tmp_dir) / "dataset"
        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        tmp_model_pretrain_path = Path(os.path.dirname(model_pretrain_path))
        tmp_model_pretrain_path.mkdir(parents=True, exist_ok=True)
        tmp_model_checkpoint_path = Path(os.path.dirname(model_checkpoint_path))
        tmp_model_checkpoint_path.mkdir(parents=True, exist_ok=True)

        images_dir, masks_dir = self.ready_train_dataset(image_dirs, mask_dirs, str(tmp_data_dir))

        # train_ds = WrinkleDatasetFlip(images_dir, masks_dir, img_size) # WrinkleDatasetNasolabial , 从配置文件动态导入
        module = importlib.import_module("features.module_unet")  # 动态加载
        train_ds = getattr(module, model_dataset_name)
        train_ds = train_ds(images_dir, masks_dir, img_size)

        train_loader = DataLoader(train_ds,
                                  batch_size=batch_size,
                                  shuffle=True,
                                  num_workers=1,
                                  pin_memory=True)

        # 2) 模型、优化器、损失
        model = UNet().to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        bce = torch.nn.BCELoss()

        start_epoch = 0

        # 3) 优先加载 checkpoint
        if model_checkpoint_path and Path(model_checkpoint_path).exists():
            checkpoint = torch.load(model_checkpoint_path, map_location=device)
            model.load_state_dict(checkpoint["model_state_dict"])
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            start_epoch = checkpoint["epoch"] + 1
            print(f"[Resume] 从 {model_checkpoint_path} 恢复，继续训练 Epoch {start_epoch}/{epochs}")

        # 4) 否则加载预训练权重
        elif model_pretrain_path and Path(model_pretrain_path).exists():
            if "bubaoliu_youhuaqi" != "bubaoliu_youhuaqi":
                state = torch.load(model_pretrain_path, map_location=device)
                if isinstance(state, dict) and "model_state_dict" in state:
                    state = state["model_state_dict"]
                model.load_state_dict(state)
                print(f"[Init] 从预训练权重 {model_pretrain_path} 加载模型")
            if "baoliu_youhuaqi" == "baoliu_youhuaqi":  # 保留优化器-迭代训练应该需要的
                checkpoint = torch.load(model_checkpoint_path, map_location=device)
                model.load_state_dict(checkpoint["model_state_dict"])
                optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
                start_epoch = checkpoint["epoch"] + 1
                print(f"[Resume] 从 {model_checkpoint_path} 恢复，继续训练 Epoch {start_epoch}/{epochs}")

        # 中断保存
        interrupted = False

        def handle_interrupt(sig, frame):
            nonlocal interrupted
            interrupted = True
            print("\n[Warning] 检测到中断信号，保存当前进度后退出...")

        signal.signal(signal.SIGINT, handle_interrupt)

        # 5) 训练循环
        for epoch in range(start_epoch, epochs):
            model.train()
            epoch_loss = 0.0

            for imgs, masks in tqdm(train_loader, desc=f"Epoch {epoch + 1}/{epochs}"):
                imgs, masks = imgs.to(device), masks.to(device)
                preds = model(imgs)
                loss = bce(preds, masks) + self.dice_loss(preds, masks)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()

            print(f"Epoch {epoch + 1} | Loss: {epoch_loss / len(train_loader):.4f}")

            # 6) 保存 checkpoint（只保存最后一次）
            latest_ckpt = Path(model_checkpoint_path)
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict()
            }, latest_ckpt)
            print(f"[Save] 最新 checkpoint 保存到: {latest_ckpt}")

            # 7) 每5轮保存一个模型到model_dir
            if (epoch + 1) % 5 == 0:  # epoch 从 0 开始，所以加1更直观
                model_save_dir = Path(model_dir)
                model_save_dir.mkdir(parents=True, exist_ok=True)

                save_path = model_save_dir / f"{model_name}_epoch{epoch + 1}.pth"
                torch.save({
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict()
                }, save_path)
                print(f"[Save] checkpoint 保存到: {save_path}")

            # 如果被 Ctrl+C 触发中断，直接退出
            if interrupted:
                break

        print("[Done] 训练结束")

    # 预测一张图片
    def predict(self, model_path, img_path, out_mask_path, out_vis_path, img_size=512, device='cuda'):
        """
        @param model_path: 模型路径,如:tool_dev/ds_ai_svr/toolbox/data/train_model/unet_epoch50.pth
        @param img_path: 输入图片目录,如:tool_dev/ds_ai_svr/toolbox/data/train_data/wrinkle/src-img/00000/1.jpg
        @param out_mask_path: 输出目录,如:tool_dev/ds_ai_svr/toolbox/data/train_data/wrinkle/dst-mask/00000/1.png
        @param out_vis_path: 可视化目录,如:tool_dev/ds_ai_svr/toolbox/data/train_data/wrinkle/dst-combine/00000/1_combine.png
        """
        device = torch.device(device if torch.cuda.is_available() else 'cpu')

        # 1. 加载模型
        model = UNet(n_channels=3, n_classes=1).to(device)
        model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
        model.eval()

        # 2. 读取并预处理
        img = cv2.imread(img_path)
        assert img is not None, f"无法读取图片：{img_path}"
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_res = cv2.resize(img_rgb, (img_size, img_size))
        tensor = torch.from_numpy(img_res / 255.).permute(2, 0, 1).unsqueeze(0).float().to(device)

        # 3. 推理
        with torch.no_grad():
            pred = model(tensor)[0, 0].cpu().numpy()
        mask = (pred > 0.5).astype(np.uint8) * 255

        # 4. 保存结果（路径已完整由调用者给出）
        os.makedirs(os.path.dirname(out_mask_path), exist_ok=True)
        os.makedirs(os.path.dirname(out_vis_path), exist_ok=True)

        cv2.imwrite(out_mask_path, mask)

        # 5. 可视化叠加
        mask_big = cv2.resize(mask, (img.shape[1], img.shape[0]))
        overlay = img.copy()
        overlay[..., 2] = np.where(mask_big > 127, 255, overlay[..., 2])
        vis = cv2.addWeighted(overlay, 0.5, img, 0.5, 0)
        cv2.imwrite(out_vis_path, vis)

        print(f"已保存：\n  掩膜 -> {out_mask_path}\n  可视化 -> {out_vis_path}")

    # 预测细纹(抬头纹、鱼尾纹等)
    def predictSingleXiwen(self, model_path, img_path, out_mask_path, out_vis_path, img_size=1024, device='cuda',
                           gpu_id=0):
        # 设备选择
        device = torch.device(device if torch.cuda.is_available() else 'cpu')

        if torch.cuda.is_available():
            torch.cuda.set_device(gpu_id)

        # 1. 加载模型
        model = UNet(n_channels=3, n_classes=1).to(device)
        state = torch.load(model_path, map_location=device)
        # 如果是 checkpoint（包含 model_state_dict），就取出权重
        if isinstance(state, dict) and "model_state_dict" in state:
            state = state["model_state_dict"]

        # 再加载到模型
        missing_unexpected = model.load_state_dict(state)
        model.eval()

        # 预测
        # 3. 逐张预测
        img = cv2.imread(img_path)

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h0, w0 = img.shape[:2]
        patch_size = img_size

        # 分块数量（至少为 1，避免小图报错）
        num_w = max(1, (w0 + patch_size - 1) // patch_size)
        num_h = max(1, (h0 + patch_size - 1) // patch_size)

        # 创建空 mask
        full_mask = np.zeros((num_h * patch_size, num_w * patch_size), dtype=np.uint8)
        idx = 0
        for i in range(num_h):
            y1 = i * patch_size
            y2 = min(y1 + patch_size, h0)
            for j in range(num_w):
                idx += 1
                x1 = j * patch_size
                x2 = min(x1 + patch_size, w0)

                # 裁剪 patch
                img_patch = img_rgb[y1:y2, x1:x2, :]

                # patch 不够大就 pad
                if img_patch.shape[0] != patch_size or img_patch.shape[1] != patch_size:
                    padded = np.zeros((patch_size, patch_size, 3), dtype=img_patch.dtype)
                    padded[:img_patch.shape[0], :img_patch.shape[1], :] = img_patch
                    img_patch = padded

                # 转 tensor
                tensor = torch.from_numpy(img_patch / 255.).permute(2, 0, 1).unsqueeze(0).float().to(device)

                # 预测
                with torch.no_grad():
                    pred = model(tensor)[0, 0].cpu().numpy()

                # 二值化
                mask_patch = (pred > 0.5).astype(np.uint8) * 255

                # 放回对应位置
                # full_mask[i * patch_size:(i + 1) * patch_size, j * patch_size:(j + 1) * patch_size] = mask_patch
                valid_h = min(patch_size, h0 - i * patch_size)
                valid_w = min(patch_size, w0 - j * patch_size)
                full_mask[i * patch_size:i * patch_size + valid_h,
                j * patch_size:j * patch_size + valid_w] = mask_patch[:valid_h, :valid_w]

        # 裁剪到原图大小
        full_mask = full_mask[:h0, :w0]

        # resize 回原图大小（确保对齐）
        full_mask_resized = cv2.resize(full_mask, (w0, h0), interpolation=cv2.INTER_NEAREST)

        # 转换成彩色 mask
        redMask = readMaskFromPng(full_mask_resized)

        # 保存
        cv2.imwrite(out_mask_path, full_mask_resized)
        # cv2.imwrite(out_vis_path, redMask)

    # 预测细纹(抬头纹、鱼尾纹等)
    def predictImgModuleByUnet(self, model_dir, model_name, img_dir, out_put_dir, img_size=1024, device='cuda',
                               gpu_id=0):
        # 设备选择
        device = torch.device(device if torch.cuda.is_available() else 'cpu')

        if torch.cuda.is_available():
            torch.cuda.set_device(gpu_id)

        # 输出目录
        path = Path(img_dir)
        last_folder = path.name
        full_model_path = os.path.join(model_dir, model_name)
        out_mask_dir = Path(out_put_dir) / last_folder / "src-mask"
        out_mask_dir.mkdir(parents=True, exist_ok=True)

        # 1. 加载模型
        model = UNet(n_channels=3, n_classes=1).to(device)
        state = torch.load(full_model_path, map_location=device)
        # 如果是 checkpoint（包含 model_state_dict），就取出权重
        if isinstance(state, dict) and "model_state_dict" in state:
            state = state["model_state_dict"]

        # 再加载到模型
        missing_unexpected = model.load_state_dict(state)
        model.eval()

        # 2. 扫描图片
        img_paths = [p for p in glob.glob(os.path.join(img_dir, '*')) if
                     p.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]

        # 3. 逐张预测
        idx = 0
        for img_path in tqdm(img_paths, desc='Predicting'):
            img = cv2.imread(img_path)
            if img is None:
                continue

            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h0, w0 = img.shape[:2]
            patch_size = img_size

            # 分块数量（至少为 1，避免小图报错）
            num_w = max(1, (w0 + patch_size - 1) // patch_size)
            num_h = max(1, (h0 + patch_size - 1) // patch_size)

            # 创建空 mask
            full_mask = np.zeros((num_h * patch_size, num_w * patch_size), dtype=np.uint8)

            for i in range(num_h):
                y1 = i * patch_size
                y2 = min(y1 + patch_size, h0)
                for j in range(num_w):
                    idx += 1
                    x1 = j * patch_size
                    x2 = min(x1 + patch_size, w0)

                    # 裁剪 patch
                    img_patch = img_rgb[y1:y2, x1:x2, :]

                    # patch 不够大就 pad
                    if img_patch.shape[0] != patch_size or img_patch.shape[1] != patch_size:
                        padded = np.zeros((patch_size, patch_size, 3), dtype=img_patch.dtype)
                        padded[:img_patch.shape[0], :img_patch.shape[1], :] = img_patch
                        img_patch = padded

                    # 转 tensor
                    tensor = torch.from_numpy(img_patch / 255.).permute(2, 0, 1).unsqueeze(0).float().to(device)

                    # 预测
                    with torch.no_grad():
                        pred = model(tensor)[0, 0].cpu().numpy()

                    # 二值化
                    mask_patch = (pred > 0.2).astype(np.uint8) * 255

                    # 放回对应位置
                    # full_mask[i * patch_size:(i + 1) * patch_size, j * patch_size:(j + 1) * patch_size] = mask_patch
                    valid_h = min(patch_size, h0 - i * patch_size)
                    valid_w = min(patch_size, w0 - j * patch_size)
                    full_mask[i * patch_size:i * patch_size + valid_h,
                    j * patch_size:j * patch_size + valid_w] = mask_patch[:valid_h, :valid_w]

            # 裁剪到原图大小
            full_mask = full_mask[:h0, :w0]

            # resize 回原图大小（确保对齐）
            full_mask_resized = cv2.resize(full_mask, (w0, h0), interpolation=cv2.INTER_NEAREST)

            # 转换成彩色 mask
            redMask = readMaskFromPng(full_mask_resized)

            # 保存
            basename = os.path.splitext(os.path.basename(img_path))[0]
            save_path = os.path.join(out_mask_dir, f'{basename}.png')
            cv2.imwrite(save_path, redMask)

        print(f'Done! 共处理 {len(img_paths)} 张图片')

    # 预测粗纹(法令纹、泪沟等)
    def predictImgModuleByUnetNasolabial(self, model_dir, model_name, img_dir, out_put_dir, img_size=1024,
                                         device='cuda', gpu_id=0):
        # 设备选择
        device = torch.device(device if torch.cuda.is_available() else 'cpu')

        if torch.cuda.is_available():
            torch.cuda.set_device(gpu_id)

        # 输出目录
        path = Path(img_dir)
        last_folder = path.name
        full_model_path = os.path.join(model_dir, model_name)
        out_mask_dir = Path(out_put_dir) / last_folder / "src-mask"
        out_mask_dir.mkdir(parents=True, exist_ok=True)

        # 1. 加载模型
        model = UNet(n_channels=3, n_classes=1).to(device)
        state = torch.load(full_model_path, map_location=device)
        # 如果是 checkpoint（包含 model_state_dict），就取出权重
        if isinstance(state, dict) and "model_state_dict" in state:
            state = state["model_state_dict"]

        # 再加载到模型
        missing_unexpected = model.load_state_dict(state)
        model.eval()

        # 2. 扫描图片
        img_paths = [p for p in glob.glob(os.path.join(img_dir, '*')) if
                     p.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]

        # 3. 逐张预测
        idx = 0
        for img_path in tqdm(img_paths, desc='Predicting'):
            img = cv2.imread(img_path)
            if img is None:
                continue

            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h0, w0 = img.shape[:2]
            img_predict_resize = cv2.resize(img_rgb, (img_size, img_size))

            # 转 tensor
            tensor = torch.from_numpy(img_predict_resize / 255.).permute(2, 0, 1).unsqueeze(0).float().to(device)

            # 预测
            with torch.no_grad():
                pred = model(tensor)[0, 0].cpu().numpy()

            # 二值化
            mask_predict = (pred > 0.2).astype(np.uint8) * 255

            # resize 回原图大小（确保对齐）
            full_mask_resized = cv2.resize(mask_predict, (w0, h0), interpolation=cv2.INTER_NEAREST)

            # 转换成彩色 mask
            redMask = readMaskFromPng(full_mask_resized)

            # 保存
            basename = os.path.splitext(os.path.basename(img_path))[0]
            save_path = os.path.join(out_mask_dir, f'{basename}.png')
            cv2.imwrite(save_path, redMask)

        print(f'Done! 共处理 {len(img_paths)} 张图片')


if __name__ == '__main__':
    cwrinkleimgtrain = CWrinkleImgTrain()
    # cwrinkleimgtrain.organize_dataset(
    #   image_dir="/home/gugm/workcode/tool_dev/ds_ai_svr/toolbox/data/train_data/wrinkle/src-img/00000",
    #  mask_dir="/home/gugm/workcode/tool_dev/ds_ai_svr/toolbox/data/train_data/wrinkle/nasolabial_fold/00000/src-mask",
    # output_dir="/home/gugm/workcode/tool_dev/ds_ai_svr/toolbox/data/tmp"
    # )
    cwrinkleimgtrain.trainImgModuleByUnet(data_dir='/home/gugm/workcode/tool_dev/ds_ai_svr/toolbox/data/tmp',
                                          save_root="/home/gugm/workcode/tool_dev/ds_ai_svr/toolbox/data/train_model",
                                          img_size=512, batch_size=4, epochs=50, lr=1e-4)
    # cwrinkleimgtrain.predictImgModuleByUnet('/home/gugm/workcode/tool_dev/ds_ai_svr/toolbox/data/train_model/unet_epoch30.pth',
    #              '/home/gugm/workcode/tool_dev/ds_ai_svr/toolbox/data/train_data/wrinkle/src-img/00001',
    #              '/home/gugm/workcode/tool_dev/ds_ai_svr/toolbox/data/train_data/wrinkle/nasolabial_fold/00001/dst-mask',
    #              img_size=512)
