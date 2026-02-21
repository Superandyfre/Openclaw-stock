#!/usr/bin/env python3
"""
完整演示：使用原生 PositionTracker 和 PortfolioManager
"""
from openclaw.skills.execution.position_tracker import PositionTracker
from openclaw.core.portfolio_manager import PortfolioManager

print("🎯 OpenClaw 完整演示")
print("="*60)

# 初始化（1000万韩元）
tracker = PositionTracker(initial_capital=10000000)
pm = PortfolioManager(tracker)

print(f"✅ 初始化完成")
print(f"   初始资金: ₩{tracker.initial_capital:,.0f}\n")

# ==========================================
# 1. 开仓
# ==========================================
print("1️⃣ 建立持仓")
print("------------------------------------------------------------")

positions_to_open = [
    ('005930', 10, 181200, '삼성전자'),
    ('035420', 5, 252500, 'NAVER'),
    ('035720', 20, 57400, '카카오'),
    ('KRW-BTC', 0.5, 60000000, 'Bitcoin'),
    ('KRW-ETH', 2.0, 4050000, 'Ethereum'),
]

for symbol, qty, price, name in positions_to_open:
    result = tracker.open_position(symbol, qty, price)
    
    if result.get('success', True):
        cost = qty * price
        print(f"✅ {symbol:12s} ({name:10s}): {qty:6.1f} @ ₩{price:>12,} = ₩{cost:>12,.0f}")
    else:
        print(f"❌ {symbol}: {result.get('reason')}")

print(f"\n💰 剩余现金: ₩{tracker.cash:,.0f}")

# ==========================================
# 2. 查看持仓
# ==========================================
print("\n2️⃣ 当前持仓")
print("------------------------------------------------------------")

stock_pos = pm.get_stock_positions()
print(f"📈 股票 ({len(stock_pos)} 只):")
for symbol in stock_pos.keys():
    pos = tracker.positions[symbol]
    print(f"   {symbol}: {pos['quantity']:.0f}주 @ ₩{pos['entry_price']:,}")

crypto_pos = pm.get_crypto_positions()
print(f"\n🪙 加密货币 ({len(crypto_pos)} 个):")
for symbol in crypto_pos.keys():
    pos = tracker.positions[symbol]
    print(f"   {symbol}: {pos['quantity']} @ ₩{pos['entry_price']:,}")

# ==========================================
# 3. 价格更新和盈亏计算
# ==========================================
print("\n3️⃣ 盈亏分析")
print("------------------------------------------------------------")

current_prices = {
    '005930': 183000,    # +1%
    '035420': 255000,    # +1%
    '035720': 56000,     # -2.4%
    'KRW-BTC': 61500000, # +2.5%
    'KRW-ETH': 4100000,  # +1.23%
}

# 更新价格
tracker.update_position_prices(current_prices)

# 计算盈亏
portfolio_value = tracker.calculate_portfolio_value(current_prices)
unrealized_pnl = tracker.calculate_unrealized_pnl(current_prices)

print(f"持仓市值: ₩{portfolio_value:,.0f}")
print(f"未实现盈亏: ₩{unrealized_pnl:,.0f}")
print(f"组合总值: ₩{(tracker.cash + portfolio_value):,.0f}")

# ==========================================
# 4. 分类统计
# ==========================================
print("\n4️⃣ 分类统计")
print("------------------------------------------------------------")

portfolio = pm.get_portfolio_by_type(current_prices)

print("📊 股票:")
print(f"   市值: ₩{portfolio['stocks']['total_value']:,.0f}")
print(f"   盈亏: ₩{portfolio['stocks']['total_pnl']:,.0f} "
      f"({portfolio['stocks']['total_pnl_pct']:+.2f}%)")

print("\n📊 加密货币:")
print(f"   市值: ₩{portfolio['crypto']['total_value']:,.0f}")
print(f"   盈亏: ₩{portfolio['crypto']['total_pnl']:,.0f} "
      f"({portfolio['crypto']['total_pnl_pct']:+.2f}%)")

print("\n📊 总计:")
print(f"   持仓市值: ₩{portfolio['total']['total_value']:,.0f}")
print(f"   总盈亏: ₩{portfolio['total']['total_pnl']:,.0f} "
      f"({portfolio['total']['total_pnl_pct']:+.2f}%)")

# ==========================================
# 5. 平仓示例
# ==========================================
print("\n5️⃣ 平仓示例")
print("------------------------------------------------------------")

result = tracker.close_position('035720', current_prices['035720'])

if result.get('success', True):
    print(f"✅ 平仓 035720 (카카오)")
    print(f"   盈亏: ₩{result.get('realized_pnl', 0):,.0f}")
    print(f"   现金: ₩{tracker.cash:,.0f}")

print("\n" + "="*60)
print("✅ 演示完成")
print(f"\n💡 最终状态:")
print(f"   现金: ₩{tracker.cash:,.0f}")
print(f"   持仓数: {len(tracker.positions)}")
print(f"   已平仓: {len(tracker.closed_positions)}")
