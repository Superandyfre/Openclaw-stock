#!/bin/bash
# ============================================================
# OpenClaw 守护进程内核
# 由 openclaw.sh start 调用，不要直接运行此文件
# 功能：无限重启循环，崩溃后自动拉起，连续崩溃时指数退避
# ============================================================

PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$PROJ_DIR/logs/openclaw.log"
PID_FILE="$PROJ_DIR/logs/openclaw.pid"
VENV="$PROJ_DIR/venv/bin/activate"

cd "$PROJ_DIR"
source "$VENV"
export PYTHONPATH="$PROJ_DIR:${PYTHONPATH}"
export TZ="Asia/Seoul"   # 整个进程树统一使用韩国时间（KST, UTC+9）

# 将自身 PID 写入 pidfile（覆盖 openclaw.sh 里写的临时值）
echo $$ > "$PID_FILE"

FAIL_COUNT=0
FAIL_WINDOW=60   # 60秒内连续崩溃才算"快速崩溃"
MAX_BACKOFF=60   # 最长等待60秒再重启
BOT_PID=""       # 当前 bot 子进程 PID

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# 捕获 SIGTERM / SIGINT：先杀 bot 子进程，再退出
_shutdown() {
    log "守护进程收到停止信号，正在清理子进程..."
    if [ -n "$BOT_PID" ] && kill -0 "$BOT_PID" 2>/dev/null; then
        kill -TERM "$BOT_PID" 2>/dev/null
        sleep 1
        kill -KILL "$BOT_PID" 2>/dev/null || true
        log "Bot子进程 PID=$BOT_PID 已终止"
    fi
    rm -f "$PID_FILE"
    exit 0
}
trap '_shutdown' SIGTERM SIGINT SIGHUP

log "=============================="
log "OpenClaw 守护进程启动 PID=$$"
log "=============================="

while true; do
    START_TS=$(date +%s)

    log ">>> 启动 start_conversation_bot.py"
    python "$PROJ_DIR/start_conversation_bot.py" >> "$LOG_FILE" 2>&1 &
    BOT_PID=$!
    wait $BOT_PID
    EXIT_CODE=$?

    END_TS=$(date +%s)
    ELAPSED=$((END_TS - START_TS))

    log "<<< 进程退出 exit=$EXIT_CODE 运行时长=${ELAPSED}s"

    # 运行不足 FAIL_WINDOW 秒视为快速崩溃
    if [ $ELAPSED -lt $FAIL_WINDOW ]; then
        FAIL_COUNT=$((FAIL_COUNT + 1))
    else
        FAIL_COUNT=0
    fi

    # 指数退避：1s 2s 4s 8s ... 最大60s
    WAIT=$((2 ** (FAIL_COUNT - 1)))
    [ $WAIT -gt $MAX_BACKOFF ] && WAIT=$MAX_BACKOFF
    [ $WAIT -lt 1 ]            && WAIT=1

    log "    连续快速崩溃次数=$FAIL_COUNT，${WAIT}秒后重启..."
    sleep "$WAIT"
done
