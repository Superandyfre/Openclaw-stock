#!/usr/bin/env python3
"""
OpenClaw 生产级演示
完整的韩股+加密货币投资组合管理
"""
from openclaw.skills.execution.position_tracker import PositionTracker
from openclaw.core.portfolio_manager import PortfolioManager
from datetime import datetime

def print_header(title):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def print_section(title):
    """打印小节标题"""
    print(f"\n{title}")
    print("-" * 60)

# ==========================================
# 初始化
# ==========================================
print_header("🦞 OpenClaw 投���组合管理系统")

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
    ('005930', 10, 181200, '삼성전자', '韩国股票'),
    ('035420', 5, 252500, 'NAVER', '韩国股票'),
    ('035720', 15, 57400, '카카오', '韩国股票'),
    ('051910', 2, 385000, 'LG화학', '韩国股票'),
    ('KRW-BTC', 0.03, 60000000, 'Bitcoin', '加密货币'),
    ('KRW-ETH', 0.8, 4050000, 'Ethereum', '加密货币'),
]

print(f"计划建仓 {len(portfolio_plan)} 个头寸:\n")

successful_positions = []
failed_positions = []

for symbol, qty, price, name, asset_type in portfolio_plan:
    cost = qty * price
    result = tracker.open_position(symbol, qty, price)
    
    if result.get('success') != False:
        successful_positions.append(symbol)
        print(f"✅ {symbol:12s} ({name:10s}) [{asset_type:8s}]")
        print(f"   数量: {qty:>8.2f}  价格: ₩{price:>12,}  成本: ₩{cost:>12,.0f}")
    else:
        failed_positions.append((symbol, result.get('reason')))
        print(f"❌ {symbol:12s} ({name:10s}) - {result.get('reason', 'Unknown')}")

print(f"\n📊 开仓结果:")
print(f"   成功: {len(successful_positions)}/{len(portfolio_plan)}")
print(f"   剩余资金: ₩{tracker.cash:,}")

# ==========================================
# 2. 持仓概览
# ==========================================
print_section("2️⃣ 持仓概览")

stock_positions = pm.get_stock_positions()
crypto_positions = pm.get_crypto_positions()

print(f"📈 韩国股票 ({len(stock_positions)} 只):\n")
for symbol in stock_positions.keys():
    pos = tracker.positions[symbol]
    print(f"   {symbol:12s}  {pos['quantity']:>8.0f}주  "
          f"@ ₩{pos['avg_entry_price']:>10,}  "
          f"(₩{pos['total_cost']:>12,})")

print(f"\n🪙 加密货币 ({len(crypto_positions)} 个):\n")
for symbol in crypto_positions.keys():
    pos = tracker.positions[symbol]
    print(f"   {symbol:12s}  {pos['quantity']:>8.4f}  "
          f"@ ₩{pos['avg_entry_price']:>12,}  "
          f"(₩{pos['total_cost']:>12,.0f})")

# ==========================================
# 3. 价格更新与盈亏分析
# ==========================================
print_section("3️⃣ 价格更新与盈亏分析")

# 模拟市场价格（实际应该从 pykrx 获取）
current_prices = {
    '005930': 183000,      # +1.0%
    '035420': 255000,      # +1.0%
    '035720': 56000,       # -2.4%
    '051910': 390000,      # +1.3%
    'KRW-BTC': 61500000,   # +2.5%
    'KRW-ETH': 4100000,    # +1.2%
}

print("💹 市场价格更新:\n")
for symbol, price in current_prices.items():
    if symbol in tracker.positions:
        entry_price = tracker.positions[symbol]['avg_entry_price']
        change_pct = ((price - entry_price) / entry_price) * 100
        
        emoji = "🟢" if change_pct > 0 else "🔴" if change_pct < 0 else "⚪"
        print(f"   {emoji} {symbol:12s}  ₩{price:>12,}  ({change_pct:+6.2f}%)")

# 更新价格
tracker.update_position_prices(current_prices)

# 计算总值
portfolio_value = tracker.calculate_portfolio_value(current_prices)
total_value = tracker.cash + portfolio_value

print(f"\n💰 组合总览:")
print(f"   现金余额: ₩{tracker.cash:>15,}")
print(f"   持仓市值: ₩{portfolio_value:>15,}")
print(f"   ───────────────────────────────")
print(f"   组合总值: ₩{total_value:>15,}")
print(f"   总收益:   ₩{(total_value - INITIAL_CAPITAL):>15,}  "
      f"({((total_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100):+.2f}%)")

# ==========================================
# 4. 分类统计
# ==========================================
print_section("4️⃣ 分类统计")

