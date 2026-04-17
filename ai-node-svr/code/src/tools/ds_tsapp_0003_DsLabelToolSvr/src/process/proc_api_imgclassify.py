import base64
import time
from imp import lock_held
import json
import os
from queue import Empty
import threading
from io import BytesIO
import functools
from ..conn.Url import UrlRequest
from flask import request
from flask import render_template
from PIL import Image
from fontTools.misc.classifyTools import classify
from tifffile.tifffile import indent

from .proc_comm import eStatusCode

class CProcessorAPIImgClassify():
    def __init__(self,proc_comm):
        self.proc_comm = proc_comm
        self.node_cfg = proc_comm.getNodeCfg()
        self.storage_cloud = proc_comm.getStorageCloudObj()
        self.url_mng = UrlRequest(self.node_cfg)
        self.conn_name  = self.node_cfg['dconn_name']
        self.itemCategory_remote_root_path = self.node_cfg['itemCategory_remote_root_path'] #AIDataManage/DsImgRecognition
        self.img_zoom_ratio = 0.75
        self.imgBase64Cache = [] #缓存图像的base64数据,缓存100张图像
        self.imgBase64CacheSize = 100
        self.cache_lock = threading.RLock()  #用作img的cache同步
        self.json_change_lock=threading.RLock() #
        self.classify_file_lock = threading.RLock() #用作分类文件锁
        # 添加定时同步相关属性
        self.sync_interval = 300  # 5分钟 = 300秒
        self.sync_timer = None
        #同步一次远程信息到本地
        self.json_change = []
        self.json_cache=[]
        self.max_group = len(self.storage_cloud.listFiles(self.conn_name, self.itemCategory_remote_root_path + '/img-recog/'))
        self.task_info= {}
        self.pred_path="predict_results"

    def __del__(self):
        if self.sync_timer:
            self.sync_timer.cancel()


    def getTokenFromURL(self):
        # 获取URL的head中的token
        token = request.headers.get('Authorization')
        if token == None:
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'token error')
        token = token.replace('Bearer ','')
        return token

    def getImgDirLists(self,param):
        print(param)
        if 'filter_dirname' not in param:
            param['filter_dirname'] = ''
        filter_dirname = param['filter_dirname']

        ret_dirs = {'dirlist':[]}
        remote_img_dir_path = self.itemCategory_remote_root_path.strip('/')+'/src-img/'
        tmp_dirs = self.storage_cloud.listFiles(self.conn_name,remote_img_dir_path)
        for tmp_dir in tmp_dirs:
            if tmp_dir['ftype'] == 'D':
                group_name = tmp_dir['name']
                print(group_name)
                
                if filter_dirname == '': # 没有指筛选目录，返回所有目录
                    ret_dirs['dirlist'].append(group_name)
                elif filter_dirname in group_name:
                    ret_dirs['dirlist'].append(group_name)
        ret  = self.proc_comm.packRetJson(eStatusCode.SUCCESS,ret_dirs)
        return ret

    def getImgFileLists(self, param):
        print(param)
        group_name=param['group_name']
        remote_img_dir_path = self.itemCategory_remote_root_path.strip('/') + '/src-img/' + group_name + '/'
        imgfile_list = self.storage_cloud.listFiles(self.conn_name, remote_img_dir_path)
        # 组织返回信息
        ret_files = []
        for tmp_file in imgfile_list:
            if tmp_file['ftype'] == 'F':
                imgfilename = tmp_file['name']
                imgfilepath = '/src-img/' + group_name + '/' + tmp_file['name']
                fileitem = {
                    'imgname': imgfilename,
                    'imgpath': imgfilepath,
                }
                ret_files.append(fileitem)

        ret = self.proc_comm.packRetJson(eStatusCode.SUCCESS, ret_files)
        return ret

    def getImgBase64(self,param):
        """
        @param param:img_path
        @return: base64编码的图片
        """
        print(param)
        img_path = param['img_path']
        
        # 如果缓存中存在则直接取
        base64_data_ret = self.getImgBase64FromCache(img_path)
        if base64_data_ret is not None:
            return self.proc_comm.packRetJson(eStatusCode.SUCCESS, base64_data_ret, 'success')
        
        # 如果缓存中不存在，则正常的下载文件并且转格式
        if img_path.split('.')[1] not in 'jpg/png':
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'not image file [jpg/png]')
        
        remote_img_path = self.itemCategory_remote_root_path+ '/'+img_path
        local_img_filename = os.path.basename(remote_img_path)
        local_img_path = self.node_cfg['local_data_path'].strip('/')+ '/'+local_img_filename
        self.storage_cloud.downloadFile(self.conn_name, remote_img_path, local_img_path)
        
        if not os.path.exists(local_img_path):
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'download file failed')
        
        # 读取base64
        base64_data = ''
        new_img_width = 0
        new_img_height = 0
        try:  
            # 打开图像并按比例缩小
            with Image.open(local_img_path) as img:
                # 计算新尺寸
                new_img_width = int(img.width * self.img_zoom_ratio)
                new_img_height = int(img.height * self.img_zoom_ratio)
                # 按比例缩小图像，使用高质量缩放算法
                resized_img = img.resize((new_img_width, new_img_height), Image.Resampling.LANCZOS)
                
                # 将缩放后的图像保存到内存缓冲区
                buffer = BytesIO()
                # 获取文件扩展名
                img_format = local_img_filename.split('.')[1].upper()
                if img_format == 'JPG':
                    img_format = 'JPEG'
                resized_img.save(buffer, format=img_format)
                
                # 从缓冲区读取数据并转换为base64
                base64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
                # 设置base64前缀
                base64_data = f'data:image/{img_format.lower()};base64,{base64_data}'
        except :
            os.remove(local_img_path)
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'convert img to base64 error')
        os.remove(local_img_path)
        
        ret = {
            'src_img_width':new_img_width,
            'src_img_height':new_img_height,
            'base64_data':base64_data
        }
        
        # 缓存图像的base64数据
        self.saveImgBase64ToCache(img_path,ret)
        return self.proc_comm.packRetJson(eStatusCode.SUCCESS, ret, 'success')

    def saveImgBase64ToCache(self,img_path,img_base64_obj):
        with self.cache_lock:  # 加锁保护
            # 如果已经存在，则更新
            img_path_key = img_path.replace('/','_')
            for img_obj in self.imgBase64Cache:
                if img_path_key in img_obj:
                    img_obj[img_path_key] = img_base64_obj
                    return
    
            # 不存在就添加
            if len(self.imgBase64Cache) >= self.imgBase64CacheSize:
                self.imgBase64Cache.pop(0)
            img_path_key = img_path.replace('/','_')
            self.imgBase64Cache.append({img_path_key:img_base64_obj})
    
    def getImgBase64FromCache(self,img_path):
        with self.cache_lock:  # 加锁保护
            img_path_key = img_path.replace('/','_')
            for img_obj in self.imgBase64Cache:
                if img_path_key in img_obj:
                    return img_obj[img_path_key]
            return None

    def _sync_json_to_remote(self):

        #TODO:未设置最大缓存上限
        with self.json_change_lock:
            for item in self.json_change:
                group=item['group']
                local_json = next(
                    (item2['content'] for item2 in self.json_cache if item2['group'] == group),
                    None
                )
                if local_json is None:
                    continue
                local_json_path = self.node_cfg['local_data_path'].strip('/') + '/' + group + '.json'
                with open (local_json_path,'w',encoding='utf-8') as f:
                    json.dump(local_json,f,ensure_ascii=False,indent=2)

                remote_json_path=self.itemCategory_remote_root_path + "/img-recog/"+group+'.json'
                self.storage_cloud.uploadFile(self.conn_name, local_json_path, remote_json_path)
                os.remove(local_json_path)
                self.json_change.remove(item)

    def _sync_task_info_to_remote(self,group,imgname):
        # 同步任务信息到远程
        # 遍历json_cache查找对应group
        for cache_item in self.json_cache:
            if cache_item['group'] == group:
                # 在content中查找对应imgname的索引
                for index, content_item in enumerate(cache_item['content']):
                    if content_item['imgname'] == imgname:
                        current_task_index = index
                        break
                break
            
        #和远程比较目前哪一个最新
        local_temp_taskCount=self.node_cfg['local_data_path'].strip('/')+'/task_count.json'
        remote_taskCount=self.itemCategory_remote_root_path.strip('/')+'/utils/task_count.json'
        self.storage_cloud.downloadFile(self.conn_name, remote_taskCount, local_temp_taskCount)
        with open(local_temp_taskCount, 'r',encoding='utf-8') as file:
            task_count = json.load(file)
        os.remove(local_temp_taskCount)

        remote_group_int=int(task_count['current_group'])
        remote_task_index=int(task_count['current_task_index'])
        local_group_int=int(group)

        # 处理skippedTasks列表，如果不存在则创建
        skippedTasks = task_count.get('skippedTasks', [])
        if remote_group_int<local_group_int or ( remote_group_int==local_group_int and remote_task_index<current_task_index):
            # 本地任务 newer - 上传当前状态和跳过任务

            # if remote_group_int == local_group_int: #在同一组内
        #         # 添加当前组内从远程索引到本地索引之间的所有任务到跳过列表
        #         for i in range(remote_task_index, current_task_index):
        #             skippedTasks.append(f"{group}/{cache_item['content'][i]['imgname']}")
        #         upload['skippedTasks']=skippedTasks
        #     else:  # 不在同一个组内
        #         for i in range(remote_task_index,len(task_count['current_group_content'])):
        #             skippedTasks.append(f"{task_count['current_group']}/{task_count['current_group_content'][i]['imgname']}")
        #         # 遍历所有落后的组（从远程组+1到本地组-1）
        #         for g in range(remote_group_int + 1, local_group_int):
        #             group_str = f"{g:05d}"  # 格式化为5位数字的组名
        #             # 尝试从缓存中获取该组的任务信息
        #             group_cache = next((item for item in self.json_cache if item['group'] == group_str), None)
        #             if not group_cache:
        #                 # 如果缓存中没有，则临时加载该组的JSON文件
        #                 try:
        #                     self._cache_json(group_str)
        #                     group_cache = next((item for item in self.json_cache if item['group'] == group_str), None)
        #                 except:
        #                     continue  # 如果加载失败，跳过该组
                    
        #             if group_cache:
        #                 # 将该组的所有任务添加到跳过列表
        #                 for item in group_cache['content']:
        #                     skippedTasks.append(f"{group_str}/{item['imgname']}")
                
        #         # 处理当前组（本地组）的任务
        #         for i in range(1, current_task_index):
        #             skippedTasks.append(f"{group}/{cache_item['content'][i]['imgname']}")
        # else:
        #     # 远程任务 newer
        #     src_path=f"{group}/{imgname}"
            
        #     # 将当前任务从本地跳过列表中移除（如果存在）
        #     if src_path in skippedTasks:
        #         skippedTasks.remove(src_path)

        # # 去重处理，确保没有重复的跳过任务
        # skippedTasks = list(set(skippedTasks))  
        # 构造上传数据
            upload = {
                "current_group": group,
                "current_task_index": current_task_index,
                "current_group_content": [],
                "current_group_count": 0
                # ,
                # "skippedTasks": skippedTasks
            }
            # 上传更新后的任务信息
            with open(local_temp_taskCount, 'w', encoding='utf-8') as file:
                json.dump(upload, file, ensure_ascii=False, indent=2)
            self.storage_cloud.uploadFile(self.conn_name, local_temp_taskCount, remote_taskCount)
            os.remove(local_temp_taskCount)


    def _cache_json(self,group):
        with self.json_change_lock:
            remote_json_path=self.itemCategory_remote_root_path + "/img-recog/"+group+'.json'
            local_json_path=self.node_cfg['local_data_path'].strip('/')+ '/'+group+'.json'
            self.storage_cloud.downloadFile(self.conn_name, remote_json_path, local_json_path)
            with open(local_json_path,'r',encoding='utf-8') as f:
                json_data=json.load(f)
            #检查group是否已存在于缓存中
            for item in self.json_cache:
                if item['group'] == group:
                    # 存在则更新content
                    item['content'] = json_data
                    break
            else:
                #不存在则追加新条目
                self.json_cache.append({'group':group,'content':json_data})
            os.remove(local_json_path)

        return True if json_data is not None else False

    def updateImgLabel(self,param):
        print(param)
        img_path=param["img_path"]
        new_classify_code=param['classify_code']
        img_name=img_path.replace(' ','').split('/')[-1]
        group_name=img_path.replace(' ','').split('/')[1]

        with self.json_change_lock:
            change={'imgname':img_name,'classify_code':new_classify_code}
            for item in self.json_change:
                if item['group']==group_name:
                    item['change'].append(change)
                    break
            else:
                self.json_change.append({'group':group_name,'change':[change]})

        with self.json_change_lock:

            res=self._submitWork(img_path)

            if not res:
                return self.proc_comm.packRetJson(eStatusCode.FAILED, [], 'submit failed')
            if res["code"]!=200:
                return self.proc_comm.packRetJson(eStatusCode.FAILED, res["msg"], 'submit failed')


            # 预处理：将 json_cache 转换为 group 到 item 的映射（O(1) 查询）
            cached_group_map = {item['group']: item for item in self.json_cache}
            changed_groups = [item['group'] for item in self.json_change]

            for changed_group in changed_groups:
                # 情况1：缓存中存在该 group
                if changed_group in cached_group_map:
                    cached_item = cached_group_map[changed_group]
                    # 在 content 中查找目标 img_name
                    target_content = next(
                        (content for content in cached_item['content'] if content['imgname'] == img_name),
                        None
                    )
                    if target_content:
                        target_content['classifycode'] = new_classify_code
                    else:
                        return self.proc_comm.packRetJson(eStatusCode.FAILED, [], 'img not found in group')

                # 情况2：缓存中不存在该 group，尝试加载
                else:
                    success=self._cache_json(changed_group)
                    if not success:  # 加载失败直接返回
                        return self.proc_comm.packRetJson(eStatusCode.FAILED, [], 'cache load failed')
                    # 重新获取缓存
                    cached_group_map = {item['group']: item for item in self.json_cache}
                    if changed_group not in cached_group_map:
                        return self.proc_comm.packRetJson(eStatusCode.FAILED, [], 'group not found after cache')
                    # 查找并更新 content
                    cached_item = cached_group_map[changed_group]
                    target_content = next(
                        (content for content in cached_item['content'] if content['imgname'] == img_name),
                        None
                    )
                    if target_content:
                        target_content['classifycode'] = new_classify_code
                    else:
                        return self.proc_comm.packRetJson(eStatusCode.FAILED, [], 'img not found in group')

            self._sync_json_to_remote()
            self._sync_task_info_to_remote(group_name,img_name)

        return self.proc_comm.packRetJson(eStatusCode.SUCCESS, [], 'success')

    def getImgLabel(self,param):
        print(param)
        img_path=param["img_path"]
        img_name=img_path.replace(' ','').split('/')[-1]
        group_name=img_path.replace(' ','').split('/')[1]

        with self.json_change_lock:
            # 尝试从缓存中查找对应标签
            cached_group_map = {item['group']: item for item in self.json_cache}
            if group_name in cached_group_map:
                cached_item = cached_group_map[group_name]
                target_content = next(
                    (content for content in cached_item['content'] if content['imgname'] == img_name),
                    None
                )
                if target_content:
                    return self.proc_comm.packRetJson(eStatusCode.SUCCESS, [target_content['classifycode']], 'success')
            
            # 缓存中没有，尝试加载
            if not self._cache_json(group_name):
                return self.proc_comm.packRetJson(eStatusCode.FAILED, [], 'cache load failed')
            
            # 重新获取缓存并查找
            cached_group_map = {item['group']: item for item in self.json_cache}
            if group_name in cached_group_map:
                cached_item = cached_group_map[group_name]
                target_content = next(
                    (content for content in cached_item['content'] if content['imgname'] == img_name),
                    None
                )
                if target_content:
                    return self.proc_comm.packRetJson(eStatusCode.SUCCESS, [target_content['classifycode']], 'success')
            
        return self.proc_comm.packRetJson(eStatusCode.FAILED, [], 'label not found')

    def _getImgLabel(self,img_name,group_name):
        with self.json_change_lock:
            # 尝试从缓存中查找对应标签
            cached_group_map = {item['group']: item for item in self.json_cache}
            if group_name in cached_group_map:
                cached_item = cached_group_map[group_name]
                target_content = next(
                    (content for content in cached_item['content'] if content['imgname'] == img_name),
                    None
                )
                if target_content:
                    return target_content['classify_code']

            # 缓存中没有，尝试加载
            if not self._cache_json(group_name):
                return None

            # 重新获取缓存并查找
            cached_group_map = {item['group']: item for item in self.json_cache}
            if group_name in cached_group_map:
                cached_item = cached_group_map[group_name]
                target_content = next(
                    (content for content in cached_item['content'] if content['imgname'] == img_name),
                    None
                )
                if target_content:
                    return target_content['classify_code']
        return None
    
    def _checkClassifyCodeValid(self,classify_code):
        if classify_code is None:
            return False,[]
        if not isinstance(classify_code,str):
            return False,[]
        if len(classify_code)==0:
            return False,[]
        if not classify_code.isdigit() or len(classify_code) != 9:
            return False,[]
        
        # 分割分类代码为三个部分
        part1 = classify_code[0:3]
        part2 = classify_code[3:6]
        part3 = classify_code[6:9]
        
        level=0
        #修改第三级的情况，比如000 001 003
        if part3!="000":
            level=3
        elif part2!="000":
            level=2
        elif part1!="000":
            level=1
        else:
            return self.proc_comm.packRetJson(eStatusCode.FAILED, [], '数据格式不对哦')

        return level,[part1,part2,part3]

    def _updateJsonLabel(self,img_name,group_name,new_classify_code):
        # 更新json_change
        with self.json_change_lock:
            change={'imgname':img_name,'classify_code':new_classify_code}
            for item in self.json_change:
                if item['group']==group_name:
                    item['change'].append(change)
                    break
            else:
                self.json_change.append({'group':group_name,'change':[change]})

        # 更新json_cache
        with self.json_change_lock:
            # 预处理：将 json_cache 转换为 group 到 item 的映射（O(1) 查询）
            cached_group_map = {item['group']: item for item in self.json_cache}

            # 情况1：缓存中存在该 group
            if group_name in cached_group_map:
                cached_item = cached_group_map[group_name]
                # 在 content 中查找目标 img_name
                target_content = next(
                    (content for content in cached_item['content'] if content['imgname'] == img_name),
                    None
                )
                if target_content:
                    target_content['classifycode'] = new_classify_code
                else:
                    return False

            # 情况2：缓存中不存在该 group，尝试加载
            else:
                success=self._cache_json(group_name)
                if not success:  # 加载失败直接返回
                    return False
                # 重新获取缓存
                cached_group_map = {item['group']: item for item in self.json_cache}
                if group_name not in cached_group_map:
                    return False
                # 查找并更新 content
                cached_item = cached_group_map[group_name]
                target_content = next(
                    (content for content in cached_item['content'] if content['imgname'] == img_name),
                    None
                )
                if target_content:
                    target_content['classifycode'] = new_classify_code
                else:
                    return False

            self._sync_json_to_remote()
        return True

    def getClassify(self,param):
        try:
            with self.classify_file_lock:
                local_temp_classify_list=self.node_cfg['local_data_path'].strip('/')+'/classify_list.json'
                remote_classify_list=self.itemCategory_remote_root_path.strip('/')+'/utils/classify_list.json'
                self.storage_cloud.downloadFile(self.conn_name, remote_classify_list, local_temp_classify_list)
                with open(local_temp_classify_list, 'r',encoding='utf-8') as file:
                    classify_list = json.load(file)
                os.remove(local_temp_classify_list)

                # 返回分类列表
                return self.proc_comm.packRetJson(eStatusCode.SUCCESS, classify_list, '获取分类列表成功')
        except Exception as e:
            return self.proc_comm.packRetJson(eStatusCode.FAILED, [], f'获取分类列表失败: {str(e)}')

    def addClassify(self,param):
        print(param)
        classifycode=param["classifycode"]

        level,parts=self._checkClassifyCodeValid(classifycode)
        classify_part1=parts[0]
        classify_part2=parts[1]
        classify_part3=parts[2]
        desc=param["desc"]

        #json文件处理 - 使用锁保护
        with self.classify_file_lock:
            local_temp_classify_list=self.node_cfg['local_data_path'].strip('/')+'/classify_list.json'
            remote_classify_list=self.itemCategory_remote_root_path.strip('/')+'/utils/classify_list.json'
            self.storage_cloud.downloadFile(self.conn_name, remote_classify_list, local_temp_classify_list)
            with open(local_temp_classify_list, 'r',encoding='utf-8') as file:
                classify_list = json.load(file)

        success=False

        # 根据level值调整分类添加逻辑
        if level == 1: 
            # 添加到第一层级
            found = False
            for item in classify_list: 
                if item['code'] == classify_part1: 
                    found = True
                    break
            
            if found:
                return self.proc_comm.packRetJson(eStatusCode.FAILED, [], '分类已存在，无权限修改')
            else:
                new_item = { 
                    'desc': desc, 
                    'code': classify_part1, 
                    'sub_categories': [] 
                } 
                classify_list.append(new_item)
                success=True
        elif level == 2: 
            # 添加到第二层级
            for item in classify_list: 
                if item['code'] == classify_part1: 
                    sub_categories = item.get('sub_categories', [])
                    found = False
                    for sub_item in sub_categories:
                        if sub_item['code'] == classify_part2:
                            found = True
                            break
                    
                    if found:
                        return self.proc_comm.packRetJson(eStatusCode.FAILED, [], '分类已存在，无权限修改')
                    else:
                        new_sub_item = { 
                            'desc': desc, 
                            'code': classify_part2, 
                            'sub_categories': [] 
                        } 
                        # 确保item有sub_categories键
                        if 'sub_categories' not in item:
                            item['sub_categories'] = []
                        item['sub_categories'].append(new_sub_item)
                        success=True 
                    break        
        elif level == 3: 
            # 添加到第三层级
            for item in classify_list: 
                if item['code'] == classify_part1: 
                    # 找到第一级分类，使用get方法安全获取sub_categories
                    sub_categories = item.get('sub_categories', [])
                    for sub_item in sub_categories: 
                        if sub_item['code'] == classify_part2: 
                            found_level2 = True
                            # 使用get方法安全获取sub_item的sub_categories
                            sub_sub_categories = sub_item.get('sub_categories', [])
                            found_level3 = False
                            for sub_sub_item in sub_sub_categories: 
                                if sub_sub_item['code'] == classify_part3: 
                                    found_level3 = True
                                    break
                            
                            if found_level3:
                                return self.proc_comm.packRetJson(eStatusCode.FAILED, [], '分类已存在，无权限修改')
                            else:
                                new_sub_sub_item = { 
                                    'desc': desc, 
                                    'code': classify_part3, 
                                    'sub_categories': [] 
                                } 
                                # 确保sub_item有sub_categories键
                                if 'sub_categories' not in sub_item:
                                    sub_item['sub_categories'] = []
                                sub_item['sub_categories'].append(new_sub_sub_item) 
                                success=True
                            break
        else:
            return self.proc_comm.packRetJson(eStatusCode.FAILED, [], 'error!')

        if not success:
            return self.proc_comm.packRetJson(eStatusCode.FAILED, [], '父级分类未找到,要先添加父级分类，然后才能添加子级分类')            

        # 保存更新后的分类列表
        with self.classify_file_lock:
            with open(local_temp_classify_list, 'w',encoding='utf-8') as file:
                json.dump(classify_list, file, indent=4, ensure_ascii=False)

            # 上传更新后的文件
            self.storage_cloud.uploadFile(self.conn_name, local_temp_classify_list, remote_classify_list)

            os.remove(local_temp_classify_list)

        return self.proc_comm.packRetJson(eStatusCode.SUCCESS, [], '添加分类成功')


    def getNewTask(self,param):
        #本地的self.task_info和远程的同步在用户更新标签的时候触发

        #对于新开始的任务，从远程读取处理到哪里了
        if not self.task_info:
            #从远程读取当前处理到哪里
            local_temp_taskCount=self.node_cfg['local_data_path'].strip('/')+'/task_count.json'
            remote_taskCount=self.itemCategory_remote_root_path.strip('/')+'/utils/task_count.json'
            self.storage_cloud.downloadFile(self.conn_name, remote_taskCount, local_temp_taskCount)
            with open(local_temp_taskCount, 'r',encoding='utf-8') as file:
                task_count = json.load(file)
            os.remove(local_temp_taskCount)
            self._cache_json(task_count['current_group'])

            target_json=next(
                (group_json for group_json in self.json_cache if group_json['group'] == task_count['current_group']),
                    None
                )

            self.task_info.update({
                "current_group":task_count['current_group'],
                "current_task_index":task_count['current_task_index'],
                "current_group_content":target_json['content'],
                "current_group_count":len(target_json['content']),
            })
        current_group=self.task_info['current_group']
        current_task_index=self.task_info['current_task_index']
        
        if current_task_index<self.task_info['current_group_count']:
            self.task_info.update({"current_task_index":current_task_index+1,})
            ret={
                "img_name":self.task_info['current_group_content'][current_task_index]['imgname'],
                "group_name":current_group,
            }
            return self.proc_comm.packRetJson(eStatusCode.SUCCESS,[ret],"获取新任务成功")
        else:
            #检查是否是最后一组:
            current_group_int=int(self.task_info['current_group'])
            if current_group_int==self.max_group:
                return self.proc_comm.packRetJson(eStatusCode.FAILED,[],"当前group任务已完成")
            else:
                #切换到下一组
                current_group=f"{current_group_int+1:05d}"
                self._cache_json(current_group)
                target_json=next(
                    (group_json for group_json in self.json_cache if group_json['group'] == current_group),
                        None
                    )
                if target_json:
                    self.task_info.update({
                        "current_group":current_group,
                        "current_task_index":0,
                        "current_group_content":target_json['content'],
                        "current_group_count":len(target_json['content']),
                    })
                    return self.getNewTask(param)
                else:
                    return self.proc_comm.packRetJson(eStatusCode.FAILED,[],"下一个group不存在")

    def _submitWork(self,data_path,tool="img_classify",):
        token = request.headers.get('Authorization')
        if token == None:
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'token error')
        token = token.replace('Bearer ','')
        print(token)
        client_id=request.headers.get('clientid')

        urlsvr = self.node_cfg["plt_url"]
        urlname = "aibase/labelTaskSubmit/submit"
        current_time=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        param = {
            "dataPath":str(data_path),
            "tool":str(tool),
            "timestamp":current_time,
        }
        headers = {
            "Authorization": "Bearer {}".format(token),
            "clientId":client_id,
            "Content-Type": "application/json"
        }
        ret = self.url_mng.url_post(urlsvr,urlname,param,headers,True)
        
        return ret


    def getWorkCount(self, param):
        token = request.headers.get('Authorization')
        if token == None:
            return self.proc_comm.packRetJson(eStatusCode.FAILED,[],'token error')
        token = token.replace('Bearer ','')
        client_id=request.headers.get('clientid')
        print(token)

        tool=param['tool']

        urlsvr = self.node_cfg["plt_url"]
        urlname = "aibase/labelTaskSubmit/query"
        param = {
            "tool":tool
        }
        headers = {
            "Authorization": "Bearer {}".format(token),
            "clientId":client_id
        }
        ret = self.url_mng.url_get(urlsvr,urlname,param,headers,True)
        print(ret)

        return self.proc_comm.packRetJson(eStatusCode.SUCCESS,ret,'success')

    def getNextTask(self, param):
        src_img = param.get('src_img', None)
        current_img_name = src_img.split('/')[-1]
        current_group = src_img.split('/')[-2]
        
        # 从对应cache里的group找出当前任务的索引
        current_group_json = next(
            (group_json for group_json in self.json_cache if group_json['group'] == current_group),
            None
        )
        
        if not current_group_json:
            if not self._cache_json(current_group):
                return self.proc_comm.packRetJson(eStatusCode.FAILED, [], "当前group的缓存不存在且缓存失败")
            # 缓存成功后，直接从缓存中获取
            current_group_json = next(
                (group_json for group_json in self.json_cache if group_json['group'] == current_group),
                None
            )
        
        # 获取当前任务的索引
        current_img_index = next(
            idx for idx, item in enumerate(current_group_json['content']) 
            if item['imgname'] == current_img_name
        )
    
        # 检查是否在当前组内还有下一个任务
        if current_img_index < len(current_group_json['content']) - 1:
            # index不是最后一个的情况
            ret = {
                "img_name": current_group_json['content'][current_img_index + 1]['imgname'],
                "group_name": current_group,
            }
            return self.proc_comm.packRetJson(eStatusCode.SUCCESS, [ret], "success")
        else:
            # 处理index是最后一个的情况
            # 检查是否是最后一个组
            current_group_int = int(current_group)
            if current_group_int == self.max_group - 1:  # 注意：max_group是组数量，索引从0开始
                return self.proc_comm.packRetJson(eStatusCode.FAILED, [], "已经是最后一个任务")
            
            # 如果不是最后一个组，切换到下一组
            next_group = f"{current_group_int + 1:05d}"
            self._cache_json(next_group)
            target_json = next(
                (group_json for group_json in self.json_cache if group_json['group'] == next_group),
                None
            )
            
            if target_json:
                # 切换到下一组的第一个任务
                ret = {
                    "img_name": target_json['content'][0]['imgname'],
                    "group_name": next_group,
                }
                return self.proc_comm.packRetJson(eStatusCode.SUCCESS, [ret], "获取下一个任务成功")
            else:
                return self.proc_comm.packRetJson(eStatusCode.FAILED, [], "下一个group不存在")

    def getLastTask(self, param):
        src_img=param.get('src_img',None)
        current_img_name=src_img.split('/')[-1]
        current_group=src_img.split('/')[-2]
        # 尝试获取上一个任务
        # 从对应cache里的group找出当前任务的索引
        current_group_json = next(
            (group_json for group_json in self.json_cache if group_json['group'] == current_group),
            None
        )
        if not current_group_json:
            if not self._cache_json(current_group):
                return self.proc_comm.packRetJson(eStatusCode.FAILED, [], "当前group的缓存不存在且缓存失败")
            # 缓存成功后，直接从缓存中获取
            current_group_json = next(
                (group_json for group_json in self.json_cache if group_json['group'] == current_group),
                None
            )
        current_img_index = next(
                idx for idx, item in enumerate(current_group_json['content']) 
                if item['imgname'] == current_img_name
        ) 


        if current_img_index > 0:#index不是0的情况
            ret={
                "img_name":current_group_json['content'][current_img_index - 1]['imgname'],
                "group_name":current_group,
            }
            return self.proc_comm.packRetJson(eStatusCode.SUCCESS, [ret], "success")
        else:#处理index 是 0 的情况
            #检查是否是第一个组
            if current_group == '00000':
                return self.proc_comm.packRetJson(eStatusCode.FAILED, [], "已经是第一个任务")
            #如果不是第一个组，切换到上一个组       
            # 当前索引为0，需要切换到上一组的最后一个任务
            current_group_int=int(current_group)
            # 不是第一组，切换到上一组
            prev_group=f"{current_group_int - 1:05d}"
            self._cache_json(prev_group)
            target_json=next(
                (group_json for group_json in self.json_cache if group_json['group'] == prev_group),
                    None
                )
            if target_json:
                prev_group_count = len(target_json['content'])
                ret={
                    "img_name":target_json['content'][prev_group_count - 1]['imgname'],
                    "group_name":prev_group,
                }
                return self.proc_comm.packRetJson(eStatusCode.SUCCESS, [ret], "获取上一个任务成功")
            else:
                return self.proc_comm.packRetJson(eStatusCode.FAILED, [], "上一个group不存在")

    def getPredGroup(self,param):
        """
        获取预测组的信息
        @param group:被预测的组
        """
        remote_file='/predict_results/'+f"{param['group']}_predictions.json"
        remote_pred_path=self.node_cfg['local_data_path'].strip('/')+ '/' + remote_file
        local_temp_file=self.node_cfg['local_data_path'].strip('/')+'/'+f"{param['group']}_predictions.json"
        self.storage_cloud.downloadFile(self.conn_name, remote_pred_path, local_temp_file)
        with open(local_temp_file, 'r') as f:
            pred_data = json.load(f)
        remove(local_temp_file)    
        return self.proc_comm.packRetJson(eStatusCode.SUCCESS, pred_data, "success")

    def correctCode(self,param):
        """
        纠正分类,如果收到空字符串，默认不改变分类，但是保存在json的没有classifycode这个字段
        @param group:被预测的组
        @param imgname:被纠正的图像
        @param code:纠正后的分类
        """
        group=param.get('group',None)
        imgname=param.get('imgname',None)
        code=param.get('code',None)
        if not group or not imgname or not code:
            return self.proc_comm.packRetJson(eStatusCode.FAILED, [], "参数错误")
        remote_file='/predict_results/'+f"{param['group']}_predictions.json"
        remote_pred_path=self.node_cfg['local_data_path'].strip('/')+ '/' + remote_file
        local_temp_file=self.node_cfg['local_data_path'].strip('/')+'/'+f"{param['group']}_predictions.json"
        self.storage_cloud.downloadFile(self.conn_name, remote_pred_path, local_temp_file)
        with open(local_temp_file, 'r') as f:
            pred_data = json.load(f)    
        target_item=next(
            (item for item in pred_data if item['imgname'] == imgname),
            None
        )
        if not target_item:
            return self.proc_comm.packRetJson(eStatusCode.FAILED, [], "图像不存在")
        if code:
            target_item.setdefault('classifycode',code)  
        return self.proc_comm.packRetJson(eStatusCode.SUCCESS, pred_data, "success")      

    def predGroup(self,param):
        """
        预测一个组
        @param group
        """
        #TODO : 平台开放接口用来预测一个或者多个组
        pass

    def trainGroup(self,param):
        """
        训练一个组
        @param group
        """
        #TODO : 平台开放接口用来训练一个或者多个组
        pass

# ------------- HTML ----------------------
                
    def getHtmlClassify(self,param,htmlname):
        print(param)
        
        # 尝试从URL参数中获取token
        token_value = None
        if param and 'token' in param:
            token_value = param['token']
        
        # 如果URL参数中没有token，再从请求头获取
        if not token_value:
            token_result = self.getTokenFromURL()
            # 检查token_result是否为字典格式（错误情况）
            if isinstance(token_result, dict):
                token = token_result
            else:
                # 将字符串token转换为统一的字典格式
                token = {'code': 0, 'data': token_result, 'msg': 'success'}
        else:
            # 手动构造token结果对象
            token = {'code': 0, 'data': token_value, 'msg': 'success'}
        
        print(f"获取到的token: {token}")
        filted_pages=['photoClassify.html']
        if token['code']==-1:
            if htmlname in filted_pages:
                return self.proc_comm.packRetJson(eStatusCode.FAILED,[],"请登录")
    
        try:
            template_path = htmlname
            htmlcontent = render_template(template_path,**param)
        except Exception as e:
            print(f"模板渲染错误: {str(e)}")
        return htmlcontent



# ------------- ai-Reco --------------
