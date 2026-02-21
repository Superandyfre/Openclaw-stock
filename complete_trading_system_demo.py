"""
完整的交易系统演示

整合所有模块：
1. 免费数据源（FreeDataSourceConnector）
2. 市场深度分析（MarketDepthAnalyzer）
3. 高级技术指标（AdvancedIndicatorMonitor）
4. 市场情绪分析（MarketSentimentAnalyzer）
5. 智能信号聚合（SmartSignalAggregator）
6. 增强AI顾问（EnhancedAITradingAdvisor）
7. 自动监控（AutoMarketMonitor）
8. 回测引擎（RealDataBacktestEngine）
"""
import asyncio
from typing import Dict, List, Any
from datetime import datetime
from loguru import logger

# 导入所有模块
try:
    from openclaw.skills.analysis.enhanced_ai_trading_advisor import EnhancedAITradingAdvisor
    from openclaw.skills.monitoring.auto_market_monitor import AutoMarketMonitor
    from openclaw.skills.backtesting.real_data_backtest_engine import RealDataBacktestEngine
    ALL_MODULES_AVAILABLE = True
except ImportError as e:
    logger.error(f"模块导入失败: {e}")
    ALL_MODULES_AVAILABLE = False


class CompleteTradingSystem:
    """完整的加密货币交易系统"""
    
    def __init__(self):
        """初始化系统"""
        logger.info("="*80)
        logger.info("🚀 初始化完整交易系统")
        logger.info("="*80)
        
        if not ALL_MODULES_AVAILABLE:
            logger.error("❌ 系统模块不完整，无法启动")
            return
        
        # 初始化各个组件
        self.ai_advisor = EnhancedAITradingAdvisor(enable_derivatives=False)
        logger.info("✅ AI交易顾问已就绪")
        
        self.monitor = AutoMarketMonitor(
            symbols=[('BTCUSDT', 'bitcoin'), ('ETHUSDT', 'ethereum')],
            check_interval_minutes=60,
            save_reports=True
        )
        logger.info("✅ 自动监控系统已就绪")
        
        self.backtest_engine = RealDataBacktestEngine()
        logger.info("✅ 回测引擎已就绪")
        
        logger.info("="*80)
        logger.info("✅ 系统初始化完成")
        logger.info("="*80)
        logger.info("")
    
    async def run_comprehensive_analysis(self, symbol: str = 'BTCUSDT', coin_id: str = 'bitcoin'):
        """运行综合分析"""
        
        print("\n" + "="*80)
        print(f"📊 开始综合分析: {symbol}")
        print("="*80 + "\n")
        
        # 1. AI顾问分析
        print("【步骤1/3】运行AI顾问分析...")
        analysis = await self.ai_advisor.analyze_crypto(symbol, coin_id)
        
        # 打印分析报告
        print("\n" + self.ai_advisor.get_summary_report(analysis))
        
        # 2. 获取推荐
        recommendation = analysis.get('recommendation', {})
        action = recommendation.get('action', 'NEUTRAL')
        confidence = recommendation.get('confidence', 0)
        
        print(f"\n【步骤2/3】交易决策")
        print(f"  推荐操作: {action}")
        print(f"  置信度: {confidence:.1%}")
        print(f"  风险等级: {recommendation.get('risk_level', 'N/A')}")
        print(f"  建议仓位: {recommendation.get('position_size', 'N/A')}")
        
        if action != 'NEUTRAL':
            print(f"\n  ✅ 系统建议: {recommendation.get('recommendation_text', '')}")
        else:
            print(f"\n  ℹ️  系统建议: 暂时观望，等待更明确信号")
        
        # 3. 回测验证（如果是买入信号）
        if action == 'BUY' and confidence >= 0.6:
            print(f"\n【步骤3/3】回测验证...")
            print(f"  使用最近7天数据验证MA交叉策略...")
            
            backtest_results = await self.backtest_engine.backtest_simple_strategy(
                symbol=symbol,
                coin_id=coin_id,
                days=7,
                interval='1h',
                strategy_type='MA_CROSS'
            )
            
            perf = backtest_results.get('performance', {})
            print(f"\n  回测收益率: {perf.get('total_return_pct', 0):+.2f}%")
            print(f"  胜率: {perf.get('win_rate', 0):.1f}%")
            print(f"  最大回撤: {perf.get('max_drawdown_pct', 0):.2f}%")
        
        print("\n" + "="*80)
        print("📈 综合分析完成")
        print("="*80 + "\n")
        
        return analysis
    
    async def run_monitoring_cycle(self):
        """运行一轮监控"""
        
        print("\n" + "="*80)
        print("🔍 执行市场监控...")
        print("="*80 + "\n")
        
        await self.monitor.run_once()
        
        # 生成报告
        report = await self.monitor.generate_daily_report()
        print(report)
        
        # 显示告警
        alerts = self.monitor.get_alerts_summary(hours=24)
        print(f"\n{alerts}")
    
    async def run_strategy_comparison(self, symbol: str = 'BTCUSDT', coin_id: str = 'bitcoin'):
        """对比不同策略的回测结果"""
        
        print("\n" + "="*80)
        print(f"📊 策略对比回测: {symbol}")
        print("="*80 + "\n")
        
        strategies = ['MA_CROSS', 'RSI', 'BOLLINGER']
        results_summary = []
        
        for strategy in strategies:
            print(f"\n【回测策略】{strategy}")
            print("-"*80)
            
            results = await self.backtest_engine.backtest_simple_strategy(
                symbol=symbol,
                coin_id=coin_id,
                days=7,
                interval='1h',
                strategy_type=strategy
            )
            
            perf = results.get('performance', {})
            results_summary.append({
                'strategy': strategy,
                'return_pct': perf.get('total_return_pct', 0),
                'win_rate': perf.get('win_rate', 0),
                'max_drawdown': perf.get('max_drawdown_pct', 0),
                'trades': perf.get('total_trades', 0)
            })
            
            print(f"  收益率: {perf.get('total_return_pct', 0):+.2f}%")
            print(f"  胜率: {perf.get('win_rate', 0):.1f}%")
            print(f"  最大回撤: {perf.get('max_drawdown_pct', 0):.2f}%")
            print(f"  交易次数: {perf.get('total_trades', 0)}")
        
        # 排名
        print("\n" + "="*80)
        print("🏆 策略排名（按收益率）")
        print("="*80)
        
        sorted_results = sorted(results_summary, key=lambda x: x['return_pct'], reverse=True)
        
        for i, result in enumerate(sorted_results, 1):
            print(f"\n{i}. {result['strategy']}")
            print(f"   收益率: {result['return_pct']:+.2f}%")
            print(f"   胜率: {result['win_rate']:.1f}%")
            print(f"   最大回撤: {result['max_drawdown']:.2f}%")
            print(f"   交易次数: {result['trades']}")
        
        print("\n" + "="*80 + "\n")
        
        return sorted_results


