#!/usr/bin/env python3
"""
完整可用的持仓管理演示
使用 SimplePositionManager
"""
import redis
from simple_portfolio_manager import SimplePositionManager

print("🎯 OpenClaw 持仓管理演示（可用版）")
print("="*60)

# 初始化
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
pm = SimplePositionManager(r)

print("✅ SimplePositionManager 初始化完成\n")

# ==========================================
# 1. 添加测试持仓
# ==========================================
print("1️⃣ 开仓")
print("------------------------------------------------------------")

# 韩国股票
pm.open_position('005930', 10, 181200, '삼성전자')
pm.open_position('035420', 5, 252500, 'NAVER')
pm.open_position('035720', 20, 57400, '카카오')
pm.open_position('051910', 3, 385000, 'LG화학')

# 加密货币
pm.open_position('KRW-BTC', 0.5, 60000000, 'Bitcoin')
pm.open_position('KRW-ETH', 2.0, 4050000, 'Ethereum')
pm.open_position('KRW-SOL', 10.0, 132000, 'Solana')

# ==========================================
# 2. 查看持仓
# ==========================================
print("\n2️⃣ 当前持仓")
print("------------------------------------------------------------")

positions = pm.get_all_positions()
print(f"总持仓数: {len(positions)}\n")

for symbol, pos in positions.items():
    cost = pos['cost']
    print(f"{symbol:12s}: {pos['quantity']:8.2f} @ ₩{pos['entry_price']:>12,} "
          f"(成本: ₩{cost:>12,.0f})")

# ==========================================
# 3. 分类查看
# ==========================================
print("\n3️⃣ 分类持���")
print("------------------------------------------------------------")

stock_positions = pm.get_stock_positions()
print(f"📈 股票 ({len(stock_positions)} 只):")
for symbol, pos in stock_positions.items():
    print(f"   {symbol}: {pos['quantity']:.0f}주")

crypto_positions = pm.get_crypto_positions()
print(f"\n🪙 加密货币 ({len(crypto_positions)} 个):")
for symbol, pos in crypto_positions.items():
    print(f"   {symbol}: {pos['quantity']}")

# ==========================================
# 4. 更新价格并计算盈亏
# ==========================================
print("\n4️⃣ 盈亏计算")
print("------------------------------------------------------------")

# 模拟当前市场价格
current_prices = {
    '005930': 183000,    # +1%
    '035420': 255000,    # +1%
    '035720': 56000,     # -2.4%
    '051910': 390000,    # +1.3%
    'KRW-BTC': 61500000, # +2.5%
    'KRW-ETH': 4100000,  # +1.23%
    'KRW-SOL': 135000,   # +2.27%
}

# 计算总组合
portfolio = pm.calculate_portfolio_value(current_prices)

print(f"总成本: ₩{portfolio['total_cost']:>15,.0f}")
print(f"总市值: ₩{portfolio['total_value']:>15,.0f}")
print(f"总盈亏: ₩{portfolio['total_pnl']:>15,.0f} ({portfolio['total_pnl_pct']:+.2f}%)")

# ==========================================
# 5. 按类型统计
# ==========================================
print("\n5️⃣ 分类统计")
print("------------------------------------------------------------")

by_type = pm.calculate_portfolio_by_type(current_prices)

print("📊 股票:")
print(f"   持仓数: {by_type['stocks']['count']}")
print(f"   成本: ₩{by_type['stocks']['total_cost']:,.0f}")
print(f"   市值: ₩{by_type['stocks']['total_value']:,.0f}")
print(f"   盈亏: ₩{by_type['stocks']['total_pnl']:,.0f} "
      f"({by_type['stocks']['total_pnl_pct']:+.2f}%)")

print("\n📊 加密货币:")
print(f"   持仓数: {by_type['crypto']['count']}")
print(f"   成本: ₩{by_type['crypto']['total_cost']:,.0f}")
print(f"   市值: ₩{by_type['crypto']['total_value']:,.0f}")
print(f"   盈亏: ₩{by_type['crypto']['total_pnl']:,.0f} "
      f"({by_type['crypto']['total_pnl_pct']:+.2f}%)")

print("\n📊 总计:")
print(f"   持仓数: {by_type['total']['count']}")
print(f"   成本: ₩{by_type['total']['total_cost']:,.0f}")
print(f"   市值: ₩{by_type['total']['total_value']:,.0f}")
print(f"   盈亏: ₩{by_type['total']['total_pnl']:,.0f} "
      f"({by_type['total']['total_pnl_pct']:+.2f}%)")

# ==========================================
# 6. 模拟平仓
# ==========================================
print("\n6️⃣ 平仓示例")
print("------------------------------------------------------------")

pm.close_position('035720', current_prices['035720'], '止损')

# ==========================================
# 7. 交易历史
# ==========================================
print("\n7️⃣ 交易历史")
print("------------------------------------------------------------")

trades = pm.get_trades_history(limit=10)
for i, trade in enumerate(trades[:5], 1):
    action = trade['action']
    symbol = trade['symbol']
    quantity = trade['quantity']
    price = trade['price']
    pnl_info = ""
    
    if action == 'CLOSE' and 'pnl' in trade:
        pnl_info = f" (PnL: ₩{trade['pnl']:,.0f})"
    
    print(f"{i}. {action:5s} {symbol:12s} {quantity:8.2f} @ ₩{price:>12,.0f}{pnl_info}")

# ==========================================
# 8. 清理
# ==========================================
print("\n8️⃣ 清理")
print("------------------------------------------------------------")

response = input("清理测试数据？(y/N): ")
if response.lower() == 'y':
    pm.clear_all()
else:
    print("⏭️  数据保留")

print("\n" + "="*60)
print("✅ 演示完成")
