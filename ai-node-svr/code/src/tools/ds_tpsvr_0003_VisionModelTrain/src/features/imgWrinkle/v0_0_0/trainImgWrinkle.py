"""
璁粌鐨辩汗妯″瀷: 
trainSlimImgModuleByUnetIterator: 缁嗙汗妯″瀷Pytorch
trainBoldImgModuleByUnetIterator: 绮楃汗妯″瀷Pytorch

"""
import os
import torch
import glob
import cv2
import numpy as np
import requests
import shutil
import time
import pynvml  # nvidia-ml-py3
import torch.nn.functional as F
from torch.utils.data import DataLoader, random_split
from tqdm import tqdm
from pathlib import Path
import importlib
import random
from src.features.imgWrinkle.v0_0_0.module_unet import UNet
from src.features.common.imgbase import *
import warnings
from urllib.parse import urlparse
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")
from src.SysLogger import CSysLogger
logger = CSysLogger("trainImgWrinkle")

"""
璇锋眰鏍煎紡锛?{
    "FunDesc": "cskin鐨辩汗妯″瀷璁粌鈥斺€旀暟鎹澶勭悊",
    "ReqParam": {
        "dtype": "wrinkledataPreProcess",
        "folder_paths": [
            "/data_ware/work_data/cskin_wrinkle/src-img/00000/",
            "/data_ware/work_data/cskin_wrinkle/src-img/00001/",
            "/data_ware/work_data/cskin_wrinkle/nasolabial_fold/00000/src-mask/",
            "/data_ware/work_data/cskin_wrinkle/nasolabial_fold/00001/src-mask/"
        ]
}

{
    "FunDesc": "cskin鐨辩汗妯″瀷璁粌鈥斺€旇缁?,
    "ReqParam": {
        "dtype": "wrinkletrainImgModuleByUnet",
        "train_img_dirs": [
            "data/train_data/wrinkle/00",
            "data/train_data/wrinkle/01"
        ],
        "train_mask_dirs": [
            "data/train_data/wrinkle/00",
            "data/train_data/wrinkle/01"
        ],
        "train_model_dir": "data/train_model",
        "train_model_name": "wrinkle_model.pth",
        "tmp_data": "/tmp/wrinkle_train",
        "train_img_size": 256,
        "train_batch_size": 4,
        "train_epochs": 100,
        "train_lr": 0.001,
        "train_val_ratio": 0.2,
        "train_patience": 4,
        "train_pretrain_path": "data/train_model/wrinkle_model.pth"
    }
}

{
    "FunDesc": "cskin鐨辩汗妯″瀷璁粌鈥斺€旀壒閲忛娴?,
    "ReqParam": {
        "dtype": "wrinklebatchpredictByUnet",
        "use_gpu": true,
        "predict_model_dir": "data/train_model",
        "predict_model_name": "wrinkle_model.pth",
        "predict_img_dirs": [
            "data/train_data/wrinkle/00000",
            "data/train_data/wrinkle/00001"
        ],
        "predict_out_mask_dirs": [
            "data/train_data/wrinkle/00000/dst-mask",
            "data/train_data/wrinkle/00001/dst-mask"
        ],
        "predict_out_vis_dirs": [
            "data/train_data/wrinkle/00000/dst-vis",
            "data/train_data/wrinkle/00001/dst-vis"
        ],  
        "predict_img_size": 256
    }
}

"""

