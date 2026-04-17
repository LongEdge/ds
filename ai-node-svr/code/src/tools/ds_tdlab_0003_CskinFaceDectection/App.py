import os
import dlib
import json
import xml.etree.ElementTree as ET
import shutil
import glob
import cv2
import time
from datetime import datetime
from minio import Minio
from minio.error import S3Error

class CApp:
    def __init__(self):
        """
        鍒濆鍖杁lib浜鸿劯鍏抽敭鐐规ā鍨嬭缁冩湇鍔?        鍙傛暟:
            minio_endpoint: MinIO鏈嶅姟鍣ㄥ湴鍧€ (e.g. "116.62.238.72:9000")
            minio_access_key: MinIO璁块棶瀵嗛挜
            minio_secret_key: MinIO绉樺瘑瀵嗛挜
            bucket_name: 鐩爣瀛樺偍妗跺悕绉?            secure: 鏄惁浣跨敤HTTPS (榛樿False)
            input_path: minio瀛樺偍鍦板潃
            model_path: minio妯″瀷瀛樻斁鍦板潃
            cache_path: 鏈嶅姟鍣ㄦ殏瀛樺湴鍧€
        """
        self.minio_endpoint = None
        self.minio_access_key = None
        self.minio_secret_key = None
        self.bucket_name = None
        self.deal_percent = 0 # 杩涘害, 涓€瀹氬瓨鍦?        self.deal_time = 0 #澶勭悊鏃堕棿
        self.deal_msg = "ready" # 澶勭悊淇℃伅
        self.params = None # 鍙傛暟
        self.model_name = None # 浜鸿劯浜斿畼鐐规ā鍨?        self.model_svm = None # 浜鸿劯妫€娴嬪櫒妯″瀷
        self.save_and_predict_path = "src/tools/data/"
        self.model_save_path = "src/tools/models/" # 瀛樻斁妯″瀷浣嶇疆
        self.cache_path = "src/tools/datacache/" # 瀛樻斁鏁版嵁涓棿杩囩▼
        self.model_dat_path = None # 浜鸿劯浜斿畼鐐规ā鍨嬭矾寰?        self.model_svm_path = None # 浜鸿劯浜斿畼鎺㈡祴鍣ㄦā鍨嬭矾寰?
    def Init(self, params):
        """
        param:浼犲叆鍐呭
        """
        self.params = params
        # 1. 鍒濆鍖栭厤缃?        for param in self.params:
            funcname = param["dtype"]
            if funcname == "model-train":
                self.Init_model_train(param)
            elif funcname == "relabel-for-group":
                self.Init_relabel_for_group(param)
            

    def Init_model_train(self, param):
        """
        @param: dict 鍖呭惈浜嗕綘鎻愪氦鐨勫嚱鏁板叆鍙備俊鎭紝浣犺嚜琛岃В鏋?        """
        inoutdata = param['inoutdata']
        dconn_name = inoutdata['dconn_name']
        dconn_config = {
            "endpoint": "dslancher.tpddns.cn:9900", 
            "accessKey": "<REDACTED_USERNAME>", 
            "secretKey": "<REDACTED_PASSWORD>", 
            "bucket_name": "ds-data-ware", 
        }
        minio_endpoint =  dconn_config['endpoint']
        minio_access_key = dconn_config['accessKey']
        minio_secret_key = dconn_config['secretKey']
        self.bucket_name = dconn_config['bucket_name']
        # 2. 鍒濆鍖朚inIO瀹㈡埛绔?        self.minio_client = Minio(
            minio_endpoint,
            access_key=minio_access_key,
            secret_key=minio_secret_key,
            secure=False
        )

    def Init_relabel_for_group(self, param):
        """
        @param: dict 鍖呭惈浜嗕綘鎻愪氦鐨勫嚱鏁板叆鍙備俊鎭紝浣犺嚜琛岃В鏋?        """
        inoutdata = param['inoutdata']
        dconn_name = inoutdata['dconn_name']
        dconn_config = {
            "endpoint": "dslancher.tpddns.cn:9900", 
            "accessKey": "<REDACTED_USERNAME>", 
            "secretKey": "<REDACTED_PASSWORD>", 
            "bucket_name": "ds-data-ware", 
        }
        self.model_landmark_name = inoutdata['model_landmark_name']
        self.model_svm_name = inoutdata['model_svm_name']
        if "" == self.model_landmark_name:  # 閫夋嫨棰勬祴鐨勪汉鑴稿畾浣嶇偣妯″瀷
            self.model_landmark_name = "p81.dat" # 閫夋嫨棰勬祴鐨勪汉鑴告帰娴嬪櫒妯″瀷
        if "" == self.model_svm_name:
            self.model_svm_name = "middle.svm"

        minio_endpoint =  dconn_config['endpoint']
        minio_access_key = dconn_config['accessKey']
        minio_secret_key = dconn_config['secretKey']
        self.bucket_name = dconn_config['bucket_name']

        # 2. 鍒濆鍖朚inIO瀹㈡埛绔?        self.minio_client = Minio(
            minio_endpoint,
            access_key=minio_access_key,
            secret_key=minio_secret_key,
            secure=False
        )

    def StartTask(self, param):
        """
        @param: dict 鍖呭惈浜嗕綘鎻愪氦鐨勫嚱鏁板叆鍙備俊鎭紝浣犺嚜琛岃В鏋?        """
        for param in self.params:
            
            funcname = param["dtype"]
            if funcname == "relabel-for-group":
                self.relabel_for_group(param)
            
            elif funcname == "relabel-for-all-groups":
                print("relabel-for-all-groups")
            elif funcname == "model-train":
                self.train_model(param)
                

    
    def GetTaskExecInfo(self):
        """
        @param: None 杩欓噷鏄杩斿洖鐨勬墽琛岃繘搴︾瓑鍏朵粬淇℃伅
        """
        return {
            "taskProcessingVal": self.deal_percent
        }


    
    """
    ------------------------------------------------------杩欓儴鍒嗘槸棰勬祴璧峰------------------------------------------------------
    """

    def relabel_for_group(self, param):
        def init_predict_obj(model_dat_path, model_svm_path) -> object:
            """
            @params: None
            @return: obj 妯″瀷瀵硅薄 鍜?浜鸿劯鎺㈡祴鍣ㄥ璞?            """
            detector = dlib.simple_object_detector(model_svm_path)
            predictor = dlib.shape_predictor(model_dat_path)
            return predictor, detector

        def predict_by_model(img, predictor, detector) -> list:
            """
            @params: predictor_obj 妯″瀷瀵硅薄, 
            @params: img_path 鍥剧墖璺緞
            @return: list 棰勬祴缁撴灉
            """
            height, width = img.shape[:2]
            img_resize = cv2.resize(img, (480, 640))
            gray = cv2.cvtColor(img_resize, cv2.COLOR_BGR2RGB)
            try:
                faces = detector(gray, 1)[0]
            except Exception as e:
                faces = dlib.rectangle(0, 0, 480, 640)
            shape = predictor(gray, faces)
            shape_np = [(shape.part(i).x / width * 100, shape.part(i).y / height * 100) for i in range(81)]
            return shape_np

        def deal_img_2_json(predict_path, json_save_prefix, json_save_path, group_name):
            """
            @param: predict_path -> 棰勬祴鐨勮矾寰?            @param: json_save_prefix -> json淇濆瓨鐨勫墠缂€, 鐢ㄤ簬涓婁紶鍒癿inio缁?            @param: json_save_path -> json淇濆瓨鐨勮矾寰? 鍜岄娴嬭矾寰勭浉鍚?            @param: group_name -> 缁勫悕绉? 鐢ㄤ簬涓婁紶鍒癿inio缁?            棰勬祴鏌愪釜璺緞涓嬬殑鎵€鏈夊浘鐗囦负json骞朵笂浼?            """
            # 1. 閬嶅巻鎵€鏈夌殑Jpg鏂囦欢
            file_list = glob.glob(os.path.join(predict_path, '**', '*.jpg'), recursive=True)
            
            model_dat_path = self.model_save_path + self.model_landmark_name
            model_svm_path = self.model_save_path + self.model_svm_name
            # 2. 鍒濆鍖栨ā鍨嬪璞″拰鎺㈡祴鍣ㄥ璞?            predictor, detector = init_predict_obj(model_dat_path, model_svm_path)
            
            # 3. 杈撳嚭鎵€鏈?jpg 鏂囦欢璺緞
            for path in file_list:
                file_name = path.split('/')[-1]
                img = cv2.imread(path)
                # 3.1 棰勬祴鍥剧墖鐨勭偣浣?                self.deal_time = int(time.time())
                self.deal_msg = "predict img: {}".format(file_name)
                p_lists = predict_by_model(img, predictor, detector) # 2d骞抽潰浜斿畼鐐?                height, width, _ = img.shape
                result = []
                for (x, y) in p_lists:
                    result.append({
                        "original_width": width,
                        "original_height": height,
                        "image_rotation": 0,
                        "value": {
                            "x": x,
                            "y": y,
                            "width": 0.3719200371920037,
                            "keypointlabels": ["Face"]
                        },
                        "from_name": "kp-1",
                        "to_name": "img-1",
                        "type": "keypointlabels",
                        "origin": "manual"
                    })
                json_save_prefix1 = json_save_prefix.strip('/')
                S3_PREFIX = 's3://ds-data-ware/{}/{}/src-img/'.format(json_save_prefix1, group_name)
                local_out_path = '{}/{}/src-label/{}'.format(json_save_prefix, group_name, os.path.splitext(file_name)[0] + '.json') # 鏈湴瀛樺偍璺緞
                json_data = {
                    "data": {
                        "img": S3_PREFIX + file_name
                    },
                    "annotations": [],
                    "predictions": [
                        {
                            "result": result
                        }
                    ]
                }

                # 淇濆瓨 JSON 鍒?source 鐩綍
                json_save_result_path = os.path.join(json_save_path, os.path.splitext(file_name)[0] + '.json')
                with open(json_save_result_path, 'w') as f:
                    json.dump(json_data, f, indent=2)


                # 涓婁紶鍒癿inio
                self.deal_time = int(time.time())
                self.deal_msg = "Upload: {} to {}".format(json_save_result_path, local_out_path)
                self.minio_client.fput_object(self.bucket_name, local_out_path, json_save_result_path)

        def download_specific_group(remote_group_path, save_and_predict_path):
            """
            涓嬭浇鏌愪釜group-xxxx鍒版煇涓洰褰曚笅
            """
            remote_group_path += "/src-img/"
            for obj in self.minio_client.list_objects(self.bucket_name, prefix=remote_group_path, recursive=True):
                # 鏋勯€犳湰鍦版枃浠跺畬鏁磋矾寰?                relative_path = obj.object_name.split('/')[-1]
                local_path = os.path.join(save_and_predict_path, relative_path)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                # 涓嬭浇瀵硅薄鍒版湰鍦拌矾寰?                self.minio_client.fget_object(self.bucket_name, obj.object_name, local_path)
                self.deal_time = int(time.time())
                self.deal_msg = "Downloaded: {} to {}".format(obj.object_name, local_path)
                print("Downloaded: {} to {}".format(obj.object_name, local_path))


        remote_group_path = param['inoutdata']['url']
        if remote_group_path.endswith('/'): # 淇濊瘉杈撳叆鐨勭洰褰曠粷瀵规纭? 鏃犳枩鏉?            remote_group_path = remote_group_path.rstrip('/')
        group_name = remote_group_path.split('/')[-1] # 璁＄畻group_name
        json_save_prefix = remote_group_path[:-len(group_name)] # 璁＄畻闈瀏roup_name
        
        download_specific_group(remote_group_path, self.save_and_predict_path) # 1. 涓嬭浇
        deal_img_2_json(self.save_and_predict_path, json_save_prefix, self.save_and_predict_path, group_name) # 2. 棰勬祴骞朵笂浼?
    
    """
    ------------------------------------------------------杩欓儴鍒嗘槸棰勬祴缁撴潫------------------------------------------------------
    """


    """
    ------------------------------------------------------杩欓儴鍒嗘槸璁粌璧峰------------------------------------------------------
    """
    def train_model(self, param):
        """
        璁粌妯″瀷
        """
        def train_download_group(save_and_predict_path, group_name_lists):
            """
            涓嬭浇澶氫釜group-xxxx鍒版煇涓洰褰曚笅
            """
            remote_group_path = param['inoutdata']['path']
            
            for group_name in group_name_lists:
                remote_group_img_path = remote_group_path + "/" + group_name + "/src-img/"
                remote_group_label_path = remote_group_path + "/" + group_name + "/src-label/"

                for obj in self.minio_client.list_objects(self.bucket_name, prefix=remote_group_img_path, recursive=True):
                    # 鏋勯€犳湰鍦版枃浠跺畬鏁磋矾寰?                    relative_path = obj.object_name.split('/')[-1]
                    local_img_path = os.path.join(save_and_predict_path, group_name, "src-img", relative_path)
                    os.makedirs(os.path.dirname(local_img_path), exist_ok=True)
                    # 涓嬭浇瀵硅薄鍒版湰鍦拌矾寰?                    self.minio_client.fget_object(self.bucket_name, obj.object_name, local_img_path)
                    self.deal_time = int(time.time())
                    self.deal_msg = "Downloaded: {} to {}".format(obj.object_name, local_img_path)
                    print("Downloaded: {} to {}".format(obj.object_name, local_img_path))

                for obj in self.minio_client.list_objects(self.bucket_name, prefix=remote_group_label_path, recursive=True):
                    # 鏋勯€犳湰鍦版枃浠跺畬鏁磋矾寰?                    relative_path = obj.object_name.split('/')[-1]
                    local_label_path = os.path.join(save_and_predict_path, group_name, "src-label", relative_path)
                    os.makedirs(os.path.dirname(local_label_path), exist_ok=True)
                    # 涓嬭浇瀵硅薄鍒版湰鍦拌矾寰?                    self.minio_client.fget_object(self.bucket_name, obj.object_name, local_label_path)
                    self.deal_time = int(time.time())
                    self.deal_msg = "Downloaded: {} to {}".format(obj.object_name, local_label_path)
                    print("Downloaded: {} to {}".format(obj.object_name, local_label_path))

        def train_json_to_xml(json_files_dir, output_xml_path):
            # 鍒涘缓 XML 鏍戠粨鏋?            dataset = ET.Element('dataset')
            name = ET.SubElement(dataset, 'name')
            name.text = 'Training faces'
            images = ET.SubElement(dataset, 'images')
            
            # 閬嶅巻鎸囧畾鏂囦欢澶瑰強鍏跺瓙鏂囦欢澶逛腑鐨勬墍鏈?JSON 鏂囦欢
            dirs = os.listdir(json_files_dir)
            for dir in dirs:
                for root, dirs, files in os.walk(json_files_dir + "/" + dir):
                    for filename in files:
                        if filename.endswith('.json'):
                            json_file_path = os.path.join(root, filename)
                            
                            # 瑙ｆ瀽 JSON 鏂囦欢
                            with open(json_file_path, 'r') as file:
                                data = json.load(file)
                            
                            # 鎻愬彇鍥惧儚璺緞
                            image_file = data['data']['img'].split('/')[-1]  # 鎻愬彇鏂囦欢鍚嶉儴鍒?                            
                            # 鍒涘缓 image 鍏冪礌
                            image = ET.SubElement(images, 'image')
                            image.set('file', image_file)
                            
                            # 鍒涘缓 box 鍏冪礌骞舵坊鍔犲叧閿偣
                            box = ET.SubElement(image, 'box')
                            
                            box.set('top', '0')
                            box.set('left', '0') 
                            box.set('width', '480')
                            box.set('height', '640')  # 鍋囪楂樺害鍜屽搴︾浉鍚?                            
                            # 閬嶅巻 JSON 涓殑鎵€鏈夊叧閿偣骞舵坊鍔犲埌 XML 涓?                            for idx, point in enumerate(data['predictions'][0]['result']):
                                part = ET.SubElement(box, 'part')
                                part.set('name', f'{idx:02}')  # 鏍煎紡鍖栦负涓や綅鏁板瓧鐨勭储寮?                                
                                # 璋冩暣 x 鍜?y 鍧愭爣
                                x = round(point['value']['x'] * 4.8)
                                y = round(point['value']['y'] * 6.4)
                                
                                part.set('x', str(x))
                                part.set('y', str(y))
            
            # 鍒涘缓甯︽湁澹版槑鍜屾牱寮忚〃鐨?XML 瀛楃涓?            xml_str = ET.tostring(dataset, encoding='ISO-8859-1', method='xml')
            xml_stylesheet = '<?xml-stylesheet type="text/xsl" href="image_metadata_stylesheet.xsl"?>\n'
            xml_str_with_header = f'{xml_stylesheet}{xml_str.decode("ISO-8859-1")}'
            
            os.makedirs(os.path.dirname(output_xml_path), exist_ok=True)
            output_xml_path =os.path.join(output_xml_path, 'train.xml')
            # 鍐欏叆 XML 鏂囦欢
            with open(output_xml_path, 'w', encoding='ISO-8859-1') as file:
                file.write(xml_str_with_header)

        #灏嗗涓枃浠跺す涓殑image鏂囦欢淇濆瓨鍒版湇鍔″櫒涓€涓枃浠跺す涓?        def train_copy_jpg_files(source_dir, target_dir):
            # 纭繚鐩爣鐩綍瀛樺湪锛屽鏋滀笉瀛樺湪鍒欏垱寤?            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            
            # 閬嶅巻婧愮洰褰曞強鍏跺瓙鐩綍
            # 閬嶅巻鎸囧畾鏂囦欢澶瑰強鍏跺瓙鏂囦欢澶逛腑鐨勬墍鏈?JSON 鏂囦欢
            dirs = os.listdir(source_dir)
            for dir in dirs:
                for root, dirs, files in os.walk(source_dir + "/" + dir):
                    for filename in files:
                        if filename.endswith('.jpg'):
                            # 鏋勫缓瀹屾暣鐨勬枃浠惰矾寰?                            source_file_path = os.path.join(root, filename)
                            # 澶嶅埗鏂囦欢鍒扮洰鏍囩洰褰?                            shutil.copy2(source_file_path, target_dir)
                            print(f'Copied: {source_file_path} to {target_dir}')

        def train_upload_model(local_model_path, remote_model_prefix):
            """
            涓婁紶妯″瀷鍒癿inio
            """
            self.deal_time = int(time.time())
            self.deal_msg = "Upload model: {} to {}".format(local_model_path, remote_model_prefix)
            filename = os.path.basename(local_model_path)  # 鎻愬彇鏂囦欢鍚嶏紝濡?20250609_train_1.dat
            remote_model_path = f"{remote_model_prefix.rstrip('/')}/{filename}"  # 鎷兼垚 models/20250609_train_1.dat
            # 1. 鎺ㄩ€佹ā鍨?            self.minio_client.fput_object(self.bucket_name, remote_model_path, local_model_path)

        def train_shape_predictor(param, faces_path, model_path, model_name):
            """
            璁粌 dlib shape predictor 妯″瀷

            鍙傛暟:
                faces_path: 鍖呭惈璁粌鏁版嵁鐨勮矾寰?
            杩斿洖:
                璁粌濂界殑妯″瀷鏂囦欢璺緞
            """
            # 鍙傛暟璁剧疆
            options = dlib.shape_predictor_training_options()
            model_param = param['inoutmodel']['model_param']
            options.oversampling_amount = model_param['oversampling_amount']
            options.tree_depth = model_param['tree_depth']
            if "True" == model_param['tree_depth']:
                options.be_verbose = True
            else:
                options.be_verbose = False

            options.nu = model_param['nu']
            options.oversampling_translation_jitter = model_param['oversampling_translation_jitter']
            options.num_threads = model_param['num_threads']

            # 瀵煎叆鎵撳ソ浜嗘爣绛剧殑 xml 鏂囦欢
            training_xml_path = os.path.join(faces_path, "train.xml")

            # 妫€鏌ヨ缁冩暟鎹枃浠舵槸鍚﹀瓨鍦?            if not os.path.exists(training_xml_path):
                raise FileNotFoundError(f"Training XML file not found at {training_xml_path}")

            # 瀹氫箟杈撳嚭妯″瀷鏂囦欢璺緞
            output_model_path = os.path.join(model_path, "{}.dat".format(model_name))

            # 杩涜璁粌
            print("Starting training...")
            dlib.train_shape_predictor(training_xml_path, output_model_path, options)

            # 鎵撳嵃鍦ㄨ缁冮泦涓殑鍑嗙‘鐜?            print("Training accuracy: {0}".format(dlib.test_shape_predictor(training_xml_path, output_model_path)))

            print(f"Training completed. Model saved to {output_model_path}")
            return output_model_path
    

        group_lists = param['inoutdata']['group_lists']
        remote_path = param['inoutdata']['path']
        remote_path += "/"
        model_save_name = param['inoutmodel']['model_save_name']
        
        # 璁剧疆妯″瀷鐨勫悕绉?        if model_save_name == "":
            model_save_name = datetime.now().strftime('%y-%m-%d')

        # 濡傛灉group_lists涓虹┖, 鍒欎粠minio涓嬭浇鎵€鏈夌殑group
        if 0 == len(group_lists):
            objects = self.minio_client.list_objects(self.bucket_name, prefix=remote_path, recursive=False)
            for obj in objects:
                if obj.is_dir:
                    dir_name = obj.object_name.split('/')[-2]
                    group_lists.append(dir_name)

        train_download_group(self.save_and_predict_path, group_lists) # 涓嬭浇璁粌鐨勬暟鎹?        train_json_to_xml(self.save_and_predict_path, self.cache_path) # 瑙ｆ瀽璁粌鐨勬暟鎹负xml
        train_copy_jpg_files(self.save_and_predict_path, self.cache_path) # 灏嗘墍鏈夌殑jpg鏂囦欢淇濆瓨鍒颁竴涓枃浠跺す涓?        local_model_train_save_path = train_shape_predictor(param, self.cache_path, self.model_save_path, model_save_name) # 璁粌妯″瀷
        train_upload_model(local_model_train_save_path, "models") # 涓婁紶妯″瀷鍒癿inio
    """
    ------------------------------------------------------杩欓儴鍒嗘槸璁粌缁撴潫------------------------------------------------------
    """



    
    def Cleanup(self):
        """
        @param: None 浣犱繚瀛樼殑绗笁鏂瑰鐞嗚繃绋?        """
        for param in self.params:
            if "relabel-for-group" == param['dtype']:
                os.system("rm -rf {}".format(self.save_and_predict_path))

            elif "model-train" == param['dtype']:
                os.system("rm -rf {}".format(self.cache_path))
                os.system("rm -rf {}".format(self.save_and_predict_path))

        print(f"璺緞 {self.cache_path} 宸叉竻鐞嗗畬鎴?)   
        print("娓呯悊浠诲姟")


