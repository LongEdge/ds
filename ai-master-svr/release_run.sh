#!/bin/bash
# 获取脚本文件所在的绝对路径
SCRIPT_PATH=$(realpath $0)
SCRIPT_DIR=$(dirname $SCRIPT_PATH)
USER_NAME=$(whoami)
ENV_NAME="cskin"
DEPLOY_LOC="/data_ware/tool_deploy/$USER_NAME/ds_master"
APP_PATH=$DEPLOY_LOC"/app.py"
LOG_PATH=$DEPLOY_LOC"/../logs/"
SQLITE_PORT=8225

# 创建目录
mkdir -p $DEPLOY_LOC
mkdir -p $LOG_PATH

# 检查进程是否正在运行
function is_running {
    pgrep -f "python -u $APP_PATH $1" > /dev/null
}

# 启动应用程序（不使用 nohup）
function start_app {
    echo "Starting app..."
    source /usr/local/anaconda3/etc/profile.d/conda.sh
    conda activate $ENV_NAME
    # 将 stdout/stderr 写入日志，不使用 nohup
    python -u $APP_PATH $1 > $LOG_PATH$1".log" 2>&1 &
    echo "App started. Logs: $LOG_PATH$1.log"
}

# 停止应用程序
function stop_app {
    echo "Stopping app..."
    pkill -f "python -u $APP_PATH $1"
    echo "App stopped."

    echo "Stopping app on port $SQLITE_PORT..."

    # 找到占用端口的 PID
    pid=$(lsof -ti:"$SQLITE_PORT")

    if [ -z "$pid" ]; then
        echo "No process is using port $SQLITE_PORT."
    else
        kill -9 $pid
        echo "Process $pid on port $SQLITE_PORT stopped."
    fi
    
}

# 重启应用程序
function restart_app {
    stop_app $2
    sleep 2
    start_app $2
}

# 发布版本
release_version() {
    # 获取当前路径
    SERVICE_DIR="$PWD"
    echo "${SERVICE_DIR}"
    CODE_DIR="$SERVICE_DIR"
    RELEASE_BASE_DIR="$CODE_DIR/release_hub"
    RELEASE_DIR="$RELEASE_BASE_DIR/$2"


    if [ -d "$RELEASE_DIR" ]; then
        echo "❌ Version $2 already exists in release_hub"
        exit 1
    fi

    echo "📦 Releasing version: $2"
    echo "📂 From: $CODE_DIR"
    echo "📂 To:   $RELEASE_DIR"

    mkdir -p "$RELEASE_DIR"

    # 拷贝应用代码
    rsync -a \
        --exclude 'release_hub' \
        --exclude 'data' \
        "$CODE_DIR/" \
        "$RELEASE_DIR/"

    # 拷贝模型数据（如果存在）
    if [ -d "$DATA_DIR" ]; then
        mkdir -p "$RELEASE_DIR/data"
        cp -r "$DATA_DIR/." "$RELEASE_DIR/data/"
    fi

    echo "✅ Version $2 released successfully"
}


function MainConsole {
    case "$1" in
        release_version)
            echo $2
            release_version $2 $3
            ;;
        deploy)
            rm -rf $DEPLOY_LOC
            cp -r $SCRIPT_DIR $DEPLOY_LOC
            ;;
        start)
            start_app $2
            ;;
        stop)
            stop_app $2
            ;;
        restart)
            restart_app $1 $2
            ;;
        isrunning)
            is_running $2
            ;;
        logs)
            tail -f $LOG_PATH$2".log"
            ;;
        *)
            echo "Usage: ./release_run.sh {deploy|start|stop|restart|logs|isrunning} [app_name]"
            ;;
    esac
}

MainConsole $1 "ds_master" $3