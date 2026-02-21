#!/usr/bin/env python3
"""
完整的持仓管理演示
"""
import redis
from openclaw.skills.execution.position_tracker import PositionTracker
from openclaw.core.portfolio_manager import PortfolioManager

print("🎯 OpenClaw 持仓管理完整演示")
print("="*60)

# 初始化
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
tracker = PositionTracker(r)
pm = PortfolioManager(tracker)

print("✅ 系统初始化完成\n")

# ==========================================
# 1. 添加一些测试持仓
# ==========================================
print("1️⃣ 添加测试持仓")
print("------------------------------------------------------------")

# 韩国股票
stocks = [
    {'symbol': '005930', 'quantity': 10, 'entry_price': 181200, 'name': '삼성전자'},
    {'symbol': '035420', 'quantity': 5, 'entry_price': 252500, 'name': 'NAVER'},
    {'symbol': '035720', 'quantity': 20, 'entry_price': 57400, 'name': '카카오'},
]

for stock in stocks:
    try:
        tracker.open_position(
            symbol=stock['symbol'],
            quantity=stock['quantity'],
            entry_price=stock['entry_price']
        )
        print(f"✅ 开仓: {stock['symbol']} ({stock['name']}) "
              f"{stock['quantity']}주 @ ₩{stock['entry_price']:,}")
    except Exception as e:
        print(f"❌ {stock['symbol']}: {e}")

# 加密货币
cryptos = [
    {'symbol': 'KRW-BTC', 'quantity': 0.5, 'entry_price': 60000000, 'name': 'Bitcoin'},
    {'symbol': 'KRW-ETH', 'quantity': 2.0, 'entry_price': 4050000, 'name': 'Ethereum'},
]

for crypto in cryptos:
    try:
        tracker.open_position(
            symbol=crypto['symbol'],
            quantity=crypto['quantity'],
            entry_price=crypto['entry_price']
        )
        print(f"✅ 开仓: {crypto['symbol']} ({crypto['name']}) "
              f"{crypto['quantity']} @ ₩{crypto['entry_price']:,}")
    except Exception as e:
        print(f"❌ {crypto['symbol']}: {e}")

# ==========================================
# 2. 查看所有持仓
# ==========================================
print("\n2️⃣ 查看所有持仓")
print("------------------------------------------------------------")

try:
    all_positions = tracker.get_all_positions()
    print(f"✅ 总持仓数: {len(all_positions)}")
    
    for symbol, position in all_positions.items():
        print(f"\n{symbol}:")
        for key, value in position.items():
            print(f"   {key}: {value}")
except Exception as e:
    print(f"❌ 获取持仓失败: {e}")

# ==========================================
# 3. 分类查看持仓
# ==========================================
print("\n3️⃣ 分类查看持仓")
print("------------------------------------------------------------")

# 股票持仓
stock_positions = pm.get_stock_positions()
print(f"📈 股票持仓: {len(stock_positions)} 只")
for symbol, position in stock_positions.items():
    print(f"   {symbol}: {position}")

# 加密货币持仓
crypto_positions = pm.get_crypto_positions()
print(f"\n🪙 加密货币持仓: {len(crypto_positions)} 个")
for symbol, position in crypto_positions.items():
    print(f"   {symbol}: {position}")

# ==========================================
# 4. 更新价格并计算盈亏
# ==========================================
print("\n4️⃣ 更新价格并计算盈亏")
print("------------------------------------------------------------")

# 当前市场价格
current_prices = {
    '005930': 181200,   # 삼성전자 (无变化)
    '035420': 255000,   # NAVER (+1%)
    '035720': 56000,    # 카카오 (-2.4%)
    'KRW-BTC': 61000000,  # Bitcoin (+1.67%)
    'KRW-ETH': 4100000,   # Ethereum (+1.23%)
}

try:
    # 更新价格
    tracker.update_position_prices(current_prices)
    print("✅ 价格已更新")
    
    # 计算未实现盈亏
    unrealized_pnl = tracker.calculate_unrealized_pnl(current_prices)
    print(f"\n💰 未实现盈亏: ₩{unrealized_pnl:,.0f}")
    
    # 计算组合总值
    portfolio_value = tracker.calculate_portfolio_value(current_prices)
    print(f"💼 组合总值: ₩{portfolio_value:,.0f}")
    
except Exception as e:
    print(f"❌ 计算失败: {e}")

# ==========================================
# 5. 使用 PortfolioManager 分类统计
# ==========================================
print("\n5️⃣ 分类统计")
print("------------------------------------------------------------")

try:
    portfolio = pm.get_portfolio_by_type(current_prices)
    
    print("📊 股票:")
    print(f"   持仓数: {portfolio['stocks']['count']}")
    print(f"   总成本: ₩{portfolio['stocks']['total_cost']:,.0f}")
    print(f"   总市值: ₩{portfolio['stocks']['total_value']:,.0f}")
    print(f"   盈亏: ₩{portfolio['stocks']['total_pnl']:,.0f} "
          f"({portfolio['stocks']['total_pnl_pct']:+.2f}%)")
    
    print("\n📊 加密货币:")
    print(f"   持仓数: {portfolio['crypto']['count']}")
    print(f"   总成本: ₩{portfolio['crypto']['total_cost']:,.0f}")
    print(f"   总市值: ₩{portfolio['crypto']['total_value']:,.0f}")
    print(f"   盈亏: ₩{portfolio['crypto']['total_pnl']:,.0f} "
          f"({portfolio['crypto']['total_pnl_pct']:+.2f}%)")
    
    print("\n📊 总计:")
    print(f"   总成本: ₩{portfolio['total']['total_cost']:,.0f}")
    print(f"   总市值: ₩{portfolio['total']['total_value']:,.0f}")
    print(f"   总盈亏: ₩{portfolio['total']['total_pnl']:,.0f} "
          f"({portfolio['total']['total_pnl_pct']:+.2f}%)")
    
except Exception as e:
    print(f"❌ 分类统计失败: {e}")
    import traceback
    traceback.print_exc()

# ==========================================
# 6. 绩效指标
# ==========================================
print("\n6️⃣ 绩效指标")
print("------------------------------------------------------------")

try:
    metrics = tracker.calculate_performance_metrics(current_prices)
    
    if metrics:
        for key, value in metrics.items():
            print(f"   {key}: {value}")
    else:
        print("   （暂无绩效数据）")
        
except Exception as e:
    print(f"❌ 绩效计算失败: {e}")

# ==========================================
# 7. 清理测试数据（可选）
# ==========================================
print("\n7️⃣ 清理测试数据")
print("------------------------------------------------------------")

response = input("是否清理测试数据？(y/N): ")

if response.lower() == 'y':
    try:
        all_positions = tracker.get_all_positions()
        for symbol in all_positions.keys():
            tracker.close_position(symbol, current_prices.get(symbol, 0))
            print(f"✅ 已平仓: {symbol}")
        
        print("\n✅ 所有测试数据已清理")
    except Exception as e:
        print(f"❌ 清理失败: {e}")
else:
    print("⏭️  跳过清理，数据保留")

print("\n" + "="*60)
print("✅ 演示完成")
