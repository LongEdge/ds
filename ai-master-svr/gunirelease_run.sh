#!/bin/bash
set -u

# ========== 鍩虹璺緞 ==========
SCRIPT_PATH=$(realpath "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
USER_NAME=$(whoami)
ENV_NAME="cskin"

# 鐢ㄦ硶: 绗竴涓弬鏁颁负鍛戒护锛岀浜屼釜鍙傛暟涓哄疄渚嬪悕锛堜緥濡?ds_master锛?NAME_DEFAULT="ds_master"
NAME="${2:-$NAME_DEFAULT}"

DEPLOY_LOC="/data_ware/tool_deploy/$USER_NAME/$NAME"
APP_PATH="$DEPLOY_LOC/app.py"
LOG_DIR="$DEPLOY_LOC/../logs"
LOG_FILE="$LOG_DIR/$NAME.log"
PID_FILE="$DEPLOY_LOC/gunicorn_${NAME}.pid"

mkdir -p "$DEPLOY_LOC"
mkdir -p "$LOG_DIR"

# ========== 浠?yml 璇诲彇绔彛锛堝閿欙級 ==========
function get_port_from_yml {
    if [ -f "$DEPLOY_LOC/config.yml" ]; then
        grep -oP 'port:\s*"\K[0-9]+' "$DEPLOY_LOC/config.yml" | head -n1
    fi
}

# ========== 鏌?pidfile 鏄惁瀵瑰簲娲昏繘绋?==========
function pidfile_alive {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
        if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
            echo "$PID"
            return 0
        fi
    fi
    return 1
}

# ========== 閫氳繃绔彛鏌?gunicorn master锛堝洖閫€鏂规锛屼粎鍦?pidfile 涓㈠け鏃朵娇鐢級 ==========
function find_pid_by_port {
    PORT=$(get_port_from_yml)
    if [ -z "$PORT" ]; then
        return 1
    fi
    # 鎵惧崰鐢ㄨ绔彛鐨勮繘绋?pid锛堜娇鐢?ss/lsof 浠婚€夊叾涓€锛?    PID=$(ss -ltnp 2>/dev/null | awk -v P=":$PORT" '$4 ~ P { gsub(/.*pid=/,"",$6); gsub(/,.*/,"",$6); print $6 }' | head -n1)
    if [ -n "$PID" ]; then
        echo "$PID"
        return 0
    fi
    return 1
}

# ========== 鍚姩 ==========
function start_app {
    echo "==== Starting $NAME (gunicorn) ===="
    # 璇诲彇绔彛
    PORT=$(get_port_from_yml)
    [ -z "$PORT" ] && PORT=9000

    # 鑻?pid 瀛樺湪涓旇繘绋嬫椿鐫€锛屾嫆缁濋噸澶嶅惎鍔?    if pidfile_alive >/dev/null 2>&1; then
        echo "Instance $NAME already running (pid $(cat "$PID_FILE"))."
        return 0
    fi

    # 鍚姩鍛戒护鍐欏叆瀛?shell锛岄伩鍏?conda 婵€娲诲奖鍝嶇埗 shell
    (
        # 鍒濆鍖?conda 鐜锛堝鏋滀笉瀛樺湪涔熶笉 fatal锛?        if [ -f /usr/local/anaconda3/etc/profile.d/conda.sh ]; then
            source /usr/local/anaconda3/etc/profile.d/conda.sh
            conda activate "$ENV_NAME" || true
        fi

        cd "$DEPLOY_LOC" || exit 1

        # 浣跨敤 gunicorn锛屽苟鎶?stdout/stderr 閮借拷鍔犲埌鍗曚釜鏃ュ織鏂囦欢
        # 鍚屾椂浣跨敤 --pid 浣?gunicorn 鍐?pidfile锛坢aster pid锛?        nohup gunicorn --bind 0.0.0.0:"$PORT" \
            --workers 4 \
            --timeout 300 \
            --log-level info \
            --access-logfile - \
            --error-logfile - \
            --pid "$PID_FILE" \
            app:app >> "$LOG_FILE" 2>&1 &

        # disown 淇濊瘉瀛愯繘绋嬩笉浼氶殢鏈剼鏈殑 shell 缁撴潫鑰岃 SIGHUP
        disown
    )

    # give it a moment to create pidfile
    sleep 0.6

    if pidfile_alive >/dev/null 2>&1; then
        echo "Started $NAME on port $PORT, pid $(cat "$PID_FILE")"
        echo "Logs: $LOG_FILE"
    else
        echo "Failed to start $NAME (pidfile missing). Check $LOG_FILE for errors."
    fi
}

# ========== 鍋滄锛堜紭闆?-> 寮哄埗锛?==========
function stop_app {
    echo "==== Stopping $NAME ===="
    if PID=$(pidfile_alive 2>/dev/null); then
        echo "Found pid $PID from $PID_FILE. Sending QUIT (graceful)..."
        kill -QUIT "$PID"

        # 绛夊緟浼橀泤閫€鍑猴紙鏈€澶?10s锛?        for i in {1..10}; do
            sleep 1
            if kill -0 "$PID" 2>/dev/null; then
                echo "Waiting for process $PID to exit ($i)..."
            else
                break
            fi
        done

        # 濡傛灉浠嶇劧瀛樺湪锛屽彂閫?TERM锛岀劧鍚?KILL
        if kill -0 "$PID" 2>/dev/null; then
            echo "Process still alive; sending TERM..."
            kill -TERM "$PID"
            sleep 2
        fi
        if kill -0 "$PID" 2>/dev/null; then
            echo "Process still alive; sending KILL..."
            kill -KILL "$PID"
            sleep 1
        fi

        # 娓呯悊 pidfile
        rm -f "$PID_FILE"
        echo "Stopped $NAME."
        return 0
    fi

    # pidfile 涓嶅瓨鍦ㄦ垨鏃犳晥 -> 鍥為€€鐢ㄧ鍙ｆ煡鎵?    if PID=$(find_pid_by_port 2>/dev/null); then
        echo "No valid pidfile; found pid $PID by port. Killing it."
        kill -9 "$PID" 2>/dev/null || true
        echo "Killed pid $PID."
        return 0
    fi

    echo "No running instance of $NAME found."
    return 1
}

# ========== 閲嶅惎 ==========
function restart_app {
    stop_app
    sleep 1
    start_app
}

# ========== 鐘舵€?==========
function status_app {
    if PID=$(pidfile_alive 2>/dev/null); then
        echo "$NAME running, pid $PID"
    elif PID=$(find_pid_by_port 2>/dev/null); then
        echo "$NAME seems running on configured port, pid $PID (no pidfile)"
    else
        echo "$NAME not running"
    fi
}

# ========== tail 鏃ュ織 ==========
function logs_app {
    tail -n 200 -f "$LOG_FILE"
}

# ========== 涓诲叆鍙?==========
case "${1:-}" in
    deploy)
        # 绠€鍗?deploy锛氬鍒惰剼鏈洰褰曞埌鐩爣锛堣皑鎱庝娇鐢級
        [ -f "$DEPLOY_LOC/test.db" ] && cp "$DEPLOY_LOC/test.db" "$SCRIPT_DIR/" #鎶婄洰鏍囪矾寰勭殑 test.db 鎷峰洖褰撳墠鐩綍
        rm -rf "$DEPLOY_LOC"
        cp -r "$SCRIPT_DIR" "$DEPLOY_LOC"
        echo "Deployed to $DEPLOY_LOC"
        ;;
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    restart)
        restart_app
        ;;
    status)
        status_app
        ;;
    logs)
        logs_app
        ;;
    *)
        echo "Usage: $0 {deploy|start|stop|restart|status|logs}"
        exit 1
        ;;
esac

