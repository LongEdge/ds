import os
import yaml

with open('config.yml', 'r', encoding='utf-8') as f:
    configs = yaml.load(f, Loader=yaml.SafeLoader)
port = configs['port']

accesslog = "-"   # 输出到 stdout
errorlog = "-"    # 输出到 stdout
loglevel = "" # 日志级别
bind = "0.0.0.0:{}".format(port)
workers = 20
timeout = 120