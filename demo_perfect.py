#!/usr/bin/env python3
"""
OpenClaw 完美演示版本
基于实际的 API 结构
"""
from openclaw.skills.execution.position_tracker import PositionTracker
from openclaw.core.portfolio_manager import PortfolioManager
from datetime import datetime

def print_header(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def print_section(title):
    print(f"\n{title}")
    print("-" * 70)

# ==========================================
# 初始化
# ==========================================
print_header("🦞 OpenClaw 韩股交易系统 - 完美演示")

INITIAL_CAPITAL = 10_000_000  # 1000万韩元
tracker = PositionTracker(initial_capital=INITIAL_CAPITAL)
pm = PortfolioManager(tracker)

print(f"✅ 系统初始化成功")
print(f"   初始资金: ₩{INITIAL_CAPITAL:,}")
print(f"   当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ==========================================
# 1. 建立投资组合
# ==========================================
print_section("1️⃣ 建立投资组合")

portfolio_plan = [
    # (代码, 数量, 价格, 名称, 类型)
    ('005930', 10, 181200, '삼성전자', '🇰🇷 韩国股票'),
    ('035420', 5, 252500, 'NAVER', '🇰🇷 韩国股票'),
    ('035720', 15, 57400, '카카오', '🇰🇷 韩国股票'),
    ('051910', 2, 385000, 'LG화학', '🇰🇷 韩国股票'),
    ('KRW-BTC', 0.03, 60000000, 'Bitcoin', '🪙 加密货币'),
    ('KRW-ETH', 0.8, 4050000, 'Ethereum', '🪙 加密货币'),
]

print(f"计划建仓 {len(portfolio_plan)} 个头寸:\n")

successful = []
failed = []

for symbol, qty, price, name, asset_type in portfolio_plan:
    cost = qty * price
    result = tracker.open_position(symbol, qty, price)
    
    if result.get('success') != False:
        successful.append(symbol)
        print(f"✅ {asset_type}  {symbol:12s} ({name:12s})")
        print(f"   数量: {qty:>8.2f}  价格: ₩{price:>12,}  成本: ₩{cost:>12,.0f}")
    else:
        failed.append((symbol, result.get('reason')))
        print(f"❌ {asset_type}  {symbol:12s} ({name:12s}) - {result.get('reason', '未知')}")

print(f"\n📊 建仓结果:")
print(f"   成功: {len(successful)}/{len(portfolio_plan)}")
print(f"   失败: {len(failed)}")
print(f"   剩余现金: ₩{tracker.cash:,}")

# ==========================================
# 2. 持仓总览
# ==========================================
print_section("2️⃣ 持仓总览")

stock_positions = pm.get_stock_positions()
crypto_positions = pm.get_crypto_positions()

print(f"📈 韩国股票 ({len(stock_positions)} 只):\n")
for symbol in stock_positions.keys():
    pos = tracker.positions[symbol]
    print(f"   {symbol:12s}  {pos['quantity']:>8.0f}주  "
          f"@ ₩{pos['avg_entry_price']:>10,}  "
          f"成本: ₩{pos['total_cost']:>12,}")

if crypto_positions:
    print(f"\n🪙 加密货币 ({len(crypto_positions)} 个):\n")
    for symbol in crypto_positions.keys():
        pos = tracker.positions[symbol]
        print(f"   {symbol:12s}  {pos['quantity']:>8.4f}  "
              f"@ ₩{pos['avg_entry_price']:>12,}  "
              f"成本: ₩{pos['total_cost']:>12,.0f}")

# ==========================================
# 3. 市场价格更新
# ==========================================
print_section("3️⃣ 市场价格更新")

# 模拟市场价格（实际应该从 pykrx 获取）
current_prices = {
    '005930': 183000,      # +1.0%
    '035420': 255000,      # +1.0%
    '035720': 56000,       # -2.4%
    '051910': 390000,      # +1.3%
    'KRW-BTC': 61500000,   # +2.5%
    'KRW-ETH': 4100000,    # +1.2%
}

print("💹 当前市场价格:\n")
for symbol in tracker.positions.keys():
    if symbol in current_prices:
        entry_price = tracker.positions[symbol]['avg_entry_price']
        current_price = current_prices[symbol]
        change_pct = ((current_price - entry_price) / entry_price) * 100
        
        emoji = "🟢" if change_pct > 0 else "🔴" if change_pct < 0 else "⚪"
        print(f"   {emoji} {symbol:12s}  ₩{current_price:>12,}  ({change_pct:+6.2f}%)")

# 更新价格
tracker.update_position_prices(current_prices)

# ==========================================
# 4. 盈亏分析（完美版）
# ==========================================
print_section("4️⃣ 盈亏分析")

# 获取完整的组合数据
portfolio = pm.get_portfolio_by_type(current_prices)

# 股票
stocks = portfolio['stocks']
print("📊 韩国股票:")
print(f"   持仓数:     {stocks['count']}")
print(f"   总成本:     ₩{stocks['total_cost']:>15,.0f}")
print(f"   当前市值:   ₩{stocks['total_value']:>15,.0f}")
print(f"   未实现盈亏: ₩{stocks['unrealized_pnl']:>15,.0f}  "
      f"({stocks['unrealized_pnl_pct']:+.2f}%)")

# 显示每只股票的详细盈亏
print(f"\n   持仓明细:")
for symbol, pos in stocks['positions'].items():
    print(f"     {symbol:10s}  "
          f"₩{pos['current_value']:>12,.0f}  "
          f"盈亏: ₩{pos['unrealized_pnl']:>10,.0f} "
          f"({pos['unrealized_pnl_pct']:+.2f}%)")

# 加密货币
if portfolio['crypto']['count'] > 0:
    crypto = portfolio['crypto']
    print(f"\n📊 加密货币:")
    print(f"   持仓数:     {crypto['count']}")
    print(f"   总成本:     ₩{crypto['total_cost']:>15,.0f}")
    print(f"   当���市值:   ₩{crypto['total_value']:>15,.0f}")
    print(f"   未实现盈亏: ₩{crypto['unrealized_pnl']:>15,.0f}  "
          f"({crypto['unrealized_pnl_pct']:+.2f}%)")
    
    print(f"\n   持仓明细:")
    for symbol, pos in crypto['positions'].items():
        print(f"     {symbol:10s}  "
              f"₩{pos['current_value']:>12,.0f}  "
              f"盈亏: ₩{pos['unrealized_pnl']:>10,.0f} "
              f"({pos['unrealized_pnl_pct']:+.2f}%)")

# 总计
total = portfolio['total']
print(f"\n📊 组合总计:")
print(f"   初始资金:   ₩{total['initial_capital']:>15,}")
print(f"   现金余额:   ₩{total['cash']:>15,}")
print(f"   持仓市值:   ₩{total['position_value']:>15,}")
print(f"   组合总值:   ₩{total['portfolio_value']:>15,}")
print(f"   ───────────────────────────────────────────")
print(f"   总盈亏:     ₩{total['total_pnl']:>15,.0f}  "
      f"({total['total_pnl_pct']:+.2f}%)")

# ==========================================
# 5. 绩效指标
# ==========================================
print_section("5️⃣ 绩效指标")

try:
    metrics = tracker.calculate_performance_metrics(current_prices)
    
    print(f"📈 投资表现:\n")
    print(f"   组合市值:     ₩{metrics['portfolio_value']:>15,.0f}")
    print(f"   总收益:       ₩{metrics['total_return']:>15,.0f}")
    print(f"   收益率:       {metrics['total_return_pct']:>15.2f}%")
    print(f"   未实现盈亏:   ₩{metrics['unrealized_pnl']:>15,.0f}")
    print(f"   已实现盈亏:   ₩{metrics['realized_pnl']:>15,.0f}")
    
    print(f"\n📊 交易统计:\n")
    print(f"   持仓数量:     {int(metrics['num_positions']):>15}")
    print(f"   已平仓数:     {int(metrics['num_closed_trades']):>15}")
    print(f"   胜率:         {metrics['win_rate']:>14.1f}%")
    
    print(f"\n📉 风险指标:\n")
    print(f"   夏普比率:     {metrics['sharpe_ratio']:>15.2f}")
    print(f"   最大回撤:     {metrics['max_drawdown']:>14.2f}%")
    
except Exception as e:
    print(f"⚠️  绩效指标计算: {e}")

# ==========================================
# 6. 风险分析
# ==========================================
print_section("6️⃣ 风险分析")

# 资金使用率
used_capital = INITIAL_CAPITAL - tracker.cash
capital_usage_pct = (used_capital / INITIAL_CAPITAL) * 100

print(f"💰 资金使用:")
print(f"   已使用: ₩{used_capital:>12,}  ({capital_usage_pct:>5.1f}%)")
print(f"   剩余:   ₩{tracker.cash:>12,}  ({(100 - capital_usage_pct):>5.1f}%)")

if capital_usage_pct > 90:
    print(f"\n   ⚠️  警告: 资金使用率过高！")
elif capital_usage_pct > 70:
    print(f"\n   💡 提示: 资金使用率较高，注意风险")
else:
    print(f"\n   ✅ 资金使用率健康")

# 持仓集中度
portfolio_value_calc = tracker.calculate_portfolio_value(current_prices)

print(f"\n📊 持仓集中度:")
concentration_list = []
for symbol, pos in tracker.positions.items():
    current_price = current_prices.get(symbol, pos['avg_entry_price'])
    position_value = pos['quantity'] * current_price
    concentration = (position_value / portfolio_value_calc) * 100 if portfolio_value_calc > 0 else 0
    concentration_list.append((symbol, concentration))

# 排序并显示
for symbol, concentration in sorted(concentration_list, key=lambda x: x[1], reverse=True):
    emoji = "⚠️" if concentration > 30 else "💡" if concentration > 20 else "✅"
    print(f"   {emoji} {symbol:12s}  {concentration:>5.1f}%")

# ==========================================
# 总结
# ==========================================
print_header("📊 投资组合总结")

total_value_final = tracker.cash + portfolio_value_calc
total_return = total_value_final - INITIAL_CAPITAL
total_return_pct = (total_return / INITIAL_CAPITAL) * 100

print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\n💰 资金状况:")
print(f"   初始资金: ₩{INITIAL_CAPITAL:,}")
print(f"   现金余额: ₩{tracker.cash:,}")
print(f"   持仓市值: ₩{portfolio_value_calc:,}")
print(f"   组合总值: ₩{total_value_final:,}")

print(f"\n📈 收益情况:")
print(f"   总收益:   ₩{total_return:,}")
print(f"   收益率:   {total_return_pct:+.2f}%")

print(f"\n📊 持仓分布:")
print(f"   韩国股票: {len(stock_positions)} 只")
print(f"   加密货币: {len(crypto_positions)} 个")
print(f"   总持仓:   {len(tracker.positions)} 个")

print(f"\n🎯 系统状态:")
print(f"   开仓成功: {len(successful)}/{len(portfolio_plan)}")
print(f"   已平仓:   {len(tracker.closed_positions)}")
print(f"   交易记录: {len(tracker.trade_history)}")

print(f"\n{'='*70}")
print(f"✅ 演示完成")
print(f"{'='*70}\n")
