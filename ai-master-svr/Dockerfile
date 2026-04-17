FROM python:3.8

# 覆盖源
RUN { \
    echo "deb http://mirrors.aliyun.com/debian bookworm main contrib non-free"; \
    echo "deb http://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free"; \
    echo "deb http://mirrors.aliyun.com/debian bookworm-updates main contrib non-free"; \
} > /etc/apt/sources.list

RUN \
    apt-get update && \
    apt-get install -y \
        vim \
        zip \
        unzip \
        wget \
        sqlite3 \
        --allow-unauthenticated && \
    apt-get clean

RUN pip install --upgrade pip setuptools

ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN mkdir -p /app
WORKDIR /app


COPY requirements.txt /app/

ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple 

RUN pip install --upgrade pip
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . /app

CMD ["gunicorn", "app:app", "-c", "gunicorn.conf.py"]