#  Wrinkle 鏁版嵁璁粌
# 1銆佹暟鎹笅杞斤紙syncFilesFromCloud2Local锛夛細data/train_data/wrinkle 鐩綍鏄粠minio鍚屾杩囨潵鐨勬暟鎹?
# 2銆佹暟鎹暣鐞嗭紙organize_dataset锛夛細璁粌涔嬪墠鎶婃暟鎹暣鐞嗗埌/tmp鐩綍涓?
# 3銆佽缁冿紙锛夛紝璁粌妯″瀷鏀惧湪 data/train_model涓?# 4銆侀娴嬶紙锛夛紝棰勬祴缁撴灉鏀惧湪 data/train_data/wrinkle/銆愮毐绾圭被鍨嬨€?銆怗roupName銆?dst-mask鐩綍涓?# 5銆佹暟鎹笂浼狅紙锛?class CTrainImgWrinkle:
    # def __init__(self):
    def __init__(self, node_cfg, process_comm, proc_modules_obj, progress_callback):
        self.node_cfg = node_cfg
        self.process_comm = process_comm
        self.proc_modules_obj = proc_modules_obj
        self.progress_callback = progress_callback

         
    #
    def checkPreFileValid(self, cmd_param):
        self.proc_modules_obj['imgbase'].checkPreFileValid(cmd_param['folder_paths'])


    def ready_train_dataset(self, image_dirs, mask_dirs, tmp_data_dir):
        """
        灏嗗缁勫浘鍍?鏍囩鐩綍鏁寸悊鍒?enhance_image_dir 涓?enhance_mask_dir銆?        涓嶅啀妫€鏌ュ彲璇绘€ф垨灏哄涓€鑷存€э紝浠呮寜鏂囦欢鍚嶅尮閰嶅悗鎴愬鎷疯礉銆?        image_dirs / mask_dirs 鏀寔 list / str / Path銆?        """
        # 缁熶竴涓?list[Path]
        image_dirs = [Path(image_dirs)] if isinstance(image_dirs, (str, Path)) else [Path(d) for d in image_dirs]
        mask_dirs  = [Path(mask_dirs)]  if isinstance(mask_dirs,  (str, Path)) else [Path(d) for d in mask_dirs]

        if len(image_dirs) != len(mask_dirs):
            raise ValueError("image_dirs 涓?mask_dirs 鏁伴噺蹇呴』鐩稿悓锛?)

        images_out = Path(tmp_data_dir) / "images"
        masks_out  = Path(tmp_data_dir) / "masks"
        images_out.mkdir(parents=True, exist_ok=True)
        masks_out.mkdir(parents=True, exist_ok=True)

        copied = 0
        for idx, (img_dir, mask_dir) in enumerate(zip(image_dirs, mask_dirs)):
            mask_files = list(mask_dir.glob("*.png"))
            self.progress_callback((idx/len(image_dirs)*100), 'Organizing file format.')
            for mask_file in mask_files:
                img_file = img_dir / f"{mask_file.stem}.jpg"
                if not img_file.exists():
                    continue  # 娌℃湁瀵瑰簲鍥剧墖灏辫烦杩?                shutil.copy2(img_file,  images_out / img_file.name)
                shutil.copy2(mask_file, masks_out  / mask_file.name)
                copied += 1

        print(f"[ready_train_dataset] 鏁寸悊瀹屾垚锛歿copied} 瀵?)
        return str(images_out), str(masks_out)

    def dice_loss(self, pred, target):
        smooth = 1e-5
        pred   = pred.view(-1)
        target = target.view(-1)
        intersection = (pred * target).sum()
        return 1 - (2. * intersection + smooth) / (pred.sum() + target.sum() + smooth)

    # 鍔犺浇鍗曚釜鎴栬€呭涓ā鍨?    def load_models(self, model_paths, device="cuda", gpu_id=0):
        # 璁惧閫夋嫨
        if torch.cuda.is_available() and device.startswith("cuda"):
            torch.cuda.set_device(gpu_id)
            device = torch.device(f"cuda:{gpu_id}")
        else:
            device = torch.device("cpu")

        models = []
        for mp in model_paths:
            model = UNet(n_channels=3, n_classes=1).to(device)
            state = torch.load(mp, map_location=device)
            if isinstance(state, dict) and "model_state_dict" in state:
                state = state["model_state_dict"]
            model.load_state_dict(state)
            model.eval()
            models.append(model)

        return models, device


    """////---------------------------------------------------------------------------------------------
    ------------------------------------------------------------------------------------------------
    --------------------------------------------銆愮粏绾瑰紑濮?zhl銆?-------------------------------------------
    -------------------------------------------------------------------------------------------------////
    """

    def enhanceSlimImg(self,cmd_param):
        def random_light_color(img):
            """闅忔満璋冩暣浜害銆佸姣斿害銆佽壊娓?""
            # 杞埌 HSV 鏀逛寒搴?            hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV).astype(np.float32)
            # 浜害璋冩暣 (V)
            value_scale = random.uniform(0.7, 1.3)  # 0.7~1.3 鍊?            hsv[:, :, 2] = np.clip(hsv[:, :, 2] * value_scale, 0, 255)

            # 鑹叉俯璋冩暣锛圚 鍋忕Щ妯℃嫙鍐锋殩鑹茶皟锛?            hue_shift = random.randint(-8, 8)  # 灏忓箙鍋忕Щ鑹茬浉
            hsv[:, :, 0] = (hsv[:, :, 0] + hue_shift) % 180

            img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)

            # 瀵规瘮搴﹁皟鏁?            alpha = random.uniform(0.8, 1.2)  # 瀵规瘮搴︾郴鏁?            beta = random.randint(-10, 10)    # 浜害鍋忕Щ
            img = np.clip(alpha * img + beta, 0, 255).astype(np.uint8)

            return img

        def rotate_img_any_angle(img, mask, angle):
            h, w = img.shape[:2]

            # 鎵╁睍杈圭晫锛岄伩鍏嶆棆杞鍒?            pad = int(0.3 * max(h, w))
            img_pad = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_REFLECT)
            mask_pad = cv2.copyMakeBorder(mask, pad, pad, pad, pad, cv2.BORDER_REFLECT)

            H, W = img_pad.shape[:2]
            center = (W // 2, H // 2)

            M = cv2.getRotationMatrix2D(center, angle, 1.0)

            img_rot = cv2.warpAffine(img_pad, M, (W, H), flags=cv2.INTER_LINEAR)
            mask_rot = cv2.warpAffine(mask_pad, M, (W, H), flags=cv2.INTER_NEAREST)

            # 鍐嶈鍥炲師鏉?patch 澶у皬
            y = (H - h) // 2
            x = (W - w) // 2
            return img_rot[y:y+h, x:x+w], mask_rot[y:y+h, x:x+w]

        def enhanceSlimFinalImg(images_dir, masks_dir, enhance_image_dir, enhance_mask_dir, patch_size):
            """
            @desc: 澧炲己鍥剧墖
            """
            # 濡傛灉鏂囦欢澶逛笉瀛樺湪灏辨柊寤烘枃浠跺す
            img_paths  = sorted(glob.glob(os.path.join(images_dir, '*')))
            mask_paths = sorted(glob.glob(os.path.join(masks_dir, '*')))

            images_enhance_out = Path(enhance_image_dir)
            masks_enhance_out  = Path(enhance_mask_dir)
            images_enhance_out.mkdir(parents=True, exist_ok=True)
            masks_enhance_out.mkdir(parents=True, exist_ok=True)

            # 棰勮绠楁瘡寮犲浘鐨勬粦鍧楃储寮?            pbar = tqdm(img_paths, desc="Enhancing images")
            for img_idx, img_path in enumerate(pbar):
                self.proc_modules_obj["imgbase"].send_progress(
                    pbar, "Enhancing img: {}".format(img_path)
                )
                try:
                    img = cv2.imread(img_path) # BGR->RGB
                    img_mask_alpha = cv2.imread(mask_paths[img_idx], cv2.IMREAD_UNCHANGED) # 閫忔槑鐏板害鍥?                    rgba = cv2.split(img_mask_alpha)
                    r, g, b, a = rgba
                except Exception as e:
                    print("read img wrong: ", str(e))
                    continue
                # 鎻愬彇mask
                img_mask = a
                img_mask = (img_mask > 10).astype(np.uint8) * 255 #
                img_mask, _ = self.proc_modules_obj["imgbase"].erode_mask_file(img_mask) # 鑵愯殌, 缁嗙汗杩欓噷蹇呴』寰楄繖涔堝共
                h, w = img.shape[:2]
                num_w = int(w // patch_size) # 鐪嬭兘鏈夊嚑涓搴﹀潡锛?鍧楀乏鍙?                # 楂樺害鏂瑰悜锛氬浐瀹氫粠宸︿笂寮€濮嬪垏 3 鍧?                max_height_pixel = h * 0.7 # 澶ф鍒伴蓟瀛愮殑浣嶇疆, num_h澶ф7鍧楀乏鍙? 鎳掑緱寮曞叆瀹氫綅浜?                num_h = int(max_height_pixel // patch_size) # 楂樺害閮ㄥ垎鍙栧埌榧诲瓙, 杩欓噷鍥犱负鏍囨敞浣嶇疆鍒扮溂鐫涗互涓? 鎻愰珮閬嶅巻鏁堢巼, 灏变笉閫傜敤鍔ㄦ€佺畻楂樺害鐨勫啓娉?                for i in range(num_h):
                    y1 = i * patch_size
                    for j in range(num_w):
                        x1 = j * patch_size
                        patch_mask = img_mask[y1:y1+patch_size, x1:x1+patch_size]
                        if np.count_nonzero(patch_mask) < 200:
                            continue
                        patch_img = img[y1:y1+patch_size, x1:x1+patch_size, :]

                        # 鍘熷浘澧炲己 512*512
                        enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), "origin", j, i)
                        enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), "origin", j, i)
                        cv2.imwrite(enhance_img_path, patch_img)
                        cv2.imwrite(enhance_mask_path, patch_mask)

                        if 1 == 1:
                            # 鍏夌収/浜害/鑹叉俯澧炲己
                            light_img = random_light_color(patch_img)
                            enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), "light", j, i)
                            enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), "light", j, i)
                            cv2.imwrite(enhance_img_path, light_img)
                            cv2.imwrite(enhance_mask_path, patch_mask)

                            # 姘村钩缈昏浆澧炲己
                            enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), "horizon_flip", j, i)
                            enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), "horizon_flip", j, i)
                            cv2.imwrite(enhance_img_path, np.fliplr(patch_img).copy())
                            cv2.imwrite(enhance_mask_path, np.fliplr(patch_mask).copy())

                            # 鍨傜洿缈昏浆澧炲己
                            enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), "vertical_flip", j, i)
                            enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), "vertical_flip", j, i)
                            cv2.imwrite(enhance_img_path, np.flipud(patch_img).copy())
                            cv2.imwrite(enhance_mask_path, np.flipud(patch_mask).copy())

                            # 姘村钩缈昏浆澧炲己-鍏夋簮
                            enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), "horizon_flip_light", j, i)
                            enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), "horizon_flip_light", j, i)
                            light_img = random_light_color(patch_img)
                            cv2.imwrite(enhance_img_path, np.fliplr(light_img).copy())
                            cv2.imwrite(enhance_mask_path, np.fliplr(patch_mask).copy())

                            # 鍨傜洿缈昏浆澧炲己-鍏夋簮
                            enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), "vertical_flip_light", j, i)
                            enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), "vertical_flip_light", j, i)
                            light_img = random_light_color(patch_img)
                            cv2.imwrite(enhance_img_path, np.flipud(light_img).copy())
                            cv2.imwrite(enhance_mask_path, np.flipud(patch_mask).copy())


                            # 闅忔満鏃嬭浆澧炲己
                            angles = [-75, -60, -45, -30, -15, 15, 30, 45, 60, 75]
                            for angle in angles:
                                img_rot, mask_rot = rotate_img_any_angle(patch_img, patch_mask, angle)
                                if np.count_nonzero(mask_rot) < 200: # 鏃嬭浆鏈夌┖鍥剧殑涔熷幓鎺?                                    continue
                                enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), "rotate", angle, j, i)
                                enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), "rotate", angle, j, i)
                                cv2.imwrite(enhance_img_path, img_rot)
                                cv2.imwrite(enhance_mask_path, mask_rot)


            # 鍒犻櫎images_dir鍜宮asks_dir
            shutil.rmtree('dataset')
 

        def _enhanceImg(img_dir_lists, mask_dir_lists, enhance_image_dir, enhance_mask_dir, patch_size):
            """
            鏁版嵁浠嶽'/xx/xx/xx/', '/xx/xx/xx/']瀛樺偍鍒?            /dataset鐩綍
            -----images
            -----masks
            銆愬啀鍒般€?            <鐢ㄦ埛瀹氫箟鐨勬枃浠跺す>-杩欓噷鐨勬暟鎹甫浜嗘暟鎹寮?            ------images
            ------masks
            """
            tmp_data_dir = Path("dataset")
            tmp_data_dir.mkdir(parents=True, exist_ok=True)

            print("img_dir_lists: ", img_dir_lists)
            images_dir, masks_dir = self.ready_train_dataset(img_dir_lists, mask_dir_lists, str(tmp_data_dir)) # 鎶婂涓洰褰曠殑鏁版嵁鏁寸悊鍒颁竴涓洰褰?            enhanceSlimFinalImg(images_dir, masks_dir, enhance_image_dir, enhance_mask_dir, patch_size) # 瀵瑰崟涓洰褰曠殑images鐩綍杩涜鏁版嵁澧炲己骞跺瓨鍌ㄥ埌鏈湴

        _enhanceImg(
            cmd_param['img_dir_lists'],
            cmd_param['mask_dir_lists'],
            cmd_param['enhance_image_dir'],
            cmd_param['enhance_mask_dir'],
            cmd_param['patch_size']
        )


    # 璁粌缁嗙汗銆恇y zhl 缁嗙汗銆?    def trainSlimImgModuleByUnetIterator(self,cmd_param):
        def _trainSlimImgModuleByUnetIterator(
                            train_image_dir,
                            train_mask_dir,
                            model_dir,
                            model_name,
                            model_pretrain_path=None,
                            model_checkpoint_path=None,
                            model_dataset_name="WrinkleDatasetSlim",
                            tmp_dir="./tmp",
                            img_size=512,
                            batch_size=4,
                            epochs=50,
                            lr=1e-4,
                            device=torch.device('cuda' if torch.cuda.is_available() else 'cpu'),
                            gpu_id=1):
            """
            鏀寔鏂偣缁锛堜紭鍏堝姞杞?checkpoint锛屽叾娆″姞杞介璁粌鏉冮噸锛?            """
            torch.cuda.empty_cache()
            torch.cuda.set_device(gpu_id)
            # 1) 鏁版嵁鍑嗗
            tmp_model_pretrain_path = Path(os.path.dirname(model_pretrain_path))
            tmp_model_pretrain_path.mkdir(parents=True, exist_ok=True)
            tmp_model_checkpoint_path = Path(os.path.dirname(model_checkpoint_path))
            tmp_model_checkpoint_path.mkdir(parents=True, exist_ok=True)
            # train_ds = WrinkleDatasetSlim(images_dir, masks_dir, img_size) # WrinkleDatasetNasolabial , 浠庨厤缃枃浠跺姩鎬佸鍏?            module = importlib.import_module("src.features.imgWrinkle.module_unet") # 鍔ㄦ€佸姞杞?            train_ds = getattr(module, model_dataset_name)
            train_ds = train_ds(train_image_dir, train_mask_dir, img_size)
            
            train_loader = DataLoader(train_ds,
                                    batch_size=batch_size,
                                    shuffle=True,
                                    num_workers=1,
                                    pin_memory=True)
            # 2) 妯″瀷銆佷紭鍖栧櫒銆佹崯澶?            model = UNet().to(device)
            optimizer = torch.optim.Adam(model.parameters(), lr=lr)
            bce = torch.nn.BCELoss()
            start_epoch = 0
            # 3) 浼樺厛鍔犺浇 checkpoint
            if model_checkpoint_path and Path(model_checkpoint_path).exists():
                checkpoint = torch.load(model_checkpoint_path, map_location=device)
                model.load_state_dict(checkpoint["model_state_dict"])
                optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
                start_epoch = checkpoint["epoch"] + 1
                print(f"[Resume] 浠?{model_checkpoint_path} 鎭㈠锛岀户缁缁?Epoch {start_epoch}/{epochs}")
            # 4) 鍚﹀垯鍔犺浇棰勮缁冩潈閲?            elif model_pretrain_path and Path(model_pretrain_path).exists():
                if "bubaoliu_youhuaqi" != "bubaoliu_youhuaqi": # 浼樺寲鍣?                    state = torch.load(model_pretrain_path, map_location=device)
                    if isinstance(state, dict) and "model_state_dict" in state:
                        state = state["model_state_dict"]
                    model.load_state_dict(state)
                    print(f"[Init] 浠庨璁粌鏉冮噸 {model_pretrain_path} 鍔犺浇妯″瀷")
                if "baoliu_youhuaqi" == "baoliu_youhuaqi": # 淇濈暀浼樺寲鍣?杩唬璁粌搴旇闇€瑕佺殑
                    checkpoint = torch.load(model_checkpoint_path, map_location=device)
                    model.load_state_dict(checkpoint["model_state_dict"])
                    optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
                    start_epoch = checkpoint["epoch"] + 1
                    print(f"[Resume] 浠?{model_checkpoint_path} 鎭㈠锛岀户缁缁?Epoch {start_epoch}/{epochs}")
            # 涓柇淇濆瓨
            interrupted = False
            # def handle_interrupt(sig, frame):
            #     nonlocal interrupted
            #     interrupted = True
            #     print("\n[Warning] 妫€娴嬪埌涓柇淇″彿锛屼繚瀛樺綋鍓嶈繘搴﹀悗閫€鍑?..")
            # signal.signal(signal.SIGINT, handle_interrupt)
            # 5) 璁粌寰幆
            for epoch in range(start_epoch, epochs):
                model.train()
                epoch_loss = 0.0
                pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}")
                for imgs, masks in pbar:
                    self.proc_modules_obj["imgbase"].send_progress(
                        pbar, "Trainning Slim wrinkle Epoch: {}/{}".format(epoch+1, epochs)
                    )
                    imgs, masks = imgs.to(device), masks.to(device)
                    preds = model(imgs)
                    loss = bce(preds, masks) + self.dice_loss(preds, masks)
                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()
                    epoch_loss += loss.item()
                print(f"Epoch {epoch+1} | Loss: {epoch_loss/len(train_loader):.4f}")
                # 6) 淇濆瓨 checkpoint锛堝彧淇濆瓨鏈€鍚庝竴娆★級
                latest_ckpt = Path(model_checkpoint_path)
                torch.save({
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict()
                }, latest_ckpt)
                print(f"[Save] 鏈€鏂?checkpoint 淇濆瓨鍒? {latest_ckpt}")
                # 7) 姣?杞繚瀛樹竴涓ā鍨嬪埌model_dir
                if (epoch + 1) % 1 == 0:  # epoch 浠?0 寮€濮嬶紝鎵€浠ュ姞1鏇寸洿瑙?                    model_save_dir = Path(model_dir)
                    model_save_dir.mkdir(parents=True, exist_ok=True)
                    save_path = model_save_dir / f"{model_name}_epoch{epoch+1}.pth"
                    torch.save({
                        "epoch": epoch,
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict()
                    }, save_path)
                    print(f"[Save] checkpoint 淇濆瓨鍒? {save_path}")
                # 濡傛灉琚?Ctrl+C 瑙﹀彂涓柇锛岀洿鎺ラ€€鍑?                if interrupted:
                    break
            print("[Done] 璁粌缁撴潫")

        # 璁粌鎶ご绾?        _trainSlimImgModuleByUnetIterator(cmd_param['train_image_dir'],
                                            cmd_param['train_mask_dir'],
                                            cmd_param['model_dir'],
                                            cmd_param['model_name'],
                                            cmd_param['model_pretrain_path'],
                                            cmd_param['model_checkpoint_path'],
                                            cmd_param['model_dataset_name'],
                                            self.node_cfg['tmp_data'],
                                            cmd_param['img_size'],
                                            cmd_param['batch_size'],
                                            cmd_param['epochs'],
                                            cmd_param['lr'],
                                            cmd_param['gpu_id']
                                        )

    # 棰勬祴缁嗙汗澶氱粍鏂囦欢
    def predictSlimWrinkleGroup(self, cmd_param):

        def _predictSlimWrinkleGroup(img_dirs, out_dirs, model_paths, img_size=512, device='cuda', gpu_id=0):
            # ====== 1. 鍔犺浇妯″瀷涓€娆?======
            models, device = self.load_models(model_paths, device=device, gpu_id=gpu_id)
            # ====== 2. 閬嶅巻鎵€鏈夌洰褰曪紝涓€涓€瀵瑰簲 ======
            for dir_idx, (img_dir, out_dir) in enumerate(zip(img_dirs, out_dirs)):
                print(f"\n== 澶勭悊鐩綍 {dir_idx+1}/{len(img_dirs)} ==")
                print(f"杈撳叆:  {img_dir}")
                print(f"杈撳嚭:  {out_dir}")

                # 鍒涘缓杈撳嚭鐩綍
                os.makedirs(out_dir, exist_ok=True)

                # ====== 3. 鏀堕泦鍥剧墖 ======
                img_paths = [
                    p for p in glob.glob(os.path.join(img_dir, "*"))
                    if p.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))
                ]

                if not img_paths:
                    print(f"[璀﹀憡] 鏂囦欢澶规病鏈夊浘鐗? {img_dir}")
                    continue

                # ====== 4. 姣忎釜鐩綍涓€涓繘搴︽潯 ======
                pbar = tqdm(img_paths, desc=f"Predict slim dir {img_dir}")

                # ====== 5. 閬嶅巻鐩綍涓嬫墍鏈夊浘鐗?======
                for img_path in pbar:
                    # 鍥炶皟杩涘害
                    self.proc_modules_obj["imgbase"].send_progress(
                        pbar, f"Predicting slim wrinkle FROM {img_path} TO {out_dir}"
                    )

                    img = cv2.imread(img_path)
                    if img is None:
                        continue

                    h0, w0 = img.shape[:2]
                    patch_size = img_size
                    stride = 480

                    # 杈撳嚭 mask
                    full_pred = np.zeros((h0, w0), dtype=np.uint8)

                    crop_h_start = int(h0 * 0.05)
                    crop_h_end = int(h0 * 0.6)

                    angles = [0, 45, 90, 180]

                    # ====== 6. 婊戠獥 + 澶氭ā鍨嬪瑙掑害 ======
                    for y in range(crop_h_start, crop_h_end, stride):
                        for x in range(200, w0, stride):

                            y2 = min(y + patch_size, h0)
                            x2 = min(x + patch_size, w0)
                            patch = img[y:y2, x:x2]

                            patch_mask_final = np.zeros((patch.shape[0], patch.shape[1]), dtype=np.uint8)

                            # N涓ā鍨?脳 澶氳搴?                            for model in models:
                                for angle in angles:

                                    if angle != 0:
                                        rot_patch = np.rot90(patch, k=angle//90)
                                    else:
                                        rot_patch = patch.copy()

                                    h, w = rot_patch.shape[:2]

                                    padded = np.zeros((patch_size, patch_size, 3), dtype=np.uint8)
                                    padded[:h, :w] = rot_patch

                                    tensor = torch.from_numpy(padded / 255.).permute(2, 0, 1).unsqueeze(0).float().to(device)

                                    with torch.no_grad():
                                        pred = model(tensor)[0, 0].cpu().numpy()

                                    pred = pred[:h, :w]

                                    if angle != 0:
                                        pred = np.rot90(pred, k=(4 - angle//90))

                                    mask = (pred > 0.1).astype(np.uint8)
                                    patch_mask_final |= mask

                            full_pred[y:y2, x:x2] |= patch_mask_final

                    # ====== 7. 鏈€缁?mask ======
                    full_mask = (full_pred > 0).astype(np.uint8) * 255

                    basename = os.path.splitext(os.path.basename(img_path))[0]
                    save_path = os.path.join(out_dir, f"{basename}.png")

                    redMask = self.proc_modules_obj["imgbase"].saveMaskToRGBAPng(full_mask)
                    cv2.imwrite(save_path, redMask)

        _predictSlimWrinkleGroup(
            cmd_param["img_dir"],
            cmd_param["out_put_dir"],
            cmd_param["model_dir"],
            cmd_param.get("img_size", 512)
        )


    """////---------------------------------------------------------------------------------------------
    ------------------------------------------------------------------------------------------------
    --------------------------------------------銆愮粏绾圭粨鏉?zhl銆?-------------------------------------------
    -------------------------------------------------------------------------------------------------////
    """




    """////--------------------------------------------------------------------------------------------
    -----------------------------------------------------------------------------------------------
    --------------------------------------------銆愮矖绾瑰紑濮?zhl銆?------------------------------------------
    -----------------------------------------------------------------------------------------------////
    """
    
    def enhanceBoldImg(self,cmd_param):
        def random_light_color(img):
            """闅忔満璋冩暣浜害銆佸姣斿害銆佽壊娓?""
            # 杞埌 HSV 鏀逛寒搴?            hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV).astype(np.float32)
            # 浜害璋冩暣 (V)
            value_scale = random.uniform(0.7, 1.3)  # 0.7~1.3 鍊?            hsv[:, :, 2] = np.clip(hsv[:, :, 2] * value_scale, 0, 255)

            # 鑹叉俯璋冩暣锛圚 鍋忕Щ妯℃嫙鍐锋殩鑹茶皟锛?            hue_shift = random.randint(-8, 8)  # 灏忓箙鍋忕Щ鑹茬浉
            hsv[:, :, 0] = (hsv[:, :, 0] + hue_shift) % 180

            img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)

            # 瀵规瘮搴﹁皟鏁?            alpha = random.uniform(0.8, 1.2)  # 瀵规瘮搴︾郴鏁?            beta = random.randint(-10, 10)    # 浜害鍋忕Щ
            img = np.clip(alpha * img + beta, 0, 255).astype(np.uint8)

            return img

        def rotate_img_any_angle(img, mask, angle):
            h, w = img.shape[:2]

            # 鎵╁睍杈圭晫锛岄伩鍏嶆棆杞鍒?            pad = int(0.3 * max(h, w))
            img_pad = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_REFLECT)
            mask_pad = cv2.copyMakeBorder(mask, pad, pad, pad, pad, cv2.BORDER_REFLECT)

            H, W = img_pad.shape[:2]
            center = (W // 2, H // 2)

            M = cv2.getRotationMatrix2D(center, angle, 1.0)

            img_rot = cv2.warpAffine(img_pad, M, (W, H), flags=cv2.INTER_LINEAR)
            mask_rot = cv2.warpAffine(mask_pad, M, (W, H), flags=cv2.INTER_NEAREST)

            # 鍐嶈鍥炲師鏉?patch 澶у皬
            y = (H - h) // 2
            x = (W - w) // 2
            return img_rot[y:y+h, x:x+w], mask_rot[y:y+h, x:x+w]

        def enhanceBoldFinalImg(images_dir, masks_dir, enhance_image_dir, enhance_mask_dir, patch_size):
            """
            @desc: 澧炲己鍥剧墖
            """
            # 濡傛灉鏂囦欢澶逛笉瀛樺湪灏辨柊寤烘枃浠跺す
            img_paths  = sorted(glob.glob(os.path.join(images_dir, '*')))
            mask_paths = sorted(glob.glob(os.path.join(masks_dir, '*')))

            images_enhance_out = Path(enhance_image_dir)
            masks_enhance_out  = Path(enhance_mask_dir)
            images_enhance_out.mkdir(parents=True, exist_ok=True)
            masks_enhance_out.mkdir(parents=True, exist_ok=True)

            # 棰勮绠楁瘡寮犲浘鐨勬粦鍧楃储寮?            pbar = tqdm(img_paths, desc="Enhancing images")
            for img_idx, img_path in enumerate(pbar):
                self.proc_modules_obj["imgbase"].send_progress(
                    pbar, "Enhancing img: {}".format(img_path)
                )
                try:
                    img = cv2.imread(img_path) # BGR->RGB
                    img_mask_alpha = cv2.imread(mask_paths[img_idx], cv2.IMREAD_UNCHANGED) # 閫忔槑鐏板害鍥?                    rgba = cv2.split(img_mask_alpha)
                    r, g, b, a = rgba
                except Exception as e:
                    print("read img wrong: ", str(e))
                    continue
                # 鎻愬彇mask
                img_mask = a
                img_mask = (img_mask > 10).astype(np.uint8) * 255
                img_mask = cv2.resize(img_mask, (patch_size, patch_size))
                img = cv2.resize(img, (patch_size, patch_size))
                
                patch_mask = img_mask
                patch_img = img
                if np.count_nonzero(patch_mask) < 200:
                    continue
                i, j = 0, 0
    
                if 1 == 1:
                    # 鍘熷浘澧炲己 1024*1024
                    enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), img_idx, "origin")
                    enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), img_idx, "origin")
                    cv2.imwrite(enhance_img_path, patch_img.copy())
                    cv2.imwrite(enhance_mask_path, patch_mask.copy())

                    # 姘村钩缈昏浆澧炲己
                    enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), img_idx, "horizonFlip")
                    enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), img_idx, "horizonFlip")
                    cv2.imwrite(enhance_img_path, np.fliplr(patch_img.copy()))
                    cv2.imwrite(enhance_mask_path, np.fliplr(patch_mask.copy()))

                    # 姘村钩缈昏浆澧炲己-浜厜
                    light_img = random_light_color(patch_img)
                    enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), img_idx, "horizonFlipLight")
                    enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), img_idx, "horizonFlipLight")
                    cv2.imwrite(enhance_img_path, light_img)
                    cv2.imwrite(enhance_mask_path, patch_mask.copy())

                    # 鍏夌収/浜害/鑹叉俯澧炲己
                    light_img = random_light_color(patch_img)
                    enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), img_idx, "light")
                    enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), img_idx, "light")
                    cv2.imwrite(enhance_img_path, light_img)
                    cv2.imwrite(enhance_mask_path, patch_mask.copy())


                    # 鍨傜洿缈昏浆澧炲己
                    enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), img_idx, "verticalFlip")
                    enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), img_idx, "verticalFlip")
                    cv2.imwrite(enhance_img_path, np.flipud(patch_img.copy()))
                    cv2.imwrite(enhance_mask_path, np.flipud(patch_mask.copy()))

                    # 鍨傜洿缈昏浆澧炲己-浜厜
                    light_img = random_light_color(patch_img.copy())
                    enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), img_idx, "verticalFlipLight")
                    enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), img_idx, "verticalFlipLight")
                    cv2.imwrite(enhance_img_path, np.flipud(light_img))
                    cv2.imwrite(enhance_mask_path, np.flipud(patch_mask.copy()))

                    # 闅忔満鏃嬭浆澧炲己
                    angles = [-30, -15, 15, 30]
                    for angle in angles:
                        img_rot, mask_rot = rotate_img_any_angle(patch_img.copy(), patch_mask.copy(), angle)
                        if np.count_nonzero(mask_rot) < 200: # 鏃嬭浆鏈夌┖鍥剧殑涔熷幓鎺?                            continue
                        enhance_img_path = str(images_enhance_out).rstrip("/") + "/{}_{}{}_{}_{}.jpg".format(os.path.basename(img_path).replace('.jpg', ''), "rotate", angle, j, i)
                        enhance_mask_path = str(masks_enhance_out).rstrip("/") + "/{}_{}{}_{}_{}.png".format(os.path.basename(img_path).replace('.jpg', ''), "rotate", angle, j, i)
                        cv2.imwrite(enhance_img_path, img_rot)
                        cv2.imwrite(enhance_mask_path, mask_rot)
            # 鍒犻櫎images_dir鍜宮asks_dir
            shutil.rmtree("dataset")

 

        def _enhanceImg(img_dir_lists, mask_dir_lists, enhance_image_dir, enhance_mask_dir, patch_size):
            """
            鏁版嵁浠嶽'/xx/xx/xx/', '/xx/xx/xx/']瀛樺偍鍒?            /dataset鐩綍
            -----images
            -----masks
            銆愬啀鍒般€?            <鐢ㄦ埛瀹氫箟鐨勬枃浠跺す>-杩欓噷鐨勬暟鎹甫浜嗘暟鎹寮?            ------images
            ------masks
            """
            tmp_data_dir = Path("dataset")
            tmp_data_dir.mkdir(parents=True, exist_ok=True)

            images_dir, masks_dir = self.ready_train_dataset(img_dir_lists, mask_dir_lists, str(tmp_data_dir)) # 鎶婂涓洰褰曠殑鏁版嵁鏁寸悊鍒颁竴涓洰褰?            enhanceBoldFinalImg(images_dir, masks_dir, enhance_image_dir, enhance_mask_dir, patch_size) # 瀵瑰崟涓洰褰曠殑images鐩綍杩涜鏁版嵁澧炲己骞跺瓨鍌ㄥ埌鏈湴

        _enhanceImg(
            cmd_param['img_dir_lists'],
            cmd_param['mask_dir_lists'],
            cmd_param['enhance_image_dir'],
            cmd_param['enhance_mask_dir'],
            cmd_param['patch_size']
        )


    # 璁粌绮楃汗 銆恇y zhl 绮楃汗銆?    def trainBoldImgModuleByUnetIterator(self,cmd_param):
        def _trainBoldImgModuleByUnetIterator(
                            train_image_dir,
                            train_mask_dir,
                            model_dir,
                            model_name,
                            model_pretrain_path=None,
                            model_checkpoint_path=None,
                            model_dataset_name="WrinkleDatasetSlim",
                            tmp_dir="./tmp",
                            img_size=1024,
                            batch_size=4,
                            epochs=50,
                            lr=1e-4,
                            device=torch.device('cuda' if torch.cuda.is_available() else 'cpu'),
                            gpu_id=1):
            """
            鏀寔鏂偣缁锛堜紭鍏堝姞杞?checkpoint锛屽叾娆″姞杞介璁粌鏉冮噸锛?            """
            torch.cuda.empty_cache()
            torch.cuda.set_device(gpu_id)
            # 1) 鏁版嵁鍑嗗
            tmp_model_pretrain_path = Path(os.path.dirname(model_pretrain_path))
            tmp_model_pretrain_path.mkdir(parents=True, exist_ok=True)
            tmp_model_checkpoint_path = Path(os.path.dirname(model_checkpoint_path))
            tmp_model_checkpoint_path.mkdir(parents=True, exist_ok=True)
            # train_ds = WrinkleDatasetSlim(images_dir, masks_dir, img_size) # WrinkleDatasetNasolabial , 浠庨厤缃枃浠跺姩鎬佸鍏?            module = importlib.import_module("src.features.imgWrinkle.module_unet") # 鍔ㄦ€佸姞杞?            train_ds = getattr(module, model_dataset_name)
            train_ds = train_ds(train_image_dir, train_mask_dir, img_size)
            
            train_loader = DataLoader(train_ds,
                                    batch_size=batch_size,
                                    shuffle=True,
                                    num_workers=1,
                                    pin_memory=True)
            # 2) 妯″瀷銆佷紭鍖栧櫒銆佹崯澶?            model = UNet().to(device)
            optimizer = torch.optim.Adam(model.parameters(), lr=lr)
            bce = torch.nn.BCELoss()
            start_epoch = 0
            # 3) 浼樺厛鍔犺浇 checkpoint
            if model_checkpoint_path and Path(model_checkpoint_path).exists():
                checkpoint = torch.load(model_checkpoint_path, map_location=device)
                model.load_state_dict(checkpoint["model_state_dict"])
                optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
                start_epoch = checkpoint["epoch"] + 1
                print(f"[Resume] 浠?{model_checkpoint_path} 鎭㈠锛岀户缁缁?Epoch {start_epoch}/{epochs}")
            # 4) 鍚﹀垯鍔犺浇棰勮缁冩潈閲?            elif model_pretrain_path and Path(model_pretrain_path).exists():
                if "bubaoliu_youhuaqi" != "bubaoliu_youhuaqi":
                    state = torch.load(model_pretrain_path, map_location=device)
                    if isinstance(state, dict) and "model_state_dict" in state:
                        state = state["model_state_dict"]
                    model.load_state_dict(state)
                    print(f"[Init] 浠庨璁粌鏉冮噸 {model_pretrain_path} 鍔犺浇妯″瀷")
                if "baoliu_youhuaqi" == "baoliu_youhuaqi": # 淇濈暀浼樺寲鍣?杩唬璁粌搴旇闇€瑕佺殑
                    checkpoint = torch.load(model_checkpoint_path, map_location=device)
                    model.load_state_dict(checkpoint["model_state_dict"])
                    optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
                    start_epoch = checkpoint["epoch"] + 1
                    print(f"[Resume] 浠?{model_checkpoint_path} 鎭㈠锛岀户缁缁?Epoch {start_epoch}/{epochs}")
            # 涓柇淇濆瓨
            interrupted = False
            # def handle_interrupt(sig, frame):
            #     nonlocal interrupted
            #     interrupted = True
            #     print("\n[Warning] 妫€娴嬪埌涓柇淇″彿锛屼繚瀛樺綋鍓嶈繘搴﹀悗閫€鍑?..")
            # signal.signal(signal.SIGINT, handle_interrupt)

            # 5) 璁粌寰幆
            for epoch in range(start_epoch, epochs):
                model.train()
                epoch_loss = 0.0
                pbar = tqdm(train_loader, desc="Epoch {}/{}".format(epoch+1, epochs))
                for imgs, masks in pbar:
                    self.proc_modules_obj["imgbase"].send_progress(
                        pbar, "Trainning Bold wrinkle Epoch: {}/{}".format(epoch+1, epochs)
                    )
                    imgs, masks = imgs.to(device), masks.to(device)
                    preds = model(imgs)
                    loss = bce(preds, masks) + self.dice_loss(preds, masks)
                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()
                    epoch_loss += loss.item()
                print(f"Epoch {epoch+1} | Loss: {epoch_loss/len(train_loader):.4f}")
                # 6) 淇濆瓨 checkpoint锛堝彧淇濆瓨鏈€鍚庝竴娆★級
                latest_ckpt = Path(model_checkpoint_path)
                torch.save({
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict()
                }, latest_ckpt)
                print(f"[Save] 鏈€鏂?checkpoint 淇濆瓨鍒? {latest_ckpt}")
                # 7) 姣?杞繚瀛樹竴涓ā鍨嬪埌model_dir
                if (epoch + 1) % 1 == 0:  # epoch 浠?0 寮€濮嬶紝鎵€浠ュ姞1鏇寸洿瑙?                    model_save_dir = Path(model_dir)
                    model_save_dir.mkdir(parents=True, exist_ok=True)
                    save_path = model_save_dir / f"{model_name}_epoch{epoch+1}.pth"
                    torch.save({
                        "epoch": epoch,
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict()
                    }, save_path)
                    print(f"[Save] checkpoint 淇濆瓨鍒? {save_path}")
                # 濡傛灉琚?Ctrl+C 瑙﹀彂涓柇锛岀洿鎺ラ€€鍑?                if interrupted:
                    break
            print("[Done] 璁粌缁撴潫")
            
        # 璁粌娉曚护绾?        _trainBoldImgModuleByUnetIterator(cmd_param['train_image_dir'],
                                            cmd_param['train_mask_dir'],
                                            cmd_param['model_dir'],
                                            cmd_param['model_name'],
                                            cmd_param['model_pretrain_path'],
                                            cmd_param['model_checkpoint_path'],
                                            cmd_param['model_dataset_name'],
                                            self.node_cfg['tmp_data'],
                                            cmd_param['img_size'],
                                            cmd_param['batch_size'],
                                            cmd_param['epochs'],
                                            cmd_param['lr'],
                                            cmd_param['gpu_id']
                                        )


    def _fixed_color_jitter(self, img):
        """娉曚护绾归娴嬩笓鐢ㄥ浐瀹氫寒搴﹀寮猴細浜?/ 鏆?鍚勪竴浠?""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)

        # 鍘熷浘
        img_orig = img

        # 浜害澧炲己锛堝彉浜級
        hsv_bright = hsv.copy()
        hsv_bright[:, :, 2] *= 1.25
        hsv_bright[:, :, 2] = np.clip(hsv_bright[:, :, 2], 0, 255)
        img_bright = cv2.cvtColor(hsv_bright.astype(np.uint8), cv2.COLOR_HSV2BGR)

        # 浜害闄嶄綆锛堝彉鏆楋級
        hsv_dark = hsv.copy()
        hsv_dark[:, :, 2] *= 0.75
        hsv_dark[:, :, 2] = np.clip(hsv_dark[:, :, 2], 0, 255)
        img_dark = cv2.cvtColor(hsv_dark.astype(np.uint8), cv2.COLOR_HSV2BGR)

        # 瀵规瘮搴﹀寮?        alpha = 1.5  # 瀵规瘮搴︾郴鏁?>1 鎻愬崌
        img_contrast_up = cv2.convertScaleAbs(img, alpha=alpha, beta=0)

        # 瀵规瘮搴﹂檷浣?        alpha = 0.5  # 瀵规瘮搴︾郴鏁?<1 闄嶄綆
        img_contrast_down = cv2.convertScaleAbs(img, alpha=alpha, beta=0)

        return [img_orig, img_bright, img_dark, img_contrast_up, img_contrast_down]

    # 棰勬祴澶氱粍绮楃汗 銆愭硶浠ょ汗銆佹唱娌熺瓑銆?    def predictBoldWrinkleGroup(self, cmd_param):

        def _predictBoldWrinkleGroup(img_dirs, out_dirs, model_paths, img_size=1024, device='cuda', gpu_id=0):
            # ====== 1. 鍔犺浇妯″瀷涓€娆?======
            models, device = self.load_models(model_paths, device=device, gpu_id=gpu_id)

            # ====== 2. 澶氬昂瀵?======
            img_size_list = [
                (1024, 768),
                (768, 1024),
                (512, 1024),
                (768, 768),
                (1024, 1024)
            ]

            # ====== 2. 閬嶅巻鎵€鏈夌洰褰曪紝涓€涓€瀵瑰簲 ======
            for dir_idx, (img_dir, out_dir) in enumerate(zip(img_dirs, out_dirs)):
                print(f"\n== 澶勭悊鐩綍 {dir_idx+1}/{len(img_dirs)} ==")
                print(f"杈撳叆:  {img_dir}")
                print(f"杈撳嚭:  {out_dir}")
                # 鍒涘缓杈撳嚭鐩綍
                os.makedirs(out_dir, exist_ok=True)
                # ====== 3. 鏀堕泦鍥剧墖 ======
                img_paths = [
                    p for p in glob.glob(os.path.join(img_dir, "*"))
                    if p.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))
                ]
                if not img_paths:
                    print(f"[璀﹀憡] 鏂囦欢澶规病鏈夊浘鐗? {img_dir}")
                    continue

                # ====== 4. 姣忎釜鐩綍涓€涓繘搴︽潯 ======
                pbar = tqdm(img_paths, desc=f"Predict bold dir {img_dir}")

                # ====== 3. 閬嶅巻鍥剧墖 ======
                for img_path in pbar:
                    # 鍥炶皟杩涘害
                    self.proc_modules_obj["imgbase"].send_progress(
                        pbar, f"Predicting Bold wrinkle: FROM {img_path} TO {out_dir}"
                    )

                    img = cv2.imread(img_path)
                    if img is None:
                        continue

                    h0, w0 = img.shape[:2]

                    # 鏈€缁?OR 鎺╄啘

                    # ====== 4. 澶氭ā鍨?脳 澶氬昂瀵?脳 澶氬寮?======
                    final_mask = np.zeros((h0, w0), dtype=np.uint8)
                    for model in models:
                        for (W, H) in img_size_list:
                            img_resized = cv2.resize(img, (W, H))
                            aug_list = self._fixed_color_jitter(img_resized)

                            for aug_i, img_aug in enumerate(aug_list):
                                tensor = torch.from_numpy(img_aug / 255.).permute(2, 0, 1).unsqueeze(0).float().to(device)
                                # --- 妯″瀷棰勬祴 ---
                                with torch.no_grad():
                                    pred = model(tensor)[0, 0].cpu().numpy()

                                del tensor
                                torch.cuda.empty_cache()

                                # --- 闃堝€煎寲 ---
                                mask_resized = (pred > 0.1).astype(np.uint8) * 255

                                # --- 杩樺師鍒板師鍥惧昂瀵?---
                                mask_back = cv2.resize(mask_resized, (w0, h0), interpolation=cv2.INTER_NEAREST)

                                # --- OR 铻嶅悎 ---
                                final_mask = np.logical_or(final_mask, (mask_back > 1)).astype(np.uint8) * 255

                    # ====== 5. 淇濆瓨缁撴灉 ======
                    redMask = self.proc_modules_obj["imgbase"].saveMaskToRGBAPng(final_mask)

                    basename = os.path.splitext(os.path.basename(img_path))[0]
                    save_path = os.path.join(out_dir, f'{basename}.png')
                    cv2.imwrite(save_path, redMask)

        # 娉曚护绾归娴嬭皟鐢?        _predictBoldWrinkleGroup(
            cmd_param["img_dir"],
            cmd_param["out_put_dir"],
            cmd_param["model_dir"],
            cmd_param.get("gpuid", 0)
        )
    

    # 棰勬祴鍗曚釜绮楃汗 銆愩€?    def predictSingleBoldWrinkleSvr(self, cmd_param):
        def _predictSingleBoldWrinkle(img_url, out_dir, model_paths, img_size=1024, device='cuda', gpu_id=0):
            tmp_indata_dir = os.path.join(
                self.node_cfg['tmp_data'].strip('/'),
                self.node_cfg['config_name'].strip('/'),
                'data'
            )
            os.makedirs(tmp_indata_dir, exist_ok=True)
            os.makedirs(os.path.dirname(out_dir), exist_ok=True)


            # 瀹夊叏鐢熸垚鏂囦欢鍚?            url_path = urlparse(img_url).path
            filename = os.path.basename(url_path)
            img_path = os.path.join(tmp_indata_dir, filename)

            # 涓嬭浇鍥剧墖
            resp = requests.get(img_url, timeout=15)
            resp.raise_for_status()  # 妫€鏌ヨ姹傛槸鍚︽垚鍔?            with open(img_path, 'wb') as f:
                f.write(resp.content)

            print("img_url, out_dir, model_paths: ", img_url, " ,", out_dir, "    ,", model_paths)
            # ====== 1. 鍔犺浇妯″瀷涓€娆?======
            models, device = self.load_models(model_paths, device=device, gpu_id=gpu_id)

            # ====== 2. 澶氬昂瀵?======
            img_size_list = [
                (1024, 768),
                (768, 1024),
                (512, 1024),
                (768, 768),
                (1024, 1024)
            ]

            img = cv2.imread(img_path)
            if img is None:
                raise Exception('鍥剧墖涓嶅瓨鍦?)

            h0, w0 = img.shape[:2]

            # 鏈€缁?OR 鎺╄啘

            # ====== 4. 澶氭ā鍨?脳 澶氬昂瀵?脳 澶氬寮?======
            final_mask = np.zeros((h0, w0), dtype=np.uint8)
            for model in models:

                pbar = tqdm(img_size_list, desc="棰勬祴涓?, ncols=80)
                for (W, H) in pbar:
                    self.proc_modules_obj["imgbase"].send_progress(pbar, deal_msg = 'Predict files, size is {}'.format((W,H)))
                    img_resized = cv2.resize(img, (W, H))
                    aug_list = self._fixed_color_jitter(img_resized)

                    for aug_i, img_aug in enumerate(aug_list):
                        tensor = torch.from_numpy(img_aug / 255.).permute(2, 0, 1).unsqueeze(0).float().to(device)
                        # --- 妯″瀷棰勬祴 ---
                        with torch.no_grad():
                            pred = model(tensor)[0, 0].cpu().numpy()

                        del tensor
                        torch.cuda.empty_cache()

                        # --- 闃堝€煎寲 ---
                        mask_resized = (pred > 0.1).astype(np.uint8) * 255

                        # --- 杩樺師鍒板師鍥惧昂瀵?---
                        mask_back = cv2.resize(mask_resized, (w0, h0), interpolation=cv2.INTER_NEAREST)

                        # --- OR 铻嶅悎 ---
                        final_mask = np.logical_or(final_mask, (mask_back > 1)).astype(np.uint8) * 255

            # ====== 5. 淇濆瓨缁撴灉 ======
            redMask = self.proc_modules_obj["imgbase"].saveMaskToRGBAPng(final_mask)

            file_name = os.path.basename(out_dir)
            save_path = os.path.join(os.path.dirname(out_dir), file_name)
            cv2.imwrite(save_path, redMask)
            # 绉诲姩鍒版煇鍙版湇鍔″櫒
            os.system("sshpass -p '<REDACTED_PASSWORD>' scp -r {} <REDACTED_USER>@<PRIVATE_IP>:/home/deploy/public/".format(save_path))
            os.system("rm -rf {}".format(save_path))

        # 娉曚护绾归娴嬭皟鐢?        _predictSingleBoldWrinkle(
            cmd_param["img_url"],
            cmd_param["out_put_url"],
            cmd_param["model_dir"],
            img_size=1024,
            device='cuda',
            gpu_id=cmd_param.get("gpuid", 0)
        )
        

    # 棰勬祴鍗曚釜绮楃汗 銆愩€?    def predictSingleBoldWrinkleToStorage(self, cmd_param):
        def _predictSingleBoldWrinkle(img_url, out_put_url, model_paths, img_size=1024, device='cuda', gpu_id=0):
            tmp_indata_dir = os.path.join(
                self.node_cfg['tmp_data'].strip('/'),
                self.node_cfg['config_name'].strip('/'),
                'data'
            )
            os.makedirs(tmp_indata_dir, exist_ok=True)


            # 瀹夊叏鐢熸垚鏂囦欢鍚?            url_path = urlparse(img_url).path
            filename = os.path.basename(url_path)
            img_path = os.path.join(tmp_indata_dir, filename)

            # 涓嬭浇鍥剧墖
            resp = requests.get(img_url, timeout=15)
            resp.raise_for_status()  # 妫€鏌ヨ姹傛槸鍚︽垚鍔?            with open(img_path, 'wb') as f:
                f.write(resp.content)
            logger.info("涓嬭浇鍥剧墖瀹屾垚")

            # ====== 1. 鍔犺浇妯″瀷涓€娆?======
            models, device = self.load_models(model_paths, device=device, gpu_id=gpu_id)

            # ====== 2. 澶氬昂瀵?======
            img_size_list = [
                (1024, 768),
                (768, 1024),
                (512, 1024),
                (768, 768),
                (1024, 1024)
            ]

            img = cv2.imread(img_path)
            if img is None:
                raise Exception('鍥剧墖涓嶅瓨鍦?)

            h0, w0 = img.shape[:2]

            # 鏈€缁?OR 鎺╄啘

            # ====== 4. 澶氭ā鍨?脳 澶氬昂瀵?脳 澶氬寮?======
            final_mask = np.zeros((h0, w0), dtype=np.uint8)
            for model in models:

                pbar = tqdm(img_size_list, desc="棰勬祴涓?, ncols=80)
                for (W, H) in pbar:
                    self.proc_modules_obj["imgbase"].send_progress(pbar, deal_msg = 'Predict files, size is {}'.format((W,H)))
                    img_resized = cv2.resize(img, (W, H))
                    aug_list = self._fixed_color_jitter(img_resized)

                    for aug_i, img_aug in enumerate(aug_list):
                        tensor = torch.from_numpy(img_aug / 255.).permute(2, 0, 1).unsqueeze(0).float().to(device)
                        # --- 妯″瀷棰勬祴 ---
                        with torch.no_grad():
                            pred = model(tensor)[0, 0].cpu().numpy()

                        del tensor
                        torch.cuda.empty_cache()

                        # --- 闃堝€煎寲 ---
                        mask_resized = (pred > 0.1).astype(np.uint8) * 255

                        # --- 杩樺師鍒板師鍥惧昂瀵?---
                        mask_back = cv2.resize(mask_resized, (w0, h0), interpolation=cv2.INTER_NEAREST)

                        # --- OR 铻嶅悎 ---
                        final_mask = np.logical_or(final_mask, (mask_back > 1)).astype(np.uint8) * 255

            # ====== 5. 淇濆瓨缁撴灉 ======
            redMask = self.proc_modules_obj["imgbase"].drawImgWithMask(img, final_mask, (0,0,255), alpha=0.5)
            # redMask = self.proc_modules_obj["imgbase"].saveMaskToRGBAPng(final_mask)
            logger.info("棰勬祴鍥剧墖瀹屾垚")

            save_path = tmp_indata_dir.strip('/')+'/xx.jpg'
            cv2.imwrite(save_path, redMask)
            # 绉诲姩鍒版煇鍙版湇鍔″櫒
            with open(save_path, 'rb') as f:
                response = requests.put(out_put_url, data=f)
                print("response.status_code: ", response.status_code)
                if response.status_code == 200:
                    print("涓婁紶鎴愬姛")

            logger.info("涓婁紶鍥剧墖瀹屾垚")
            
            

        # 娉曚护绾归娴嬭皟鐢?        _predictSingleBoldWrinkle(
            cmd_param["img_url"],
            cmd_param["out_put_url"],
            cmd_param["model_dir"],
            img_size=1024,
            device='cuda',
            gpu_id=cmd_param.get("gpuid", 0)
        )


    """/////---------------------------------------------------------------------------------------------
    ------------------------------------------------------------------------------------------------
    --------------------------------------------銆愮矖绾圭粨鏉?zhl銆?-------------------------------------------
    -------------------------------------------------------------------------------------------------////
    """





def dice_coeff(pred, target, thr=0.5):
    pred = (pred > thr).float()   # 鈶?浠?*鐩戞帶**鐢紝璁粌闃舵浠嶇敤杩炵画姒傜巼
    pred = pred.view(-1)
    target = target.view(-1)
    inter = (pred * target).sum()
    eps = 1e-5
    return (2. * inter + eps) / (pred.sum() + target.sum() + eps)

# -------------------------------------------------
# 1. 闃诲鐩村埌鏈夌┖浣?GPU锛岃繑鍥炴渶绌洪棽鍗＄墿鐞嗙紪鍙?# -------------------------------------------------
def _wait_and_pick_free_gpu(threshold=0.6, interval=30):
    """闃诲鐩村埌妫€娴嬪埌鏈夌┖浣?GPU锛堟樉瀛樺崰鐢?< threshold锛夛紝杩斿洖鏈€绌洪棽閭ｅ紶鍗＄殑鐗╃悊缂栧彿"""
    pynvml.nvmlInit()
    device_count = pynvml.nvmlDeviceGetCount()
    if device_count == 0:
        raise RuntimeError("鏈娴嬪埌浠讳綍 NVIDIA GPU")
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
            print(f"[GPU] 閫夋嫨鏈€绌洪棽鍗★細{best_id}锛屾樉瀛樺崰鐢?{best_free*100:.1f}%")
            return best_id

        print(f"[GPU] 鎵€鏈夊崱鏄惧瓨鍗犵敤鍧団墺{threshold*100:.0f}%锛寋interval}s 鍚庨噸璇曗€?)
        time.sleep(interval)

