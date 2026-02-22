#!/bin/bash
# ============================================================
# OpenClaw 进程管理入口
# 用法：
#   ./openclaw.sh start    — 启动守护进程（后台常驻）
#   ./openclaw.sh stop     — 优雅停止
#   ./openclaw.sh restart  — 重启
#   ./openclaw.sh status   — 查看运行状态
#   ./openclaw.sh logs     — 实时查看日志（tail -f）
#   ./openclaw.sh clean    — 清理日志文件
# ============================================================

PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$PROJ_DIR/logs/openclaw.pid"
LOG_FILE="$PROJ_DIR/logs/openclaw.log"
DAEMON="$PROJ_DIR/openclaw_daemon.sh"

# 确保 logs 目录存在
mkdir -p "$PROJ_DIR/logs"

# ────── 工具函数 ──────────────────────────────────────────────

is_running() {
    [ -f "$PID_FILE" ] || return 1
    local pid
    pid=$(cat "$PID_FILE" 2>/dev/null)
    [ -z "$pid" ] && return 1
    kill -0 "$pid" 2>/dev/null
}

get_pid() {
    cat "$PID_FILE" 2>/dev/null
}

print_header() {
    echo ""
    echo "  🦞  OpenClaw 交易系统"
    echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# ────── 命令实现 ──────────────────────────────────────────────

cmd_start() {
    print_header
    if is_running; then
        echo "  ✅ 已在运行中  PID=$(get_pid)"
        echo ""
        return 0
    fi

    # 使用 setsid 新建会话，彻底脱离终端；nohup 防止 SIGHUP
    # daemon 内部自行写日志，这里只丢弃 shell 本身的零星输出
    nohup setsid bash "$DAEMON" > /dev/null 2>&1 &
    DAEMON_PID=$!
    echo $DAEMON_PID > "$PID_FILE"
    disown $DAEMON_PID

    sleep 1
    if is_running; then
        echo "  🚀 启动成功  PID=$(get_pid)"
        echo "  📄 日志文件  $LOG_FILE"
        echo "  🔍 查看日志  ./openclaw.sh logs"
    else
        echo "  ❌ 启动失败，请检查日志："
        echo "     tail -20 $LOG_FILE"
    fi
    echo ""
}

_tg_notify() {
    # 从 .env 读取 Token / Chat ID + 白名单用户，向所有人发送通知（静默失败）
    local msg="$1"
    local env_file="$PROJ_DIR/.env"
    local token chat_id auth_users
    token=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$env_file" 2>/dev/null | tail -1 | cut -d= -f2-)
    chat_id=$(grep -E '^TELEGRAM_CHAT_ID=' "$env_file" 2>/dev/null | tail -1 | cut -d= -f2-)
    auth_users=$(grep -E '^TELEGRAM_AUTHORIZED_USERS=' "$env_file" 2>/dev/null | tail -1 | cut -d= -f2-)
    [ -z "$token" ] && return 0

    # 构建去重收件人列表（主 chat_id + 白名单用户）
    local recipients=()
    [ -n "$chat_id" ] && recipients+=("$chat_id")
    if [ -n "$auth_users" ]; then
        IFS=',' read -ra _ids <<< "$auth_users"
        for _id in "${_ids[@]}"; do
            _id="${_id// /}"  # 去空格
            [ -n "$_id" ] && recipients+=("$_id")
        done
    fi

    # 去重并发送
    local sent=()
    for cid in "${recipients[@]}"; do
        # 跳过已发送的
        local dup=0
        for s in "${sent[@]}"; do [[ "$s" == "$cid" ]] && dup=1 && break; done
        [ $dup -eq 1 ] && continue
        sent+=("$cid")
        curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
            -d chat_id="$cid" \
            -d text="$msg" > /dev/null 2>&1 || true
    done
}

cmd_stop() {
    print_header

    local pid=""
    if is_running; then
        pid=$(get_pid)
        echo "  🛑 正在停止 PID=$pid ..."

        # 通知 Telegram
        _tg_notify "🛑 OpenClaw 守护进程已手动停止（PID=$pid）
$(date '+%Y-%m-%d %H:%M:%S')"

        # 先发 SIGTERM，让守护进程自己清理子进程
        kill -TERM "$pid" 2>/dev/null
        sleep 2

        if kill -0 "$pid" 2>/dev/null; then
            # 仍存活 → SIGKILL
            kill -KILL "$pid" 2>/dev/null
            sleep 1
        fi

        # 杀掉守护进程的直接子进程
        pkill -P "$pid" 2>/dev/null || true
    fi

    # 兜底：不管 PID 文件状态如何，强制清理所有匹配进程
    # （外部 killbot / 手动 kill 可能已让 PID 文件过期，但子进程仍存活）
    local _leftover
    _leftover=$(pgrep -f 'start_conversation_bot|telegram_bot_standalone' 2>/dev/null)
    if [[ -n "$_leftover" ]]; then
        pkill -TERM -f 'start_conversation_bot|telegram_bot_standalone' 2>/dev/null || true
        sleep 1
        pkill -KILL -f 'start_conversation_bot|telegram_bot_standalone' 2>/dev/null || true
        echo "  🧹 兜底清理残留进程：$(echo "$_leftover" | tr '\n' ' ')"
    fi

    rm -f "$PID_FILE"

    if [[ -z "$pid" ]] && [[ -z "$_leftover" ]]; then
        echo "  ⚪ 未发现运行中的 Bot 进程"
    else
        echo "  ✅ 已停止"
    fi
    echo ""
}

cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

cmd_status() {
    print_header
    if is_running; then
        local pid
        pid=$(get_pid)
        echo "  ✅ 运行中  PID=$pid"
        # 子进程（python bot）
        local child
        child=$(pgrep -P "$pid" 2>/dev/null | head -1)
        [ -n "$child" ] && echo "  🐍 Bot子进程  PID=$child"
        # 内存/CPU
        ps -p "$pid" -o pid,pcpu,pmem,etime --no-headers 2>/dev/null | \
            awk '{printf "  📊 CPU=%-6s MEM=%-6s 运行时长=%s\n",$2,$3,$4}'
        echo ""
        # 最近10行日志
        echo "  ── 最近日志 ─────────────────────────────"
        tail -10 "$LOG_FILE" 2>/dev/null | sed 's/^/  /'
    else
        echo "  ⚪ 未运行"
    fi
    echo ""
}

cmd_logs() {
    echo ""
    echo "  📄 实时日志（Ctrl+C 退出）"
    echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    tail -f "$LOG_FILE"
}

cmd_clean() {
    print_header
    if is_running; then
        echo "  ⚠️  进程正在运行，停止后再清理"
        echo ""
        return 1
    fi
    > "$LOG_FILE"
    echo "  🧹 日志已清空"
    echo ""
}

# ────── 入口 ────────────────────────────────────────────────

case "${1:-}" in
    start)   cmd_start   ;;
    stop)    cmd_stop    ;;
    restart) cmd_restart ;;
    status)  cmd_status  ;;
    logs)    cmd_logs    ;;
    clean)   cmd_clean   ;;
    *)
        print_header
        echo "  用法: $0 {start|stop|restart|status|logs|clean}"
        echo ""
        echo "  start    启动守护进程（后台常驻，崩溃自动重启）"
        echo "  stop     停止守护进程"
        echo "  restart  重启"
        echo "  status   查看运行状态与最近日志"
        echo "  logs     实时查看完整日志（tail -f）"
        echo "  clean    清空日志文件"
        echo ""
        ;;
esac
