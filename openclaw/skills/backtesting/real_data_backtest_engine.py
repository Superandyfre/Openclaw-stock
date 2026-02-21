"""
增强版回测系统

整合免费数据源，使用真实历史数据进行回测
支持：
1. CoinGecko历史价格数据
2. Binance K线数据
3. 技术指标策略回测
4. 风控规则验证
"""
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger
import numpy as np

try:
    from openclaw.skills.data_collection.free_data_sources import FreeDataSourceConnector
    DATA_SOURCE_AVAILABLE = True
except ImportError:
    logger.warning("免费数据源连接器未找到")
    DATA_SOURCE_AVAILABLE = False

try:
    from openclaw.skills.backtesting.enhanced_backtest import EnhancedBacktest
    BACKTEST_AVAILABLE = True
except ImportError:
    logger.warning("回测引擎未找到")
    BACKTEST_AVAILABLE = False


class RealDataBacktestEngine:
    """使用真实数据的回测引擎"""
    
    def __init__(self):
        """初始化回测引擎"""
        if DATA_SOURCE_AVAILABLE:
            self.data_connector = FreeDataSourceConnector()
            logger.info("✅ 数据源连接器初始化成功")
        else:
            self.data_connector = None
            logger.error("❌ 数据源不可用")
        
        if BACKTEST_AVAILABLE:
            self.backtest_engine = EnhancedBacktest()
            logger.info("✅ 回测引擎初始化成功")
        else:
            self.backtest_engine = None
            logger.error("❌ 回测引擎不可用")
    
    async def fetch_historical_data(
        self,
        symbol: str,
        coin_id: str,
        interval: str = '1h',
        days: int = 30
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取历史数据
        
        Args:
            symbol: Binance交易对（如 'BTCUSDT'）
            coin_id: CoinGecko币种ID（如 'bitcoin'）
            interval: K线时间周期 (1m, 5m, 15m, 1h, 4h, 1d)
            days: 历史天数
        
        Returns:
            K线数据列表
        """
        if not self.data_connector:
            logger.error("数据源不可用")
            return None
        
        logger.info(f"获取 {symbol} 最近{days}天的{interval}数据...")
        
        try:
            # 计算需要的K线数量
            intervals_per_day = {
                '1m': 1440,
                '5m': 288,
                '15m': 96,
                '1h': 24,
                '4h': 6,
                '1d': 1
            }
            
            limit = min(intervals_per_day.get(interval, 24) * days, 1000)
            
            # 获取Binance K线数据
            klines = self.data_connector.get_binance_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            
            if klines:
                logger.info(f"✅ 获取到{len(klines)}根K线")
                return klines
            else:
                logger.error("未获取到数据")
                return None
        
        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            return None
    
    async def backtest_simple_strategy(
        self,
        symbol: str,
        coin_id: str,
        days: int = 30,
        interval: str = '1h',
        strategy_type: str = 'MA_CROSS',
        initial_capital: float = 10000.0
    ) -> Dict[str, Any]:
        """
        回测简单策略
        
        Args:
            symbol: 交易对
            coin_id: CoinGecko ID
            days: 回测天数
            interval: K线周期
            strategy_type: 策略类型 ('MA_CROSS', 'RSI', 'BOLLINGER')
            initial_capital: 初始资金
        
        Returns:
            回测结果
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"开始回测 {symbol} - {strategy_type}策略")
        logger.info(f"{'='*70}")
        
        # 获取历史数据
        klines = await self.fetch_historical_data(symbol, coin_id, interval, days)
        
        if not klines:
            return {"error": "数据获取失败"}
        
        # 转换为回测所需格式
        backtest_data = []
        for kline in klines:
            backtest_data.append({
                'timestamp': kline['timestamp'],
                'open': kline['open'],
                'high': kline['high'],
                'low': kline['low'],
                'close': kline['close'],
                'volume': kline['volume']
            })
        
        # 生成策略信号
        signals = self._generate_strategy_signals(backtest_data, strategy_type)
        
        # 为信号添加symbol字段
        for signal in signals:
            signal['symbol'] = symbol
        
        # 执行回测
        if self.backtest_engine:
            # 转换为回测引擎所需的格式
            historical_data = {symbol: backtest_data}
            
            results = self.backtest_engine.run_backtest(
                historical_data=historical_data,
                signals=signals
            )
            
            # 添加策略信息
            results['strategy'] = strategy_type
            results['interval'] = interval
            results['days'] = days
            results['symbol'] = symbol
            
            return results
        else:
            return {"error": "回测引擎不可用"}
    
    def _generate_strategy_signals(
        self,
        klines: List[Dict[str, Any]],
        strategy_type: str
    ) -> List[Dict[str, Any]]:
        """生成策略信号"""
        
        signals = []
        
        if strategy_type == 'MA_CROSS':
            # 双均线策略
            signals = self._ma_cross_strategy(klines)
        
        elif strategy_type == 'RSI':
            # RSI策略
            signals = self._rsi_strategy(klines)
        
        elif strategy_type == 'BOLLINGER':
            # 布林带策略
            signals = self._bollinger_strategy(klines)
        
        return signals
    
    def _ma_cross_strategy(
        self,
        klines: List[Dict[str, Any]],
        fast_period: int = 5,
        slow_period: int = 20
    ) -> List[Dict[str, Any]]:
        """双均线交叉策略"""
        
        closes = [k['close'] for k in klines]
        signals = []
        
        for i in range(len(closes)):
            if i < slow_period:
                continue
            
            # 计算均线
            fast_ma = np.mean(closes[i-fast_period+1:i+1])
            slow_ma = np.mean(closes[i-slow_period+1:i+1])
            
            # 前一根K线的均线
            if i > slow_period:
                prev_fast_ma = np.mean(closes[i-fast_period:i])
                prev_slow_ma = np.mean(closes[i-slow_period:i])
                
                # 金叉 - 买入信号
                if prev_fast_ma <= prev_slow_ma and fast_ma > slow_ma:
                    signals.append({
                        'timestamp': klines[i]['timestamp'],
                        'action': 'BUY',
                        'price': klines[i]['close'],
                        'reason': f'金叉 (MA{fast_period}上穿MA{slow_period})'
                    })
                
                # 死叉 - 卖出信号
                elif prev_fast_ma >= prev_slow_ma and fast_ma < slow_ma:
                    signals.append({
                        'timestamp': klines[i]['timestamp'],
                        'action': 'SELL',
                        'price': klines[i]['close'],
                        'reason': f'死叉 (MA{fast_period}下穿MA{slow_period})'
                    })
        
        logger.info(f"生成{len(signals)}个MA交叉信号")
        return signals
    
    def _rsi_strategy(
        self,
        klines: List[Dict[str, Any]],
        period: int = 14,
        overbought: float = 70,
        oversold: float = 30
    ) -> List[Dict[str, Any]]:
        """RSI策略"""
        
        closes = np.array([k['close'] for k in klines])
        signals = []
        
        # 计算RSI
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        for i in range(period, len(closes)):
            avg_gain = np.mean(gains[i-period:i])
            avg_loss = np.mean(losses[i-period:i])
            
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            # RSI超卖 - 买入
            if rsi < oversold:
                signals.append({
                    'timestamp': klines[i]['timestamp'],
                    'action': 'BUY',
                    'price': klines[i]['close'],
                    'reason': f'RSI超卖 ({rsi:.1f})'
                })
            
            # RSI超买 - 卖出
            elif rsi > overbought:
                signals.append({
                    'timestamp': klines[i]['timestamp'],
                    'action': 'SELL',
                    'price': klines[i]['close'],
                    'reason': f'RSI超买 ({rsi:.1f})'
                })
        
        logger.info(f"生成{len(signals)}个RSI信号")
        return signals
    
    def _bollinger_strategy(
        self,
        klines: List[Dict[str, Any]],
        period: int = 20,
        std_dev: float = 2.0
    ) -> List[Dict[str, Any]]:
        """布林带策略"""
        
        closes = np.array([k['close'] for k in klines])
        signals = []
        
        for i in range(period, len(closes)):
            # 计算布林带
            sma = np.mean(closes[i-period:i])
            std = np.std(closes[i-period:i])
            
            upper_band = sma + std_dev * std
            lower_band = sma - std_dev * std
            
            current_price = closes[i]
            
            # 价格触及下轨 - 买入
            if current_price <= lower_band:
                signals.append({
                    'timestamp': klines[i]['timestamp'],
                    'action': 'BUY',
                    'price': klines[i]['close'],
                    'reason': f'触及下轨 (${lower_band:.2f})'
                })
            
            # 价格触及上轨 - 卖出
            elif current_price >= upper_band:
                signals.append({
                    'timestamp': klines[i]['timestamp'],
                    'action': 'SELL',
                    'price': klines[i]['close'],
                    'reason': f'触及上轨 (${upper_band:.2f})'
                })
        
        logger.info(f"生成{len(signals)}个布林带信号")
        return signals
    
    def print_backtest_summary(self, results: Dict[str, Any]):
        """打印回测摘要"""
        
        if 'error' in results:
            print(f"\n❌ 回测失败: {results['error']}")
            return
        
        print("\n" + "="*70)
        print(f"📊 回测结果摘要 - {results.get('symbol', 'N/A')}")
        print("="*70)
        
        print(f"\n【策略信息】")
        print(f"  策略类型: {results.get('strategy', 'N/A')}")
        print(f"  K线周期: {results.get('interval', 'N/A')}")
        print(f"  回测天数: {results.get('days', 'N/A')}天")
        
        print(f"\n【收益情况】")
        perf = results.get('performance', {})
        print(f"  初始资金: ${results.get('initial_capital', 0):,.2f}")
        print(f"  最终资金: ${results.get('final_capital', 0):,.2f}")
        print(f"  总收益: ${perf.get('total_pnl', 0):,.2f}")
        print(f"  收益率: {perf.get('total_return_pct', 0):+.2f}%")
        print(f"  最大回撤: {perf.get('max_drawdown_pct', 0):.2f}%")
        
        print(f"\n【交易统计】")
        print(f"  总交易次数: {perf.get('total_trades', 0)}次")
        print(f"  盈利交易: {perf.get('winning_trades', 0)}次")
        print(f"  亏损交易: {perf.get('losing_trades', 0)}次")
        print(f"  胜率: {perf.get('win_rate', 0):.1f}%")
        
        print(f"\n【风控情况】")
        risk = results.get('risk_control', {})
        print(f"  触发止损: {risk.get('stop_loss_triggered', 0)}次")
        print(f"  触发止盈: {risk.get('take_profit_triggered', 0)}次")
        print(f"  超时平仓: {risk.get('time_limit_triggered', 0)}次")
        
        print("\n" + "="*70)


if __name__ == '__main__':
    # 测试
    async def test():
        engine = RealDataBacktestEngine()
        
        # 回测BTC的双均线策略（最近7天，1小时K线）
        results = await engine.backtest_simple_strategy(
            symbol='BTCUSDT',
            coin_id='bitcoin',
            days=7,
            interval='1h',
            strategy_type='MA_CROSS',
            initial_capital=10000.0
        )
        
        engine.print_backtest_summary(results)
        
        print("\n" + "-"*70)
        
        # 回测ETH的RSI策略
        results2 = await engine.backtest_simple_strategy(
            symbol='ETHUSDT',
            coin_id='ethereum',
            days=7,
            interval='1h',
            strategy_type='RSI',
            initial_capital=10000.0
        )
        
        engine.print_backtest_summary(results2)
    
    asyncio.run(test())
