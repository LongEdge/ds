import os
import requests
from os import mkdir
import json
from ..util.log import setup_custom_logger

logger = setup_custom_logger("UrlRequest")

class UrlRequest(object):

    def __init__(self, node_cfg):
        self.node_cfg = node_cfg

    def url_post(self, urlsvr, urlname, param, headers={}, send_as_json=False):
        retdata = {}        
        try:
            url = "{}/{}".format(urlsvr,urlname)
            send_data = param
            try:
                if send_as_json:
                    res = requests.post(url, json=send_data, headers=headers).json()
                else:
                    res = requests.post(url, data=send_data, headers=headers).json()
                if "status" in res and 0 == res["status"]:
                    retdata = res["data"]
                elif "status" not in res:
                    retdata = res
                else:
                    logger.error("get init config failed")
                    return retdata
            except Exception as e:
                logger.error("get init config error: {}".format(str(e)))
                return retdata
        except Exception as e:
            logger.error("get init config error: {}".format(str(e)))
            return retdata
        return retdata    

    def url_get(self, urlsvr, urlname, param,headers={},send_as_json=False):
        retdata = {}
        try:
            url = "{}/{}".format(urlsvr, urlname)
            send_data=param
            try:
                if param:
                    if send_as_json:
                        res = requests.get(url,json=send_data,headers=headers).json()
                    else:
                        res = requests.get(url,data=send_data,headers=headers).json()
                else:
                        res = requests.get(url,headers=headers).json()
                if "status" in res and 0 == res["status"]:
                    retdata = res["data"]
                elif "status" not in res:
                    retdata = res
                else:
                    logger.error("get request failed")
                    return retdata
            except Exception as e:
                logger.error("get request error: {}".format(str(e)))
                return retdata
        except Exception as e:
            logger.error("get request error: {}".format(str(e)))
            return retdata
        return retdata        

    # 获取项目配置信息
    def get_project_config(self):
         # 如果没有该连接信息，则向服务端读取基本的cskin配置信息
        try:
            url = "{}/get-project-config/".format(self.node_cfg['plt_url'])
            send_data = {
                "client_key": "111111"
            }
            try:
                res = requests.post(url,data=send_data).json()
                if 0 == res["status"] :
                    prjcfg = res["data"]
                    return prjcfg
                else:
                    logger.error("get init config failed")
                    return {}
            except Exception as e:
                logger.error("get init config error: {}".format(str(e)))
                return {}
        except Exception as e:
            logger.error("get init config error: {}".format(str(e)))
            return {}

    """
    查询cloud storage的连接信息
    """
    # TODO: 还没有实现
    def get_storage_info_byname(self,conn_name):
        storageinfo = {}
        try:
            url = "{}/aibase/dataServerConfig/getInfo/{}".format(self.node_cfg['plt_url'],conn_name)
            send_data = {
            }
            retdata = requests.get(url,data=send_data).json()
            if 200 == retdata["code"]:
                data = retdata["data"]
                if (data['status'] == '0') and (data['serviceType'] == 'minio'):
                    storageinfo['STORAGE_TYPE'] = 'minio'
                    data_content = json.loads(data['content'])
                    storageinfo['END_POINT'] = data_content['endpoint']
                    storageinfo['ACCESS_KEY'] = data_content['accessKey']
                    storageinfo['SECRET_KEY'] = data_content['secretKey']
                    storageinfo['BUCKET_NAME'] = data_content['bucketName']
            return storageinfo
        except Exception as e:
            print(str(e))
            return {}