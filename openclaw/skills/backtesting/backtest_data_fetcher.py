"""
回测数据获取器

使用pykrx获取韩股历史分钟级和日级数据
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
import pandas as pd

try:
    from pykrx import stock
    PYKRX_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ pykrx未安装，部分功能不可用")
    PYKRX_AVAILABLE = False


class BacktestDataFetcher:
    """
    回测数据获取器
    
    特点：
    - 获取韩股历史日线数据
    - 支持分钟级数据模拟（基于日线分解）
    - 数据格式统一
    """
    
    def __init__(self):
        """初始化数据获取器"""
        if not PYKRX_AVAILABLE:
            raise ImportError("请安装pykrx: pip install pykrx")
        
        logger.info("✅ BacktestDataFetcher 初始化成功")
    
    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = '1d'  # '1d' 日线, '1h' 小时线
    ) -> List[Dict[str, Any]]:
        """
        获取历史数据
        
        Args:
            symbol: 股票代码 (例如: '005930' 三星电子)
            start_date: 开始日期 (格式: 'YYYY-MM-DD')
            end_date: 结束日期 (格式: 'YYYY-MM-DD')
            interval: 数据周期 ('1d' 日线, '1h' 小时线)
        
        Returns:
            数据列表 [{timestamp, open, high, low, close, volume}, ...]
        """
        try:
            # 转换日期格式
            start = start_date.replace('-', '')
            end = end_date.replace('-', '')
            
            # 获取日线数据
            df = stock.get_market_ohlcv_by_date(start, end, symbol)
            
            if df is None or df.empty:
                logger.warning(f"⚠️ 无法获取 {symbol} 的历史数据")
                return []
            
            # 转换为标准格式
            data = []
            for date, row in df.iterrows():
                candle = {
                    'timestamp': date.strftime('%Y-%m-%d %H:%M:%S'),
                    'open': float(row['시가']) if '시가' in row else float(row.get('Open', 0)),
                    'high': float(row['고가']) if '고가' in row else float(row.get('High', 0)),
                    'low': float(row['저가']) if '저가' in row else float(row.get('Low', 0)),
                    'close': float(row['종가']) if '종가' in row else float(row.get('Close', 0)),
                    'volume': int(row['거래량']) if '거래량' in row else int(row.get('Volume', 0))
                }
                data.append(candle)
            
            # 如果需要小时线，分解日线数据（模拟）
            if interval == '1h':
                data = self._simulate_intraday_data(data, interval='1h')
            
            logger.debug(f"✅ 获取 {symbol} 历史数据: {len(data)}条记录")
            return data
        
        except Exception as e:
            logger.error(f"❌ 获取历史数据失败 {symbol}: {e}")
            return []
    
    def get_multiple_symbols(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        interval: str = '1d'
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取多个标的的历史数据
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            interval: 数据周期
        
        Returns:
            {symbol: data_list} 字典
        """
        logger.info(f"📊 获取 {len(symbols)} 个标的的历史数据")
        
        result = {}
        for symbol in symbols:
            data = self.get_historical_data(symbol, start_date, end_date, interval)
            if data:
                result[symbol] = data
        
        logger.info(f"✅ 成功获取 {len(result)}/{len(symbols)} 个标的数据")
        return result
    
    def _simulate_intraday_data(
        self,
        daily_data: List[Dict[str, Any]],
        interval: str = '1h'
    ) -> List[Dict[str, Any]]:
        """
        模拟日内数据（从日线数据分解）
        
        Args:
            daily_data: 日线数据
            interval: 目标周期 ('1h' 小时线, '30m' 30分钟线)
        
        Returns:
            模拟的日内数据
        """
        if interval not in ['1h', '30m', '15m']:
            return daily_data
        
        # 每天的交易时段配置（韩国股市: 9:00-15:30）
        trading_hours = {
            '1h': 6,  # 6个小时线
            '30m': 13,  # 13个30分钟线
            '15m': 26  # 26个15分钟线
        }
        
        periods_per_day = trading_hours.get(interval, 6)
        
        intraday_data = []
        
        for daily_candle in daily_data:
            # 提取日线数据
            date_str = daily_candle['timestamp'].split()[0]
            open_price = daily_candle['open']
            high_price = daily_candle['high']
            low_price = daily_candle['low']
            close_price = daily_candle['close']
            volume = daily_candle['volume']
            
            # 模拟日内价格波动（简化：线性插值）
            price_range = close_price - open_price
            volume_per_period = volume // periods_per_day
            
            for i in range(periods_per_day):
                # 计算时间
                base_time = datetime.strptime(date_str, '%Y-%m-%d')
                if interval == '1h':
                    period_time = base_time + timedelta(hours=9 + i)
                elif interval == '30m':
                    period_time = base_time + timedelta(minutes=9*60 + i*30)
                else:  # 15m
                    period_time = base_time + timedelta(minutes=9*60 + i*15)
                
                # 模拟价格（简化：线性变化 + 随机波动）
                progress = (i + 1) / periods_per_day
                base_price = open_price + price_range * progress
                
                # 添加小幅随机波动（±1%）
                import random
                volatility = base_price * 0.01
                period_open = base_price + random.uniform(-volatility, volatility)
                period_close = base_price + random.uniform(-volatility, volatility)
                period_high = max(period_open, period_close) + random.uniform(0, volatility)
                period_low = min(period_open, period_close) - random.uniform(0, volatility)
                
                # 确保high/low在日线范围内
                period_high = min(period_high, high_price)
                period_low = max(period_low, low_price)
                
                intraday_data.append({
                    'timestamp': period_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'open': period_open,
                    'high': period_high,
                    'low': period_low,
                    'close': period_close,
                    'volume': volume_per_period
                })
        
        return intraday_data
    
    def generate_sample_signals(
        self,
        symbols: List[str],
        historical_data: Dict[str, List[Dict[str, Any]]],
        strategy: str = 'momentum'
    ) -> List[Dict[str, Any]]:
        """
        生成示例交易信号（用于测试）
        
        Args:
            symbols: 股票代码列表
            historical_data: 历史数据
            strategy: 策略类型 ('momentum', 'mean_reversion', 'breakout')
        
        Returns:
            交易信号列表
        """
        signals = []
        
        for symbol in symbols:
            if symbol not in historical_data:
                continue
            
            data = historical_data[symbol]
            
            if strategy == 'momentum':
                # 动量策略：价格上涨3%买入，下跌2%卖出
                signals.extend(self._generate_momentum_signals(symbol, data))
            
            elif strategy == 'mean_reversion':
                # 均值回归：价格低于5日均线5%买入，高于5%卖出
                signals.extend(self._generate_mean_reversion_signals(symbol, data))
            
            elif strategy == 'breakout':
                # 突破策略：价格突破20日高点买入
                signals.extend(self._generate_breakout_signals(symbol, data))
        
        # 按时间排序
        signals.sort(key=lambda x: x['timestamp'])
        
        logger.info(f"✅ 生成 {len(signals)} 个交易信号 (策略: {strategy})")
        return signals
    
    def _generate_momentum_signals(
        self,
        symbol: str,
        data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """生成动量策略信号"""
        signals = []
        
        for i in range(1, len(data)):
            prev_close = data[i-1]['close']
            current_close = data[i]['close']
            change_pct = ((current_close - prev_close) / prev_close) * 100
            
            # 上涨3%买入
            if change_pct >= 3.0:
                signals.append({
                    'timestamp': data[i]['timestamp'],
                    'symbol': symbol,
                    'action': 'BUY',
                    'price': current_close,
                    'strategy': 'momentum'
                })
            
            # 下跌2%卖出（如果有持仓）
            elif change_pct <= -2.0:
                signals.append({
                    'timestamp': data[i]['timestamp'],
                    'symbol': symbol,
                    'action': 'SELL',
                    'price': current_close,
                    'strategy': 'momentum'
                })
        
        return signals
    
    def _generate_mean_reversion_signals(
        self,
        symbol: str,
        data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """生成均值回归策略信号"""
        signals = []
        window = 5  # 5日均线
        
        for i in range(window, len(data)):
            # 计算5日均线
            ma5 = sum(data[j]['close'] for j in range(i-window, i)) / window
            current_close = data[i]['close']
            deviation_pct = ((current_close - ma5) / ma5) * 100
            
            # 低于均线5%买入
            if deviation_pct <= -5.0:
                signals.append({
                    'timestamp': data[i]['timestamp'],
                    'symbol': symbol,
                    'action': 'BUY',
                    'price': current_close,
                    'strategy': 'mean_reversion'
                })
            
            # 高于均线5%卖出
            elif deviation_pct >= 5.0:
                signals.append({
                    'timestamp': data[i]['timestamp'],
                    'symbol': symbol,
                    'action': 'SELL',
                    'price': current_close,
                    'strategy': 'mean_reversion'
                })
        
        return signals
    
    def _generate_breakout_signals(
        self,
        symbol: str,
        data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """生成突破策略信号"""
        signals = []
        window = 20  # 20日
        
        for i in range(window, len(data)):
            # 计算20日最高价
            high_20 = max(data[j]['high'] for j in range(i-window, i))
            current_close = data[i]['close']
            
            # 突破20日高点买入
            if current_close > high_20:
                signals.append({
                    'timestamp': data[i]['timestamp'],
                    'symbol': symbol,
                    'action': 'BUY',
                    'price': current_close,
                    'strategy': 'breakout'
                })
        
        return signals
    
    def get_stock_name(self, symbol: str) -> str:
        """
        获取股票名称
        
        Args:
            symbol: 股票代码
        
        Returns:
            股票名称
        """
        try:
            # pykrx获取股票名称
            today = datetime.now().strftime('%Y%m%d')
            df = stock.get_market_ticker_name(today)
            
            if symbol in df.index:
                return df[symbol]
            
            return symbol
        
        except Exception as e:
            logger.debug(f"获取股票名称失败 {symbol}: {e}")
            return symbol
