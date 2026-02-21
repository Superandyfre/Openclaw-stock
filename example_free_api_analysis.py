"""
免费数据源综合示例

演示如何使用所有免费API进行市场分析
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from openclaw.skills.data_collection.free_data_sources import FreeDataSourceConnector
import time


def comprehensive_market_analysis():
    """综合市场分析 - 使用所有免费API"""
    
    connector = FreeDataSourceConnector()
    
    print("\n" + "="*70)
    print(" 🚀 加密货币市场综合分析（纯免费API）")
    print("="*70)
    
    # ==================== 1. 加密货币价格分析 ====================
    print("\n📊 【第一部分：加密货币价格分析】")
    print("-"*70)
    
    # Binance实时数据
    print("\n💱 Binance实时数据:")
    ticker = connector.get_binance_ticker_24h('BTCUSDT')
    if ticker:
        print(f"   BTC/USDT: ${ticker['last_price']:,.2f}")
        print(f"   24h涨跌: {ticker['price_change_pct']:+.2f}%")
        print(f"   24h成交量: {ticker['volume']:,.2f} BTC")
        print(f"   24h成交额: ${ticker['quote_volume']:,.0f}")
        print(f"   24h高点: ${ticker['high']:,.2f}")
        print(f"   24h低点: ${ticker['low']:,.2f}")
    
    time.sleep(1)
    
    # CoinGecko市值数据
    print("\n🦎 CoinGecko市值数据:")
    btc_price = connector.get_coingecko_price('bitcoin')
    if btc_price:
        print(f"   价格: ${btc_price['price']:,.0f}")
        print(f"   市值: ${btc_price['market_cap']:,.0f}")
        print(f"   24h成交量: ${btc_price['volume_24h']:,.0f}")
        print(f"   24h涨跌: {btc_price['change_24h']:+.2f}%")
    
    time.sleep(2)
    
    # ==================== 2. 市场情绪分析 ====================
    print("\n" + "-"*70)
    print("😱 【第二部分：市场情绪分析】")
    print("-"*70)
    
    fg_index = connector.get_fear_greed_index(limit=7)
    if fg_index:
        print(f"\n🎭 恐慌贪婪指数:")
        print(f"   当前指数: {fg_index['value']}/100")
        print(f"   市场情绪: {fg_index['classification']}")
        print(f"   官方分类: {fg_index['value_classification']}")
        
        # 投资建议
        if fg_index['classification'] == 'EXTREME_FEAR':
            print(f"   💡 建议: 市场极度恐慌，可能是买入机会（逢低建仓）")
        elif fg_index['classification'] == 'FEAR':
            print(f"   💡 建议: 市场恐慌，可以考虑分批买入")
        elif fg_index['classification'] == 'EXTREME_GREED':
            print(f"   ⚠️  建议: 市场极度贪婪，注意风险（考虑止盈）")
        elif fg_index['classification'] == 'GREED':
            print(f"   ⚠️  建议: 市场贪婪，保持警惕")
        else:
            print(f"   ℹ️  建议: 市场情绪中性，观望为主")
        
        # 7天趋势
        if len(fg_index['history']) > 1:
            change = fg_index['history'][0]['value'] - fg_index['history'][-1]['value']
            trend = "改善" if change > 0 else "恶化" if change < 0 else "稳定"
            print(f"   📈 7天趋势: {trend} ({change:+d}点)")
    
    time.sleep(1)
    
    # ==================== 3. 宏观市场环境 ====================
    print("\n" + "-"*70)
    print("🌍 【第三部分：宏观市场环境】")
    print("-"*70)
    
    # 标普500
    print("\n📈 传统市场指数:")
    sp500 = connector.get_yahoo_finance_data('^GSPC', period='5d')
    if sp500:
        print(f"   标普500: {sp500['current_price']:,.2f}")
        print(f"   5日涨跌: {sp500['price_change_pct']:+.2f}%")
        print(f"   5日高点: {sp500['high']:,.2f}")
        print(f"   5日低点: {sp500['low']:,.2f}")
    
    time.sleep(2)
    
    # 黄金
    gold = connector.get_yahoo_finance_data('GC=F', period='5d')
    if gold:
        print(f"\n   黄金期货: ${gold['current_price']:,.2f}/oz")
        print(f"   5日涨跌: {gold['price_change_pct']:+.2f}%")
    
    # ==================== 4. DeFi生态分析 ====================
    print("\n" + "-"*70)
    print("🏦 【第四部分：DeFi生态分析】")
    print("-"*70)
    
    time.sleep(1)
    
    # 总TVL
    tvl = connector.get_defillama_tvl()
    if tvl:
        print(f"\n💰 DeFi总锁仓量 (TVL):")
        print(f"   总TVL: ${tvl['total_tvl']:,.0f}")
        print(f"   更新时间: {tvl['date']}")
    
    time.sleep(1)
    
    # Uniswap
    uniswap = connector.get_defillama_tvl('uniswap')
    if uniswap:
        print(f"\n🦄 Uniswap DEX:")
        print(f"   TVL: ${uniswap['tvl']:,.0f}")
        if uniswap.get('change_1d'):
            print(f"   1日变化: {uniswap['change_1d']:+.2f}%")
        if uniswap.get('change_7d'):
            print(f"   7日变化: {uniswap['change_7d']:+.2f}%")
    
    # ==================== 5. 项目开发活跃度 ====================
    print("\n" + "-"*70)
    print("👨‍💻 【第五部分：项目开发活跃度】")
    print("-"*70)
    
    time.sleep(1)
    
    # Bitcoin仓库
    btc_repo = connector.get_github_repo_stats('bitcoin', 'bitcoin')
    if btc_repo:
        print(f"\n⚙️  Bitcoin Core:")
        print(f"   Stars: {btc_repo['stars']:,}")
        print(f"   Forks: {btc_repo['forks']:,}")
        print(f"   主语言: {btc_repo['language']}")
        print(f"   最近更新: {btc_repo['pushed_at']}")
        
        if btc_repo['recent_commits']:
            print(f"   最近3次提交:")
            for commit in btc_repo['recent_commits'][:3]:
                print(f"     • [{commit['sha']}] {commit['message'][:60]}")
    
    # ==================== 6. 综合建议 ====================
    print("\n" + "="*70)
    print("💡 【综合投资建议】")
    print("="*70)
    
    # 根据多维度数据生成建议
    signals = []
    
    # 价格信号
    if ticker and ticker['price_change_pct'] > 5:
        signals.append("✅ BTC价格强势上涨（+{:.2f}%）".format(ticker['price_change_pct']))
    elif ticker and ticker['price_change_pct'] < -5:
        signals.append("⚠️  BTC价格大幅下跌（{:.2f}%）".format(ticker['price_change_pct']))
    
    # 情绪信号
    if fg_index:
        if fg_index['classification'] in ['EXTREME_FEAR', 'FEAR']:
            signals.append("✅ 市场情绪恐慌，可能存在低估机会")
        elif fg_index['classification'] in ['EXTREME_GREED', 'GREED']:
            signals.append("⚠️  市场情绪贪婪，注意泡沫风险")
    
    # 传统市场信号
    if sp500 and sp500['price_change_pct'] < -2:
        signals.append("⚠️  传统市场走弱，风险资产承压")
    elif sp500 and sp500['price_change_pct'] > 2:
        signals.append("✅ 传统市场走强，风险偏好提升")
    
    # DeFi信号
    if uniswap and uniswap.get('change_7d'):
        if uniswap['change_7d'] > 10:
            signals.append("✅ DeFi TVL增长，生态活跃")
        elif uniswap['change_7d'] < -10:
            signals.append("⚠️  DeFi TVL下降，资金流出")
    
    if signals:
        print("\n关键信号:")
        for signal in signals:
            print(f"  {signal}")
    else:
        print("\n  ℹ️  市场整体平稳，暂无明显信号")
    
    print("\n建议操作:")
    if fg_index and fg_index['value'] < 30:
        print("  📌 分批建仓策略：市场恐慌时逢低买入")
        print("  📌 仓位建议：小仓位试探（10-20%资金）")
    elif fg_index and fg_index['value'] > 70:
        print("  📌 止盈策略：市场贪婪时部分获利了结")
        print("  📌 仓位建议：减仓观望（保留50%以下仓位）")
    else:
        print("  📌 观望策略：等待更明确信号")
        print("  📌 仓位建议：维持当前仓位，不追涨杀跌")
    
    print("\n风险提示:")
    print("  ⚠️  以上分析仅供参考，不构成投资建议")
    print("  ⚠️  加密货币投资风险极高，请合理控制仓位")
    print("  ⚠️  建议止损：-10%，止盈：+20%")
    
    print("\n" + "="*70)
    print("分析完成！所有数据来自免费API，成本$0/月 🎉")
    print("="*70 + "\n")


if __name__ == '__main__':
    comprehensive_market_analysis()
