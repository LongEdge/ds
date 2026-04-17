import json
import time
from datetime import datetime

import paho.mqtt.client as mqtt


class CMqttCli:
    def __init__(self, mqttcfg):
        """
        host, port: MQTT server
        username, password: auth credentials
        topic: subscription topic
        client_id: optional client id for offline queueing
        """
        host, port, username, password, topic, client_id = (
            mqttcfg['host'],
            mqttcfg['port'],
            mqttcfg['username'],
            mqttcfg['password'],
            mqttcfg['topic'],
            mqttcfg['client_id'],
        )

        self.host = host
        self.port = port
        self.topic = topic
        self.username = username
        self.password = password
        self.client_id = client_id
        self.messages = {}
        self._init_client()

    def _init_client(self):
        self.client = mqtt.Client(client_id=self.client_id, clean_session=False if self.client_id else True)
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.reconnect_delay_set(min_delay=1, max_delay=60)

        try:
            self.client.connect(self.host, self.port)
        except Exception as e:
            print("MQTT first connection failed:", e)

        self.client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        print(f"[MQTT connect rc]: {rc}")
        if rc == 0 and self.topic:
            result, mid = client.subscribe(self.topic, qos=1)
            print(f"MQTT subscribed {self.topic}, result: {result}, mid: {mid}")

    def on_message(self, client, userdata, msg):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            info = json.loads(msg.payload.decode())
        except Exception as e:
            info = {
                'deal_time': int(time.time()),
                'deal_percent': -1,
                'deal_msg': f'error - {e}',
                'raw_topic': msg.topic,
                'raw_time': now,
            }
        self.messages = info

    def on_disconnect(self, client, userdata, rc):
        print(f"[MQTT disconnect rc] {rc}")

    def pub(self, topic, msg, qos=1):
        try:
            info = self.client.publish(topic, msg, qos=qos)
            info.wait_for_publish()
        except Exception:
            pass

    def sub(self):
        msgs = self.messages.copy()
        self.messages = {}
        return msgs

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()


if __name__ == '__main__':
    host = "<PRIVATE_HOST>"
    port = 1883
    topic = "<REDACTED_TOPIC>"
    username = "<REDACTED_USERNAME>"
    password = "<REDACTED_PASSWORD>"
    mqttcfg = {
        'host': host,
        'port': port,
        'topic': topic,
        'username': username,
        'password': password,
        'client_id': "<REDACTED_CLIENT_ID>",
    }
    mqtt_logger = CMqttCli(mqttcfg)

    lists = []
    for i in range(3000):
        lists.append({'deal_time': int(time.time()), 'deal_percent': i, 'deal_msg': f'deal - {i}'})

    send_data = {
        'report_id': "<REDACTED_REPORT_ID>",
        'node_no': '<REDACTED_NODE>',
        'task_info': lists,
    }
    for _ in range(15):
        mqtt_logger.pub(topic, json.dumps(send_data))
