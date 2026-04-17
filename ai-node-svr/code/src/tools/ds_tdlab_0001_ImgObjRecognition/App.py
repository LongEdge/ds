import sys
import os
import requests
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from ultralytics import YOLO
import json
import time
from datetime import datetime
from minio import Minio
from minio.error import S3Error

util_path = os.path.abspath(__file__)
####鏈湴鏂囦欢璋冭瘯鐨勬椂鍊欓渶瑕?#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
util_path = os.path.join(os.path.dirname(util_path), '../../../../code')
#<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
sys.path.append(util_path)
print(util_path)


from src.Util import *
from io import BytesIO

class CApp:
    def __init__(self,param):
        """
        鍒濆鍖栬棰戝鐞嗘湇鍔★細鎻愬彇鏈夋晥鍥剧墖锛堝垎绫绘娴嬶級

        """
        self.node_cfg = node_cfg
        # 鎬讳綋鍙橀噺
        ### api鍙傛暟
        self.openapi_baseurl = "http://<REDACTED_URL>".strip('/') #寮€鏀惧钩鍙扮殑api鎺ュ彛鐨勫墠缂€
        ### 鐘舵€佸彉閲?        self.deal_percent = 0 # 杩涘害, 涓€瀹氬瓨鍦?        self.deal_time = int(time.time()) # 澶勭悊鏃堕棿, 涓嶄竴瀹氬瓨鍦?        self.deal_msg = "ready" # 澶勭悊淇℃伅, 涓嶄竴瀹氬瓨鍦?        ### 宸ュ叿榛樿宸ヤ綔鐩綍
        self.out_path = "{}/src/tools/out".format(util_path)
        self.cache_path = "{}/src/tools/datacache".format(util_path)
        self.model_predict_path = "{}/src/tools/predict_model/".format(util_path) # 棰勬祴妯″瀷鐨勫湴鍧€, 浜嬪厛瀛樻斁濂?        
        # vedio-split 涓撳睘鍙橀噺
        ### minio鐩稿叧
        self.minio_client = None
        self.bucket_name = None
        ### 鏌ヨ
        self.curr_groups_id = None # 鏌ヨ褰撳墠搴旇鍒涘缓鍒板摢涓猤roup-xxx
        self.curr_group_num = 0 # 褰撳墠group-xxx涓嬫湁澶氬皯涓暟鎹?        
        
    """
    妫€鏌roups_id鏄惁瀛樺湪锛屼笉瀛樺湪鍒欏垱寤?    鍚屾椂杩斿洖璇roupid涓嬬殑鏁版嵁鏁伴噺
    """
    def check_groups_id(self,minio_prefix_path):
        all_groups = []
        all_group_objects = self.minio_client.list_objects(self.bucket_name, prefix=minio_prefix_path+"/")
        print(all_group_objects)
        for item in all_group_objects:
            all_groups.append(item.object_name)
        groups_id = get_max_group_id(all_groups)

        #杩斿洖group鍐呯殑鏁伴噺
        img_prefix = minio_prefix_path +"/"+ groups_id + "/src-img/"
        print(img_prefix)
        obj = self.minio_client.list_objects(self.bucket_name, prefix=img_prefix)
        cnt = 0
        for _ in obj:
            cnt += 1

        return groups_id,cnt

    """
    鏌ヨminio鐨勮繛鎺ヤ俊鎭?骞跺垱寤簃inio-client
    """
    def get_minio_info_byname(self,minio_conn_name):
        url = self.openapi_baseurl + '/aibase/dataServerConfig/getInfo/'+minio_conn_name
        try:
            res = requests.get(url)
            resjson  = res.json()
        except Exception as e:
            self.logger.error('get minio stream info error')
            return -1
        if 200 == resjson['code']:
            conn_info = resjson['data']['content']
            conn_info_json = json.loads(conn_info)
            if self.minio_client == None:
                minio_endpoint = conn_info_json['endpoint']
                minio_access_key=conn_info_json['accessKey']
                minio_secret_key=conn_info_json['secretKey']
                minio_bucket = conn_info_json['bucketName']
                self.minio_client = Minio(
                    minio_endpoint,
                    access_key=minio_access_key,
                    secret_key=minio_secret_key,
                    secure=False
                )
                self.bucket_name = minio_bucket
            return 0

    
    def ProcessTask(self, params):
        
        """
        @param: dict 鍖呭惈浜嗕綘鎻愪氦鐨勫嚱鏁板叆鍙備俊鎭紝浣犺嚜琛岃В鏋?        """
        for param in params:
            funname = param["dtype"]
            if funname == "vedio-split" :
                self.StartTask_GetImgFromVedio(param)
            elif funname == "vedio-imgrecogintion" :
                self.StartTask_GetImgFromVedioAndRecognition(param)
            elif funname == "group-label-delete" :
                self.StartTask_GroupLabelDelete(param)
            elif funname == "group-combine" :
                self.StartTask_GroupCombine(param)
        
        print("\nProcessing completed")


    def StartTask_GetImgFromVedio(self,param):
        """
        param:浼犲叆鍐呭
        """
        # 鍔犺浇妯″瀷
        cls_model = YOLO('{}yolov8x-cls.pt'.format(self.model_predict_path))
        det_model = YOLO('{}yolov8n.pt'.format(self.model_predict_path))
        threshold = 0.8

        print(self.model_predict_path)
        # 璇诲彇鍙傛暟
        srcdata_url = param['srcdata-url']
        dconn_name = param['outdir']['dconn_name']
        self.get_minio_info_byname(dconn_name) # 鏌ヨminio杩炴帴淇℃伅

        out_prefix_path = param['outdir']['prefix_path'].strip('/') #鍘婚櫎棣栦綅鐨?绗﹀彿
        self.curr_groups_id, self.curr_group_num = self.check_groups_id(out_prefix_path) # 鏌ヨ褰撳墠搴旇鍒涘缓鍒板摢涓猤roup-xxx
        print(srcdata_url)
        print(dconn_name)
        print(self.curr_groups_id, self.curr_group_num)
    
        # 鎵撳紑瑙嗛鏂囦欢
        cap = cv2.VideoCapture(srcdata_url)
        if not cap.isOpened():
            raise ValueError("Error opening video file")

        # 鍒濆鍖栧鐓у抚
        ret, prev_frame = cap.read()
        if not ret:
            raise ValueError("Error reading initial frame")

        frame_count = 0

        while True:
            ret, current_frame = cap.read()
            if not ret:
                break

            frame_count += 1
            if frame_count % 120 != 0:  # 姣?s宸﹀彸澶勭悊涓€娆?                continue
            print(f"\nProcessing frame {frame_count}")

            # 姝ラ1锛氬抚鐩镐技搴︽瘮杈?            similarity = self.calculate_frame_similarity(prev_frame, current_frame)
            print(f"SSIM similarity: {similarity:.4f}")

            if similarity < threshold:
                try:
                    # 姝ラ2锛氬浘鍍忓垎绫?                    class_name = self.classify_image(current_frame, cls_model)
                    print(f"Classification result: {class_name}")

                    # 姝ラ3锛氱洰鏍囨娴?                    detection_result = self.detect_objects(current_frame, det_model)
                    
                    # 淇濆瓨缁撴灉
                    self.save_results_img(
                        current_frame, 
                        detection_result["has_detections"],
                        detection_result["detections"],
                        class_name,
                        self.out_path,
                        det_model,
                        out_prefix_path)
                    # 鏇存柊瀵圭収甯?                    prev_frame = current_frame.copy()

                except Exception as e:
                    print(f"Processing error: {str(e)}")
            else:
                print("Frame skipped (similarity above threshold)")

        cap.release()

    def StartTask_GetImgFromVedioAndRecognition(self,param):
        """
        param:浼犲叆鍐呭
        """
        # 鍔犺浇妯″瀷
        cls_model = YOLO('{}yolov8x-cls.pt'.format(self.model_predict_path))
        det_model = YOLO('{}yolov8n.pt'.format(self.model_predict_path))
        threshold = 0.8

        print(self.model_predict_path)
        # 璇诲彇鍙傛暟
        srcdata_url = param['srcdata-url']
        dconn_name = param['outdir']['dconn_name']
        self.get_minio_info_byname(dconn_name) # 鏌ヨminio杩炴帴淇℃伅

        out_prefix_path = param['outdir']['prefix_path'].strip('/') #鍘婚櫎棣栦綅鐨?绗﹀彿
        self.curr_groups_id, self.curr_group_num = self.check_groups_id(out_prefix_path) # 鏌ヨ褰撳墠搴旇鍒涘缓鍒板摢涓猤roup-xxx
        print(srcdata_url)
        print(dconn_name)
        print(self.curr_groups_id, self.curr_group_num)
    
        # 鎵撳紑瑙嗛鏂囦欢
        cap = cv2.VideoCapture(srcdata_url)
        if not cap.isOpened():
            raise ValueError("Error opening video file")

        # 鍒濆鍖栧鐓у抚
        ret, prev_frame = cap.read()
        if not ret:
            raise ValueError("Error reading initial frame")

        frame_count = 0

        while True:
            ret, current_frame = cap.read()
            if not ret:
                break

            frame_count += 1
            if frame_count % 120 != 0:  # 姣?s宸﹀彸澶勭悊涓€娆?                continue
            print(f"\nProcessing frame {frame_count}")

            # 姝ラ1锛氬抚鐩镐技搴︽瘮杈?            similarity = self.calculate_frame_similarity(prev_frame, current_frame)
            print(f"SSIM similarity: {similarity:.4f}")

            if similarity < threshold:
                try:
                    # 姝ラ2锛氬浘鍍忓垎绫?                    class_name = self.classify_image(current_frame, cls_model)
                    print(f"Classification result: {class_name}")

                    # 姝ラ3锛氱洰鏍囨娴?                    detection_result = self.detect_objects(current_frame, det_model)
                    
                    # 淇濆瓨缁撴灉
                    self.save_results_imgjson(
                        current_frame, 
                        detection_result["has_detections"],
                        detection_result["detections"],
                        class_name,
                        self.out_path,
                        det_model,
                        out_prefix_path)
                    # 鏇存柊瀵圭収甯?                    prev_frame = current_frame.copy()

                except Exception as e:
                    print(f"Processing error: {str(e)}")
            else:
                print("Frame skipped (similarity above threshold)")

        cap.release()

    def StartTask_GroupLabelDelete(self,param):
        """
        鍒犻櫎娌℃湁瀵瑰簲鍥剧墖鐨勬爣绛炬枃浠?        
        鍙傛暟:
            param (dict): 鍖呭惈浠ヤ笅閿€?                - dtype: "group-label-delete" (浠诲姟绫诲瀷)
                - dconn_name: MinIO杩炴帴鍚嶇О (鐢ㄤ簬浠庨厤缃幏鍙栬繛鎺ヤ俊鎭?
                - group-url: 瑕佸鐞嗙殑group璺緞 (濡?"/AIDataManage/ImgObjRecognition/group-00002")
        """
        try:
            # 鑾峰彇鍙傛暟
            group_url = param.get("group-url", "").strip("/")
            
            # 楠岃瘉group璺緞鏍煎紡
            if not group_url.startswith("AIDataManage/ImgObjRecognition/group-"):
                raise ValueError("鏃犳晥鐨刧roup璺緞锛屾牸寮忓簲涓? AIDataManage/ImgObjRecognition/group-XXXXX")
            
            # 鑾峰彇鐩綍璺緞
            base_path = f"{group_url}/"
            src_img_path = f"{base_path}src-img/"
            src_label_path = f"{base_path}src-label/"
            dst_label_path = f"{base_path}dst-label/"
            
            print(f"寮€濮嬫竻鐞嗘棤鏁堟爣绛炬枃浠讹紝group璺緞: {base_path}")
            dconn_name = param['dconn_name']
            self.get_minio_info_byname(dconn_name) # 鏌ヨminio杩炴帴淇℃伅
            
            # 1. 鑾峰彇鎵€鏈夊浘鐗囨枃浠跺垪琛?(鍘婚櫎鎵╁睍鍚?
            img_objects = self.minio_client.list_objects(self.bucket_name, prefix=src_img_path, recursive=True)
            valid_files = set()
            
            for obj in img_objects:
                if not obj.object_name.endswith(('.jpg', '.jpeg', '.png')):
                    continue
                # 鑾峰彇涓嶅甫鎵╁睍鍚嶇殑鏂囦欢鍚?                base_name = os.path.splitext(os.path.basename(obj.object_name))[0]
                valid_files.add(base_name)
            
            print(f"鎵惧埌 {len(valid_files)} 涓湁鏁堝浘鐗囨枃浠?)
            
            # 2. 妫€鏌ュ苟娓呯悊src-label鐩綍
            deleted_count = self._clean_orphaned_labels(
                self.bucket_name, src_label_path, valid_files, "src-label")
            
            # 3. 妫€鏌ュ苟娓呯悊dst-label鐩綍
            deleted_count += self._clean_orphaned_labels(
                self.bucket_name, dst_label_path, valid_files, "dst-label")
            
            print(f"娓呯悊瀹屾垚锛屽叡鍒犻櫎 {deleted_count} 涓棤鏁堟爣绛炬枃浠?)
            self.deal_msg = f"娓呯悊瀹屾垚锛屽垹闄?{deleted_count} 涓棤鏁堟爣绛?
            
        except Exception as e:
            self.deal_msg = f"娓呯悊澶辫触: {str(e)}"
            raise
    
    def StartTask_GroupCombine(self,param):
        # 鑾峰彇鍙傛暟
        group1 = param["group1-url"].strip("/") + "/"
        group2 = param["group2-url"].strip("/") + "/"
        dconn_name = param['dconn_name']
        self.get_minio_info_byname(dconn_name) # 鏌ヨminio杩炴帴淇℃伅

        # 鍚堝苟涓変釜瀛愮洰褰?        for folder in ["src-img/", "src-label/", "dst-label/"]:
            # 鍒楀嚭婧愬垎缁勬枃浠?            files = self.minio_client.list_objects(self.bucket_name, prefix=group2 + folder)
            
            # 澶嶅埗姣忎釜鏂囦欢
            for file in files:
                src = file.object_name
                filename = os.path.basename(src)
                print('270'+filename)
                dst = group1 + folder + filename
                src = group2 + folder + filename
                print(src)
                
                # 澶勭悊閲嶅悕鏂囦欢
                if self._file_exists(self.minio_client, self.bucket_name, dst):
                    name, ext = os.path.splitext(filename)
                    dst = group1 + folder + f"{name}_merged{ext}"
                
                # 鎵ц澶嶅埗
                print(dst)
                print(src)
                copy_source = f"/{self.bucket_name}/{src}"
                self.minio_client.copy_object(
                    self.bucket_name, 
                    dst, 
                    copy_source
                    )
                print(f"Copied: {src} -> {dst}")
    
    def GetTaskExecInfo(self):
        """
        @param: None 杩欓噷鏄杩斿洖鐨勬墽琛岃繘搴︾瓑鍏朵粬淇℃伅
        """
        return {
            "taskProcessingVal": self.deal_percent,
            "deal_time": self.deal_time,
            "deal_msg": self.deal_msg
        }

    def GetTaskReport(self):
        return 1

    def GetTaskFinalReport(self):
        return 1

    def Cleanup(self):
        """
        @param: None 浣犱繚瀛樼殑绗笁鏂瑰鐞嗚繃绋?        """
        print("娓呯悊浠诲姟")
    
    def calculate_frame_similarity(self, frame1, frame2):
        """璁＄畻涓ゅ抚涔嬮棿鐨勭粨鏋勭浉浼兼€ф寚鏁帮紙SSIM锛?""
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        score, _ = ssim(gray1, gray2, full=True)
        return score

    def classify_image(self, frame, model):
        """浣跨敤YOLO鍒嗙被妯″瀷杩涜鍥惧儚鍒嗙被"""
        results = model(frame)
        class_id = results[0].probs.top1
        return results[0].names[class_id]

    def detect_objects(self, frame, model):
        """浣跨敤YOLO妫€娴嬫ā鍨嬭繘琛岀洰鏍囨娴?""
        results = model(frame)
        boxes = results[0].boxes
        # 鍒ゆ柇鏄惁瀛樺湪鏈夋晥妫€娴?        has_detections = len(boxes.cls) > 0  # 閫氳繃绫诲埆ID鐨勬暟閲忓垽鏂?
        return {
            "annotated_frame": results[0].plot(),
            "detections": boxes,
            "has_detections": has_detections
        }

    def _upload_to_minio(self, object_name, image_data):
        """涓婁紶鍥剧墖鏁版嵁鍒癕inIO妗?""
        try:
            image_stream = BytesIO(image_data)
            self.minio_client.put_object(
                self.bucket_name,
                object_name,
                image_stream,
                length=len(image_data),
                content_type='image/jpeg'
            )
            return True
        except S3Error as e:
            print(f"涓婁紶鍒癕inIO澶辫触: {e}")
            return False
    
    def results_uplo<REDACTED_USERNAME>io(self,frame):
        self._upload_to_minio()
    
    def save_results_img(self, frame, has_detections, detections, class_name, output_dir, det_model,out_prefix_path):
        """淇濆瓨澶勭悊缁撴灉锛堝浘鐗?JSON锛夛紝鎸夌被鍒垎鏂囦欢澶瑰瓨鍌?        
        鐩綍缁撴瀯锛?        output_dir/
        鈹溾攢鈹€ images/
        鈹?  鈹溾攢鈹€ class1/
        鈹?  鈹?  鈹溾攢鈹€ class1_20230512103000_001.jpg
        鈹?  鈹?  鈹斺攢鈹€ ...
        鈹?  鈹溾攢鈹€ class2/
        鈹?  鈹?  鈹斺攢鈹€ ...
        鈹?  鈹斺攢鈹€ ...
        鈹斺攢鈹€ labels/
            鈹溾攢鈹€ class1/
            鈹?  鈹溾攢鈹€ class1_20230512103000_001.json
            鈹?  鈹斺攢鈹€ ...
            鈹溾攢鈹€ class2/
            鈹?  鈹斺攢鈹€ ...
            鈹斺攢鈹€ ...
        """
        # 鍒涘缓鍩虹鐩綍缁撴瀯
        images_dir = os.path.join(output_dir, "images")
        labels_dir = os.path.join(output_dir, "labels")

        # 妫€鏌ュ苟鍒涘缓鐩綍锛堝鏋滀笉瀛樺湪锛?        for dir_path in [images_dir, labels_dir]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
                print(f"Created directory: {dir_path}")   

        # 鍒涘缓绫诲埆瀛愮洰褰?        class_images_dir = os.path.join(images_dir, class_name)
        class_labels_dir = os.path.join(labels_dir, class_name)

        # 妫€鏌ュ苟鍒涘缓绫诲埆瀛愮洰褰曪紙濡傛灉涓嶅瓨鍦級
        for dir_path in [class_images_dir, class_labels_dir]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
                print(f"Created class directories for: {class_name}")

        # 鐢熸垚缁熶竴鏂囦欢鍚嶏紙涓嶅惈鎵╁睍鍚嶏級
        now = datetime.now() # 鏃堕棿鎴?        timestamp = now.strftime("%Y%m%d%H%M%S")
        base_name = f"{class_name}_{timestamp}" # 澶勭悊鐨勬枃浠跺悕绉?        self.deal_msg = base_name # 鏍囧噯鍖栨棩鏈?        self.deal_time = int(time.mktime(now.timetuple())) # 鏃堕棿鎴?

        if self.curr_group_num > 999: # 瓒呰繃1000涓氨鎹?            self.curr_groups_id = get_next_group_id(self.curr_groups_id)
            self.curr_group_num = 0

        # 1. 淇濆瓨鍥剧墖鍒扮被鍒洰褰?        img_path = os.path.join(class_images_dir, f"{base_name}.jpg")
        local_file_jpg = img_path # 鏈湴鍥剧墖璺緞
        remote_file_jpg = out_prefix_path+"/" + self.curr_groups_id + "/" + f"{base_name}.jpg" # 杩滅▼瀛樺偍璺緞
        width = frame.shape[1]
        height = frame.shape[0]
        # 2. 鍑嗗JSON鏁版嵁    
        if has_detections:
            cv2.imwrite(local_file_jpg, frame)
            # 4. 涓婁紶鍒癿inio
            """
            -----group-001
            -----group-002
            """
            self.minio_client.fput_object(self.bucket_name, remote_file_jpg, local_file_jpg)
            self.curr_group_num += 1
            # 5. 鍒犻櫎jpg鍜宩son
            os.remove(local_file_jpg)
        
    def save_results_imgjson(self, frame, has_detections, detections, class_name, output_dir, det_model,out_prefix_path):
        """淇濆瓨澶勭悊缁撴灉锛堝浘鐗?JSON锛夛紝鎸夌被鍒垎鏂囦欢澶瑰瓨鍌?        
        鐩綍缁撴瀯锛?        output_dir/
        鈹溾攢鈹€ images/
        鈹?  鈹溾攢鈹€ class1/
        鈹?  鈹?  鈹溾攢鈹€ class1_20230512103000_001.jpg
        鈹?  鈹?  鈹斺攢鈹€ ...
        鈹?  鈹溾攢鈹€ class2/
        鈹?  鈹?  鈹斺攢鈹€ ...
        鈹?  鈹斺攢鈹€ ...
        鈹斺攢鈹€ labels/
            鈹溾攢鈹€ class1/
            鈹?  鈹溾攢鈹€ class1_20230512103000_001.json
            鈹?  鈹斺攢鈹€ ...
            鈹溾攢鈹€ class2/
            鈹?  鈹斺攢鈹€ ...
            鈹斺攢鈹€ ...
        """
        # 鍒涘缓鍩虹鐩綍缁撴瀯
        images_dir = os.path.join(output_dir, "images")
        labels_dir = os.path.join(output_dir, "labels")

        # 妫€鏌ュ苟鍒涘缓鐩綍锛堝鏋滀笉瀛樺湪锛?        for dir_path in [images_dir, labels_dir]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
                print(f"Created directory: {dir_path}")   

        # 鍒涘缓绫诲埆瀛愮洰褰?        class_images_dir = os.path.join(images_dir, class_name)
        class_labels_dir = os.path.join(labels_dir, class_name)

        # 妫€鏌ュ苟鍒涘缓绫诲埆瀛愮洰褰曪紙濡傛灉涓嶅瓨鍦級
        for dir_path in [class_images_dir, class_labels_dir]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
                print(f"Created class directories for: {class_name}")

        # 鐢熸垚缁熶竴鏂囦欢鍚嶏紙涓嶅惈鎵╁睍鍚嶏級
        now = datetime.now() # 鏃堕棿鎴?        timestamp = now.strftime("%Y%m%d%H%M%S")
        base_name = f"{class_name}_{timestamp}" # 澶勭悊鐨勬枃浠跺悕绉?        self.deal_msg = base_name # 鏍囧噯鍖栨棩鏈?        self.deal_time = int(time.mktime(now.timetuple())) # 鏃堕棿鎴?

        if self.curr_group_num > 999: # 瓒呰繃1000涓氨鎹?            self.curr_groups_id = get_next_group_id(self.curr_groups_id)
            self.curr_group_num = 0

        # 1. 淇濆瓨鍥剧墖鍒扮被鍒洰褰?        img_path = os.path.join(class_images_dir, f"{base_name}.jpg")
        local_file_jpg = img_path # 鏈湴鍥剧墖璺緞
        remote_file_jpg = out_prefix_path+"/" + self.curr_groups_id + "/src-img/" + f"{base_name}.jpg" # 杩滅▼瀛樺偍璺緞
        width = frame.shape[1]
        height = frame.shape[0]
        # 2. 鍑嗗JSON鏁版嵁    
        if has_detections:
            cv2.imwrite(local_file_jpg, frame)
            json_data = []
            for box in detections:
                # 鑾峰彇鍧愭爣銆佺疆淇″害鍜岀被鍒獻D
                xyxy = box.xyxy.cpu().tolist()[0]  # 杞崲涓哄垪琛ㄦ牸寮?                cls_id = box.cls.item()             # 绫诲埆ID
                cls_name = det_model.names[int(cls_id)] # 绫诲埆鍚嶇О

                xywh = xyxy_to_xywh(xyxy)
                json_data.append({
                    "original_width": width, 
                    "original_height": height, 
                    "image_rotation": 0, 
                    "value": {
                        "x": xywh[0] / width * 100, 
                        "y": xywh[1] / height * 100, 
                        "width": xywh[2] / width * 100, 
                        "height": xywh[3] / height * 100, 
                        "rotation": 0, 
                        "rectanglelabels": [
                            cls_name
                        ]
                    }, 
                    "id": "WjCgZ2_TNw", 
                    "from_name": "label", 
                    "to_name": "img-1", 
                    "type": "rectanglelabels", 
                    "origin": "manual"
                })

            final_format = {
                "data": 
                { 
                    "img": "s3://{}/{}/{}/{}/{}".format(self.bucket_name,out_prefix_path, self.curr_groups_id, "src-img", base_name+".jpg")},
                "annotations": [],
                "predictions": 
                [
                    {
                        "result": json_data
                    }
                ]
            }

            # 淇濆瓨JSON鍒板搴旂殑labels绫诲埆鐩綍锛堜笌鍥剧墖鍚屽悕锛?            json_path = os.path.join(class_labels_dir, f"{base_name}.json")
            with open(json_path, 'w') as f:
                json.dump(final_format, f, indent=2)


            # 3. 鑾峰彇group-xxx鐨勮繖涓獂xx, 鐒跺悗寤虹珛xxx
            local_file_json = json_path  # 鏈湴json璺緞
            remote_file_json = out_prefix_path+"/" + self.curr_groups_id + "/src-label/" + f"{base_name}.json" # 杩滅▼json璺緞

            print(remote_file_jpg)
            # 4. 涓婁紶鍒癿inio
            """
            -----group-001
            |--src-img
            |--src-label
            |--dst-label
            -----group-002
            |--src-img
            |--src-label
            |--ds
            """
            self.minio_client.fput_object(self.bucket_name, remote_file_jpg, local_file_jpg)
            self.minio_client.fput_object(self.bucket_name, remote_file_json, local_file_json)

            self.curr_group_num += 1
            # 5. 鍒犻櫎jpg鍜宩son
            os.remove(local_file_jpg)
            os.remove(local_file_json)

    def _clean_orphaned_labels(self, bucket_name, label_path, valid_files, label_type):
            """
            娓呯悊鎸囧畾鏍囩鐩綍涓嬬殑瀛ょ珛鏂囦欢
            
            鍙傛暟:
                bucket_name: 瀛樺偍妗跺悕绉?                label_path: 鏍囩鐩綍璺緞
                valid_files: 鏈夋晥鏂囦欢鍚嶇殑闆嗗悎
                label_type: 鏍囩绫诲瀷鎻忚堪 (鐢ㄤ簬鏃ュ織)
            
            杩斿洖:
                鍒犻櫎鐨勬枃浠舵暟閲?            """
            deleted_count = 0
            label_objects = self.minio_client.list_objects(bucket_name, prefix=label_path, recursive=True)
            
            for obj in label_objects:
                if not obj.object_name.endswith('.json'):
                    continue
                    
                # 鑾峰彇涓嶅甫鎵╁睍鍚嶇殑鏂囦欢鍚?                base_name = os.path.splitext(os.path.basename(obj.object_name))[0]
                
                if base_name not in valid_files:
                    try:
                        self.minio_client.remove_object(bucket_name, obj.object_name)
                        print(f"鍒犻櫎瀛ょ珛{label_type}鏂囦欢: {obj.object_name}")
                        deleted_count += 1
                    except S3Error as e:
                        print(f"鍒犻櫎鏂囦欢澶辫触 {obj.object_name}: {e}")
            
            return deleted_count
    
    def _file_exists(self, minio, bucket, path):
        """妫€鏌ユ枃浠舵槸鍚﹀瓨鍦?""
        try:
            minio.stat_object(bucket, path)
            return True
        except:
            return False
    

if __name__ == '__main__':
    ####鏈湴鏂囦欢璋冭瘯鐨勬椂鍊欓渶瑕佹妸17琛岀殑娉ㄩ噴鍘绘帀
    app = CApp()
    urls = ["http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>",
"http://<REDACTED_URL>"]
    for url in urls:
        param=[{
            "dtype": "vedio-split",
            "srcdata-url": url,
            "outdir": {
                "dconn_name": "<REDACTED_CONN>",
                "prefix_path": "DsDataCollection/宸ュ巶宸℃鍥惧儚"
            }
        }]
        app.ProcessTask(param)

    # for url in urls:
    #     param=[{
    #         "dtype": "vedio-imgrecogintion",
    #         "srcdata-url": url,
    #         "outdir": {
    #             "dconn_name": "<REDACTED_CONN>",
    #             "prefix_path": "AIDataManage/ImgObjRecognition/"
    #         }
    #     }]
    #     app.ProcessTask(param)
    
    # param=[
    #     {
    #     "dtype": "group-label-delete",
    #     "dconn_name": "<REDACTED_CONN>",
    #     "group-url": "AIDataManage/ImgObjRecognition/group-00002"
    #     }
    # ]

    # param=[
    #     {
    #     "dtype": "group-combine",
    #     "dconn_name": "<REDACTED_CONN>",
    #     "group1-url": "AIDataManage/ImgObjRecognition/group-00001",
    #     "group2-url": "AIDataManage/ImgObjRecognition/group-00002",
    #     }
    # ]
    # app.ProcessTask(param)
    
    

    # 鑳℃棴涓滄祴璇曚唬鐮?    # minio_endpoint = "<PRIVATE_IP>:9000"
    # minio_access_key = "<REDACTED_USERNAME>"
    # minio_secret_key = "<REDACTED_PASSWORD>"
    # bucket_name = "ds-data-ware"
    # minio_client = Minio(
    #     minio_endpoint,
    #     access_key=minio_access_key,
    #     secret_key=minio_secret_key,
    #     secure=False
    # )
    # # 鑷敤, 澶栭儴涓嶅彲鏀瑰彉
    # all_group_objects = minio_client.list_objects('ds-data-ware', prefix='AIDataManage/ImgObjRecognition/')
    # all_groups = []

    # for item in all_group_objects:
    #         all_groups.append(item.object_name)
    # print(all_groups)
    # max_num = 0
    # import re
    # pattern = re.compile(r"group-(\d+)")
    
    # for name in all_groups:
    #     match = pattern.fullmatch(name)
    #     print(match)
    #     if match:
    #         num = int(match.group(1))
    #         if num > max_num:
    #             max_num = num
    # print(max_num)
    # next_num = max_num + 1
    # # 鑷姩閫傞厤鍓嶅0鐨勫搴︼紝姣斿 group-001銆乬roup-0123
    # width = len(match.group(1)) if match else 5
    # print(f"group-{next_num:0{width}d}")
