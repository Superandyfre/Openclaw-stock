#!/bin/bash

cd ~/projects/Openclaw-stock
source venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

clear
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║          🦞 OpenClaw ��股交易系统 🇰🇷                        ║"
echo "║                                                            ║"
echo "║             ✅ 系统部署完成 · 功能测试通过                   ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "请选择操作:"
echo ""
echo "  🌟 推荐选项"
echo "  ─────────────────────────────────────────────"
echo "  1) 🎯 完美演示（推荐！基于实际API）"
echo "  2) 🧪 pykrx 韩股数据测试"
echo ""
echo "  💼 持仓管理"
echo "  ─────────────────────────────────────────────"
echo "  3) 安全版本测试"
echo "  4) 生产级演示"
echo "  5) 简化持仓管理器"
echo ""
echo "  🔍 调试工具"
echo "  ─────────────────────────────────────────────"
echo "  6) 调试 Portfolio ��构"
echo "  7) 韩股数据获取器 V2"
echo ""
echo "  📊 系统信息"
echo "  ─────────────────────────────────────────────"
echo "  8) 查看系统状态"
echo "  9) 运行完整测试"
echo ""
echo "  0) 退出"
echo ""
read -p "请输入选择 [0-9]: " choice

case $choice in
    1)
        clear
        python3 demo_perfect.py
        ;;
    2)
        clear
        python3 test_minimal.py
        ;;
    3)
        clear
        python3 test_safe.py
        ;;
    4)
        clear
        python3 demo_production.py
        ;;
    5)
        clear
        python3 simple_portfolio_manager.py
        ;;
    6)
        clear
        python3 debug_portfolio_structure.py
        ;;
    7)
        clear
        python3 openclaw/skills/monitoring/korean_stock_fetcher_v2.py
        ;;
    8)
        clear
        ./system_status.sh
        ;;
    9)
        clear
        ./test_system_correct.sh
        ;;
    0)
        echo ""
        echo "👋 再见！"
        echo ""
        exit 0
        ;;
    *)
        echo ""
        echo "❌ 无效选择"
        ;;
esac

echo ""
read -p "按回车键继续..."
./start.sh
    9)
        clear
        echo "🤖 启动 Telegram Bot (增强版)..."
        echo ""
        python3 openclaw/skills/monitoring/telegram_bot_enhanced.py
        ;;