try:
    portfolio = pm.get_portfolio_by_type(current_prices)
    
    # 股票
    stocks = portfolio.get('stocks', {})
    if stocks.get('count', 0) > 0:
        stocks_cost = stocks.get('total_cost', 0)
        stocks_value = stocks.get('total_value', 0)
        stocks_pnl = stocks_value - stocks_cost
        stocks_pnl_pct = (stocks_pnl / stocks_cost * 100) if stocks_cost > 0 else 0
        
        print(f"📊 韩国股票:")
        print(f"   持仓数:   {stocks['count']} 只")
        print(f"   总成本:   ₩{stocks_cost:>15,}")
        print(f"   当前市值: ₩{stocks_value:>15,}")
        print(f"   盈亏:     ₩{stocks_pnl:>15,}  ({stocks_pnl_pct:+.2f}%)")
    
    # 加密货币
    crypto = portfolio.get('crypto', {})
    if crypto.get('count', 0) > 0:
        crypto_cost = crypto.get('total_cost', 0)
        crypto_value = crypto.get('total_value', 0)
        crypto_pnl = crypto_value - crypto_cost
        crypto_pnl_pct = (crypto_pnl / crypto_cost * 100) if crypto_cost > 0 else 0
        
        print(f"\n📊 加密货币:")
        print(f"   持仓数:   {crypto['count']} 个")
        print(f"   总成本:   ₩{crypto_cost:>15,}")
        print(f"   当前市值: ₩{crypto_value:>15,}")
        print(f"   盈亏:     ₩{crypto_pnl:>15,}  ({crypto_pnl_pct:+.2f}%)")
    
except Exception as e:
    print(f"⚠️  分类统计计算出错: {e}")

# ==========================================
# 5. 绩效指标
# ==========================================
print_section("5️⃣ 绩效指标")

try:
    metrics = tracker.calculate_performance_metrics(current_prices)
    
    print(f"📊 投资组合绩效:\n")
    print(f"   组合市值:     ₩{metrics['portfolio_value']:>15,.0f}")
    print(f"   总收益:       ₩{metrics['total_return']:>15,.0f}")
    print(f"   收益率:       {metrics['total_return_pct']:>15.2f}%")
    print(f"   未实现盈亏:   ₩{metrics['unrealized_pnl']:>15,.0f}")
    print(f"   已实现盈亏:   ₩{metrics['realized_pnl']:>15,.0f}")
    print(f"\n   持仓数量:     {int(metrics['num_positions']):>15}")
    print(f"   已平仓数:     {int(metrics['num_closed_trades']):>15}")
    print(f"   胜率:         {metrics['win_rate']:>15.1f}%")
    print(f"   夏普比率:     {metrics['sharpe_ratio']:>15.2f}")
    print(f"   最大回撤:     {metrics['max_drawdown']:>15.2f}%")
    
except Exception as e:
    print(f"⚠️  绩效指标计算出错: {e}")

# ==========================================
# 6. 风险提示
# ==========================================
print_section("6️⃣ 风险提示")

# 检查资金使用率
used_capital = INITIAL_CAPITAL - tracker.cash
capital_usage_pct = (used_capital / INITIAL_CAPITAL) * 100

print(f"💡 资金使用:")
print(f"   已使用: ₩{used_capital:,} ({capital_usage_pct:.1f}%)")
print(f"   剩余:   ₩{tracker.cash:,} ({(100 - capital_usage_pct):.1f}%)")

if capital_usage_pct > 90:
    print(f"\n⚠️  警告: 资金使用率过高 ({capital_usage_pct:.1f}%)")
elif capital_usage_pct > 70:
    print(f"\n💡 提示: 资金使用率较高 ({capital_usage_pct:.1f}%)")
else:
    print(f"\n✅ 资金使用率健康 ({capital_usage_pct:.1f}%)")

# 检查单个持仓风险
print(f"\n💡 持仓集中度:")
for symbol, pos in tracker.positions.items():
    position_value = pos['quantity'] * current_prices.get(symbol, pos['avg_entry_price'])
    concentration = (position_value / portfolio_value) * 100 if portfolio_value > 0 else 0
    
    if concentration > 30:
        emoji = "⚠️"
    elif concentration > 20:
        emoji = "💡"
    else:
        emoji = "✅"
    
    print(f"   {emoji} {symbol:12s}  {concentration:>5.1f}%")

# ==========================================
# 总结
# ==========================================
print_header("📊 投资组合总结")

print(f"开仓时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"初始资金: ₩{INITIAL_CAPITAL:,}")
print(f"组合总值: ₩{total_value:,}")
print(f"总收益:   ₩{(total_value - INITIAL_CAPITAL):,} ({((total_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100):+.2f}%)")
print(f"\n持仓分布:")
print(f"   韩国股票: {len(stock_positions)} 只")
print(f"   加密货币: {len(crypto_positions)} 个")

print(f"\n{'='*60}")
print(f"✅ 演示完成")
print(f"{'='*60}\n")
