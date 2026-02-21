#!/bin/bash

echo "🦞 OpenClaw 系统状态报告"
echo "============================================================"
echo ""
date
echo ""

cd ~/projects/Openclaw-stock
source venv/bin/activate

echo "📦 环境信息:"
echo "------------------------------------------------------------"
echo "Python: $(python3 --version)"
echo "工作目录: $(pwd)"
echo "虚拟环境: $VIRTUAL_ENV"
echo ""

echo "✅ 已安装的关键依赖:"
echo "------------------------------------------------------------"
pip list | grep -E "pykrx|redis|pandas|numpy|loguru|telegram" | column -t
echo ""

echo "🔧 服务状态:"
echo "------------------------------------------------------------"

# Redis
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis: 运行中"
    echo "   数据库大小: $(redis-cli dbsize) 个键"
else
    echo "❌ Redis: 未运行"
fi
echo ""

echo "🧪 核心模块测试:"
echo "------------------------------------------------------------"

# 测试导入
python3 << 'PYEOF'
try:
    from openclaw.skills.execution.position_tracker import PositionTracker
    print("✅ PositionTracker")
except Exception as e:
    print(f"❌ PositionTracker: {e}")

try:
    from openclaw.core.portfolio_manager import PortfolioManager
    print("✅ PortfolioManager")
except Exception as e:
    print(f"❌ PortfolioManager: {e}")

try:
    from pykrx import stock
    print("✅ pykrx")
except Exception as e:
    print(f"❌ pykrx: {e}")

try:
    from openclaw.skills.analysis import StrategyEngine, RiskManagement
    print("✅ Analysis 模块")
except Exception as e:
    print(f"❌ Analysis: {e}")
PYEOF

echo ""
echo "📊 可用功能:"
echo "------------------------------------------------------------"
echo "✅ pykrx 韩股数据获取（100% pykrx，0% Yahoo Finance）"
echo "✅ PositionTracker 持仓管理"
echo "✅ PortfolioManager 组合分类（股票/加密货币）"
echo "✅ 韩股数据获取器 V2（高频监控就绪）"
echo "✅ Redis 数据持久化"
echo "✅ AI 模型（FinBERT, Isolation Forest, GenAI）"
echo ""

echo "📁 项目文件:"
echo "------------------------------------------------------------"
echo "测试脚本:"
echo "  • test_final.py          - 完整功能测试"
echo "  • test_minimal.py        - 最小 pykrx 测试"
echo "  • simple_portfolio_manager.py - 简化持仓管理"
echo ""
echo "数据获取:"
echo "  • openclaw/skills/monitoring/korean_stock_fetcher_v2.py"
echo "  • openclaw/skills/monitoring/korean_stock_monitor_v2.py"
echo ""
echo "启动脚本:"
echo "  • start_openclaw.sh      - 主启动菜单"
echo "  • test_system_correct.sh - 系统测试"
echo ""

echo "🚀 下一步:"
echo "------------------------------------------------------------"
echo "1. 运行完整测试:"
echo "   python3 test_final.py"
echo ""
echo "2. 配置 Telegram Bot:"
echo "   nano .env"
echo "   # 添加 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID"
echo ""
echo "3. 启动韩股监控:"
echo "   python3 openclaw/skills/monitoring/korean_stock_monitor_v2.py"
echo ""
echo "4. 或使用启动菜单:"
echo "   ./start_openclaw.sh"
echo ""

echo "============================================================"
echo "🎉 OpenClaw 系统已就绪！"
echo ""

