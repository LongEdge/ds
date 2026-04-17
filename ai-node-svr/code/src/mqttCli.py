import paho.mqtt.client as mqtt
from datetime import datetime
import json
import time

class CMqttCli:
    def __init__(self, mqttcfg):
        """
        host, port: MQTT鏈嶅姟鍣?        username, password: 鐧诲綍璁よ瘉
        topic: 璁㈤槄涓婚
        client_id: 濡傛灉闇€瑕佺绾挎秷鎭槦鍒楋紝璁㈤槄绔渶瑕佸浐瀹?client_id
        """
        host, port, username, password, topic, client_id = mqttcfg['host'], mqttcfg['port'], mqttcfg['username'], mqttcfg['password'], mqttcfg['topic'], mqttcfg['client_id']
        
        self.host = host
        self.port = port
        self.topic = topic
        self.username = username
        self.password = password
        self.client_id = client_id
        self.messages = {}  # 鐢ㄤ簬瀛樺偍鏀跺埌鐨勬秷鎭?        self._init_client()

    
    def _init_client(self):
        # 鍒涘缓瀹㈡埛绔?        self.client = mqtt.Client(client_id=self.client_id, clean_session=False if self.client_id else True)
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        # 璁剧疆鍥炶皟
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        # 璁剧疆鑷姩閲嶈繛寤惰繜
        self.client.reconnect_delay_set(min_delay=1, max_delay=60)

        # 杩炴帴鏈嶅姟鍣?        try:
            self.client.connect(self.host, self.port)
        except Exception as e:
            print("MQTT棣栨杩炴帴澶辫触:", e)

        self.client.loop_start()  # 鍚姩鍚庡彴绾跨▼澶勭悊缃戠粶浜嬩欢

    # 杩炴帴鍥炶皟
    def on_connect(self, client, userdata, flags, rc):
        print(f"[杩炴帴杩斿洖鐮乚: {rc}")
        if rc == 0:
            print("杩炴帴鎴愬姛")
            if self.topic:
                print("self.topic: ", self.topic)
                result, mid = client.subscribe(self.topic, qos=1)
                print(f"璁㈤槄涓婚 {self.topic}, 缁撴灉: {result}, mid: {mid}")
        else:
            print(f"杩炴帴澶辫触锛岃繑鍥炵爜: {rc}")

    # 娑堟伅鍥炶皟
    def on_message(self, client, userdata, msg):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            payload = json.loads(msg.payload.decode())
            info = payload
        except Exception as e:
            info = f"[{now}] {msg.topic} -> {msg.payload.decode()}"
            info = {'deal_time': int(time.time()), 'deal_percent': -1, 'deal_msg': 'error - {}'.format(e)}
        self.messages = info  # 淇濆瓨鍒伴槦鍒?
    # 鏂紑鍥炶皟
    def on_disconnect(self, client, userdata, rc):
        print(f"[鏂紑杩炴帴] 杩斿洖鐮? {rc}")
        if rc != 0:
            print("闈炴甯告柇寮€锛屽鎴风灏嗚嚜鍔ㄥ皾璇曢噸杩?)

    # 鍙戝竷娑堟伅
    def pub(self, topic, msg, qos=1):
        try:
            info = self.client.publish(topic, msg, qos=qos)
            info.wait_for_publish()
            if info.is_published():
                print(f"[鎴愬姛] 娑堟伅宸插彂閫?)
            else:
                print(f"[澶辫触] 娑堟伅鍙戦€佸け璐?)
        except Exception as e:
            # print("MQTT鍙戦€佹秷鎭紓甯?", e)
            pass


    # 鑾峰彇宸叉帴鏀舵秷鎭苟娓呯┖闃熷垪
    def sub(self):
        msgs = self.messages.copy()
        self.messages = {}
        return msgs

    # 鍋滄瀹㈡埛绔?    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
        print("MQTT 瀹㈡埛绔凡鏂紑")


if __name__ == '__main__':
    host = "<PRIVATE_HOST>"
    port = 1883
    topic = "test-log"
    username = "<REDACTED_USERNAME>"
    password = "<REDACTED_PASSWORD>"
    mqttcfg = {
        'host': host,
        'port': port,
        'topic': topic,
        'username': username,
        'password': password,
        'client_id': "ds_master",

    }
    mqtt_logger = CMqttCli(mqttcfg)

    # 鍙戝竷娑堟伅绀轰緥
    lists = []

    for i in range(3000):
        lists.append({'deal_time': int(time.time()), 'deal_percent': i, 'deal_msg': 'deal - {}'.format(i)})
    send_data = {
        'report_id': "44444",
        'node_no': 'zhl_test',
        'task_info': lists
    }
    for i in range(15): 
        mqtt_logger.pub(topic, json.dumps(send_data))
        print("娑堟伅鍙戦€佸畬姣?)

    # # 澶栭儴鎺у埗寰幆锛岃疆璇㈡帴鏀舵秷鎭?    # try:
    #     while True:
    #         new_msgs = mqtt_logger.sub()
    #         print("new_msgs: ", new_msgs)
    #         for m in new_msgs:
    #             print("澶勭悊娑堟伅:", m)
    #         time.sleep(1)
    # except KeyboardInterrupt:
    #     mqtt_logger.stop()