async def main():
    """主函数 - 演示完整系统"""
    
    system = CompleteTradingSystem()
    
    # 菜单
    print("\n" + "="*80)
    print("🎯 完整交易系统演示")
    print("="*80)
    print("\n选择演示模式:")
    print("  1. 单次综合分析（推荐新用户）")
    print("  2. 市场监控循环")
    print("  3. 策略对比回测")
    print("  4. 完整演示（全部功能）")
    print("\n")
    
    choice = input("请输入选项 (1-4，直接回车默认1): ").strip() or "1"
    
    if choice == "1":
        # 单次分析
        await system.run_comprehensive_analysis('BTCUSDT', 'bitcoin')
    
    elif choice == "2":
        # 监控循环
        await system.run_monitoring_cycle()
    
    elif choice == "3":
        # 策略对比
        await system.run_strategy_comparison('BTCUSDT', 'bitcoin')
    
    elif choice == "4":
        # 完整演示
        print("\n【第一部分】综合分析BTC")
        await system.run_comprehensive_analysis('BTCUSDT', 'bitcoin')
        
        print("\n按回车继续...")
        input()
        
        print("\n【第二部分】监控ETH")
        await system.run_monitoring_cycle()
        
        print("\n按回车继续...")
        input()
        
        print("\n【第三部分】策略对比")
        await system.run_strategy_comparison('BTCUSDT', 'bitcoin')
    
    else:
        print("无效选项，退出")


if __name__ == '__main__':
    asyncio.run(main())
