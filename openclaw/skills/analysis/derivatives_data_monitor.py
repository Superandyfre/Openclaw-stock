"""
衍生品数据监控

功能：
- 资金费率监控
- 未平仓量(OI)变化追踪
- 多空比分析
- 清算数据监控
- 期现价差
- 合约溢价/折价
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from loguru import logger


class DerivativesDataMonitor:
    """
    衍生品数据监控器
    
    专注于期货/永续合约市场的特殊指标
    """
    
    def __init__(self):
        """初始化衍生品监控器"""
        # 配置参数
        self.high_funding_rate = 0.01  # 1% 视为高资金费率
        self.extreme_funding_rate = 0.05  # 5% 视为极端资金费率
        self.oi_change_threshold = 0.15  # 15% OI变化视为显著
        self.liquidation_threshold = 10000000  # 1000万美元清算视为重要
        
        # 数据缓存
        self.funding_history: Dict[str, List[Dict[str, Any]]] = {}
        self.oi_history: Dict[str, List[Dict[str, Any]]] = {}
        self.long_short_history: Dict[str, List[Dict[str, Any]]] = {}
        self.liquidation_events: List[Dict[str, Any]] = []
        
        logger.info("✅ DerivativesDataMonitor 初始化成功")
    
    def analyze_funding_rate(
        self,
        symbol: str,
        current_rate: float,
        next_funding_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分析资金费率
        
        Args:
            symbol: 交易对
            current_rate: 当前资金费率（如 0.0001 = 0.01%）
            next_funding_time: 下次资金费时间
        
        Returns:
            资金费率分析
        """
        # 记录历史
        if symbol not in self.funding_history:
            self.funding_history[symbol] = []
        
        self.funding_history[symbol].append({
            'timestamp': datetime.now().isoformat(),
            'rate': current_rate
        })
        
        # 限制历史长度
        if len(self.funding_history[symbol]) > 100:
            self.funding_history[symbol] = self.funding_history[symbol][-100:]
        
        # 计算统计指标
        history = self.funding_history[symbol]
        rates = [h['rate'] for h in history]
        
        avg_rate = np.mean(rates)
        std_rate = np.std(rates) if len(rates) > 1 else 0
        
        # 资金费率状态判断
        if current_rate > self.extreme_funding_rate:
            state = 'EXTREMELY_POSITIVE'
            signal = 'STRONG_SELL'  # 极高正费率，市场过度看多，可能回调
        elif current_rate > self.high_funding_rate:
            state = 'HIGH_POSITIVE'
            signal = 'CAUTION_SELL'
        elif current_rate < -self.extreme_funding_rate:
            state = 'EXTREMELY_NEGATIVE'
            signal = 'STRONG_BUY'  # 极低负费率，市场过度看空，可能反弹
        elif current_rate < -self.high_funding_rate:
            state = 'HIGH_NEGATIVE'
            signal = 'CAUTION_BUY'
        else:
            state = 'NEUTRAL'
            signal = 'NEUTRAL'
        
        # 趋势判断
        if len(rates) >= 5:
            recent_rates = rates[-5:]
            if all(recent_rates[i] < recent_rates[i+1] for i in range(4)):
                trend = 'RISING'
            elif all(recent_rates[i] > recent_rates[i+1] for i in range(4)):
                trend = 'FALLING'
            else:
                trend = 'STABLE'
        else:
            trend = 'UNKNOWN'
        
        # 年化收益率（假设每8小时结算一次）
        annualized_rate = current_rate * 3 * 365 * 100  # 转换为百分比
        
        return {
            'symbol': symbol,
            'current_rate': current_rate,
            'current_rate_pct': current_rate * 100,
            'annualized_rate_pct': annualized_rate,
            'avg_rate': avg_rate,
            'std_rate': std_rate,
            'state': state,
            'signal': signal,
            'trend': trend,
            'next_funding_time': next_funding_time,
            'interpretation': self._interpret_funding_rate(current_rate, state, trend)
        }
    
    def analyze_open_interest(
        self,
        symbol: str,
        current_oi: float,
        price_change_pct: float = 0
    ) -> Dict[str, Any]:
        """
        分析未平仓量
        
        Args:
            symbol: 交易对
            current_oi: 当前未平仓量（USD或合约数）
            price_change_pct: 价格变化百分比
        
        Returns:
            未平仓量分析
        """
        # 记录历史
        if symbol not in self.oi_history:
            self.oi_history[symbol] = []
        
        self.oi_history[symbol].append({
            'timestamp': datetime.now().isoformat(),
            'oi': current_oi,
            'price_change': price_change_pct
        })
        
        # 限制历史长度
        if len(self.oi_history[symbol]) > 100:
            self.oi_history[symbol] = self.oi_history[symbol][-100:]
        
        history = self.oi_history[symbol]
        
        # OI变化分析
        if len(history) >= 2:
            prev_oi = history[-2]['oi']
            oi_change = current_oi - prev_oi
            oi_change_pct = (oi_change / prev_oi * 100) if prev_oi > 0 else 0
            
            # OI变化显著性
            is_significant = abs(oi_change_pct) > self.oi_change_threshold * 100
        else:
            oi_change = 0
            oi_change_pct = 0
            is_significant = False
        
        # OI趋势
        if len(history) >= 5:
            oi_values = [h['oi'] for h in history[-5:]]
            if all(oi_values[i] < oi_values[i+1] for i in range(4)):
                oi_trend = 'INCREASING'
            elif all(oi_values[i] > oi_values[i+1] for i in range(4)):
                oi_trend = 'DECREASING'
            else:
                oi_trend = 'STABLE'
        else:
            oi_trend = 'UNKNOWN'
        
        # 价格-OI关系分析
        signal = self._analyze_price_oi_relationship(price_change_pct, oi_change_pct)
        
        return {
            'symbol': symbol,
            'current_oi': current_oi,
            'oi_change': oi_change,
            'oi_change_pct': oi_change_pct,
            'is_significant': is_significant,
            'oi_trend': oi_trend,
            'signal': signal,
            'interpretation': self._interpret_oi_change(price_change_pct, oi_change_pct, oi_trend)
        }
    
    def analyze_long_short_ratio(
        self,
        symbol: str,
        long_ratio: float,
        short_ratio: float,
        data_source: str = 'accounts'
    ) -> Dict[str, Any]:
        """
        分析多空比
        
        Args:
            symbol: 交易对
            long_ratio: 多头比例 (0-1)
            short_ratio: 空头比例 (0-1)
            data_source: 数据来源 ('accounts' 账户数, 'positions' 持仓量, 'top_traders' 大户)
        
        Returns:
            多空比分析
        """
        # 记录历史
        if symbol not in self.long_short_history:
            self.long_short_history[symbol] = {}
        
        if data_source not in self.long_short_history[symbol]:
            self.long_short_history[symbol][data_source] = []
        
        self.long_short_history[symbol][data_source].append({
            'timestamp': datetime.now().isoformat(),
            'long_ratio': long_ratio,
            'short_ratio': short_ratio
        })
        
        # 限制历史长度
        if len(self.long_short_history[symbol][data_source]) > 100:
            self.long_short_history[symbol][data_source] = \
                self.long_short_history[symbol][data_source][-100:]
        
        # 计算多空比值
        ls_ratio = long_ratio / short_ratio if short_ratio > 0 else float('inf')
        
        # 市场情绪判断
        if ls_ratio > 3:
            sentiment = 'EXTREMELY_BULLISH'
            signal = 'CAUTION_SELL'  # 过度看多，反向指标
        elif ls_ratio > 1.5:
            sentiment = 'BULLISH'
            signal = 'NEUTRAL'
        elif ls_ratio < 0.33:
            sentiment = 'EXTREMELY_BEARISH'
            signal = 'CAUTION_BUY'  # 过度看空，反向指标
        elif ls_ratio < 0.67:
            sentiment = 'BEARISH'
            signal = 'NEUTRAL'
        else:
            sentiment = 'NEUTRAL'
            signal = 'NEUTRAL'
        
        # 趋势分析
        history = self.long_short_history[symbol][data_source]
        if len(history) >= 5:
            ratios = [h['long_ratio'] / h['short_ratio'] if h['short_ratio'] > 0 else 1 
                     for h in history[-5:]]
            
            if all(ratios[i] < ratios[i+1] for i in range(4)):
                trend = 'BULLISH_INCREASING'
            elif all(ratios[i] > ratios[i+1] for i in range(4)):
                trend = 'BEARISH_INCREASING'
            else:
                trend = 'STABLE'
        else:
            trend = 'UNKNOWN'
        
        return {
            'symbol': symbol,
            'data_source': data_source,
            'long_ratio': long_ratio,
            'short_ratio': short_ratio,
            'ls_ratio': ls_ratio,
            'sentiment': sentiment,
            'signal': signal,
            'trend': trend,
            'interpretation': self._interpret_long_short_ratio(ls_ratio, sentiment, data_source)
        }
    
    def monitor_liquidations(
        self,
        symbol: str,
        liquidation_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        监控清算数据
        
        Args:
            symbol: 交易对
            liquidation_data: 清算列表 [{side: 'long'/'short', amount: 金额, price: 价格, timestamp}, ...]
        
        Returns:
            清算分析
        """
        # 记录清算事件
        for liq in liquidation_data:
            event = {
                'symbol': symbol,
                'side': liq['side'],
                'amount': liq['amount'],
                'price': liq.get('price', 0),
                'timestamp': liq.get('timestamp', datetime.now().isoformat())
            }
            self.liquidation_events.append(event)
        
        # 限制历史长度
        if len(self.liquidation_events) > 1000:
            self.liquidation_events = self.liquidation_events[-1000:]
        
        # 分析最近的清算
        recent_liq = [e for e in self.liquidation_events 
                     if e['symbol'] == symbol and
                     datetime.fromisoformat(e['timestamp']) > datetime.now() - timedelta(hours=1)]
        
        if not recent_liq:
            return {
                'symbol': symbol,
                'total_liquidations': 0,
                'signal': 'NO_DATA'
            }
        
        # 统计
        long_liq = [l for l in recent_liq if l['side'] == 'long']
        short_liq = [l for l in recent_liq if l['side'] == 'short']
        
        long_liq_amount = sum(l['amount'] for l in long_liq)
        short_liq_amount = sum(l['amount'] for l in short_liq)
        total_liq_amount = long_liq_amount + short_liq_amount
        
        # 清算方向判断
        if long_liq_amount > short_liq_amount * 2:
            liquidation_pressure = 'BEARISH'  # 多头被清算，下跌压力
            signal = 'SELL'
        elif short_liq_amount > long_liq_amount * 2:
            liquidation_pressure = 'BULLISH'  # 空头被清算，上涨压力
            signal = 'BUY'
        else:
            liquidation_pressure = 'BALANCED'
            signal = 'NEUTRAL'
        
        # 清算瀑布检测（连续大量清算）
        large_liq = [l for l in recent_liq if l['amount'] > self.liquidation_threshold]
        is_cascade = len(large_liq) >= 3
        
        return {
            'symbol': symbol,
            'time_window': '1h',
            'total_liquidations': len(recent_liq),
            'long_liquidations': len(long_liq),
            'short_liquidations': len(short_liq),
            'long_liq_amount': long_liq_amount,
            'short_liq_amount': short_liq_amount,
            'total_liq_amount': total_liq_amount,
            'liquidation_pressure': liquidation_pressure,
            'signal': signal,
            'is_cascade': is_cascade,
            'severity': 'EXTREME' if is_cascade else ('HIGH' if total_liq_amount > self.liquidation_threshold * 5 else 'NORMAL')
        }
    
    def analyze_basis(
        self,
        symbol: str,
        spot_price: float,
        futures_price: float,
        time_to_expiry_days: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        分析期现价差
        
        Args:
            symbol: 交易对
            spot_price: 现货价格
            futures_price: 期货价格
            time_to_expiry_days: 距离到期天数（永续合约为None）
        
        Returns:
            价差分析
        """
        # 绝对价差
        basis = futures_price - spot_price
        
        # 相对价差（百分比）
        basis_pct = (basis / spot_price) * 100 if spot_price > 0 else 0
        
        # 年化价差（仅适用于到期合约）
        if time_to_expiry_days and time_to_expiry_days > 0:
            annualized_basis = (basis_pct / time_to_expiry_days) * 365
        else:
            annualized_basis = None
        
        # 溢价/折价判断
        if basis_pct > 0.5:
            state = 'PREMIUM'  # 期货溢价（Contango）
            interpretation = '期货溢价，市场看涨情绪较强'
        elif basis_pct < -0.5:
            state = 'DISCOUNT'  # 期货折价（Backwardation）
            interpretation = '期货折价，市场看跌或即期需求强'
        else:
            state = 'FAIR'
            interpretation = '期货价格合理'
        
        # 套利机会判断
        if annualized_basis:
            if annualized_basis > 10:
                arbitrage_opportunity = 'LONG_SPOT_SHORT_FUTURES'  # 做多现货，做空期货
            elif annualized_basis < -10:
                arbitrage_opportunity = 'SHORT_SPOT_LONG_FUTURES'  # 做空现货，做多期货
            else:
                arbitrage_opportunity = 'NONE'
        else:
            arbitrage_opportunity = 'N/A'
        
        return {
            'symbol': symbol,
            'spot_price': spot_price,
            'futures_price': futures_price,
            'basis': basis,
            'basis_pct': basis_pct,
            'annualized_basis': annualized_basis,
            'state': state,
            'interpretation': interpretation,
            'arbitrage_opportunity': arbitrage_opportunity,
            'time_to_expiry_days': time_to_expiry_days
        }
    
    def _interpret_funding_rate(self, rate: float, state: str, trend: str) -> str:
        """解释资金费率"""
        interpretations = {
            'EXTREMELY_POSITIVE': '资金费率极高，市场过度看多，当心回调风险',
            'HIGH_POSITIVE': '资金费率偏高，多头需支付费用，市场偏多',
            'EXTREMELY_NEGATIVE': '资金费率极低，市场过度看空，可能出现反弹',
            'HIGH_NEGATIVE': '资金费率偏低，空头需支付费用，市场偏空',
            'NEUTRAL': '资金费率正常，市场处于平衡状态'
        }
        
        base = interpretations.get(state, '')
        
        if trend == 'RISING':
            base += '，且费率持续上升'
        elif trend == 'FALLING':
            base += '，且费率持续下降'
        
        return base
    
    def _analyze_price_oi_relationship(
        self,
        price_change_pct: float,
        oi_change_pct: float
    ) -> str:
        """分析价格与OI的关系"""
        # 价格上涨 + OI上升 = 新多头进场（看涨）
        if price_change_pct > 1 and oi_change_pct > self.oi_change_threshold * 100:
            return 'BULLISH'
        
        # 价格上涨 + OI下降 = 空头平仓（看涨延续）
        elif price_change_pct > 1 and oi_change_pct < -self.oi_change_threshold * 100:
            return 'BULLISH_COVERING'
        
        # 价格下跌 + OI上升 = 新空头进场（看跌）
        elif price_change_pct < -1 and oi_change_pct > self.oi_change_threshold * 100:
            return 'BEARISH'
        
        # 价格下跌 + OI下降 = 多头平仓（看跌延续）
        elif price_change_pct < -1 and oi_change_pct < -self.oi_change_threshold * 100:
            return 'BEARISH_COVERING'
        
        else:
            return 'NEUTRAL'
    
    def _interpret_oi_change(
        self,
        price_change_pct: float,
        oi_change_pct: float,
        trend: str
    ) -> str:
        """解释OI变化"""
        signal = self._analyze_price_oi_relationship(price_change_pct, oi_change_pct)
        
        interpretations = {
            'BULLISH': '价格上涨且未平仓量增加，新多头入场，看涨信号',
            'BULLISH_COVERING': '价格上涨但未平仓量减少，空头被迫平仓，看涨延续',
            'BEARISH': '价格下跌且未平仓量增加，新空头入场，看跌信号',
            'BEARISH_COVERING': '价格下跌但未平仓量减少，多头被迫平仓，看跌延续',
            'NEUTRAL': '未平仓量变化不显著或与价格关系不明确'
        }
        
        return interpretations.get(signal, '')
    
    def _interpret_long_short_ratio(
        self,
        ls_ratio: float,
        sentiment: str,
        data_source: str
    ) -> str:
        """解释多空比"""
        source_desc = {
            'accounts': '账户数',
            'positions': '持仓量',
            'top_traders': '大户持仓'
        }.get(data_source, data_source)
        
        if sentiment == 'EXTREMELY_BULLISH':
            return f'{source_desc}显示市场过度看多（{ls_ratio:.2f}:1），可能出现回调（反向指标）'
        elif sentiment == 'BULLISH':
            return f'{source_desc}显示市场偏多（{ls_ratio:.2f}:1），看涨情绪占优'
        elif sentiment == 'EXTREMELY_BEARISH':
            return f'{source_desc}显示市场过度看空（1:{1/ls_ratio:.2f}），可能出现反弹（反向指标）'
        elif sentiment == 'BEARISH':
            return f'{source_desc}显示市场偏空（1:{1/ls_ratio:.2f}），看跌情绪占优'
        else:
            return f'{source_desc}显示市场多空平衡（{ls_ratio:.2f}:1）'
    
    def get_comprehensive_analysis(
        self,
        symbol: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        获取综合衍生品分析
        
        Args:
            symbol: 交易对
            **kwargs: 包含 funding_rate, open_interest, long_ratio, short_ratio, spot_price, futures_price 等
        
        Returns:
            综合分析结果
        """
        analysis = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat()
        }
        
        # 资金费率
        if 'funding_rate' in kwargs:
            analysis['funding_rate'] = self.analyze_funding_rate(
                symbol, kwargs['funding_rate'], kwargs.get('next_funding_time')
            )
        
        # 未平仓量
        if 'open_interest' in kwargs:
            analysis['open_interest'] = self.analyze_open_interest(
                symbol, kwargs['open_interest'], kwargs.get('price_change_pct', 0)
            )
        
        # 多空比
        if 'long_ratio' in kwargs and 'short_ratio' in kwargs:
            analysis['long_short_ratio'] = self.analyze_long_short_ratio(
                symbol, kwargs['long_ratio'], kwargs['short_ratio'], 
                kwargs.get('data_source', 'accounts')
            )
        
        # 期现价差
        if 'spot_price' in kwargs and 'futures_price' in kwargs:
            analysis['basis'] = self.analyze_basis(
                symbol, kwargs['spot_price'], kwargs['futures_price'],
                kwargs.get('time_to_expiry_days')
            )
        
        # 生成综合信号
        signals = []
        
        if 'funding_rate' in analysis:
            fr_signal = analysis['funding_rate']['signal']
            if fr_signal != 'NEUTRAL':
                signals.append(fr_signal)
        
        if 'open_interest' in analysis:
            oi_signal = analysis['open_interest']['signal']
            if oi_signal != 'NEUTRAL':
                signals.append(oi_signal)
        
        # 综合判断
        buy_signals = len([s for s in signals if 'BUY' in s])
        sell_signals = len([s for s in signals if 'SELL' in s])
        
        if buy_signals > sell_signals:
            overall_signal = 'BUY'
        elif sell_signals > buy_signals:
            overall_signal = 'SELL'
        else:
            overall_signal = 'NEUTRAL'
        
        analysis['overall_signal'] = overall_signal
        analysis['signal_breakdown'] = {
            'buy_signals': buy_signals,
            'sell_signals': sell_signals
        }
        
        return analysis


if __name__ == '__main__':
    # 测试
    monitor = DerivativesDataMonitor()
    
    # 测试资金费率
    funding_analysis = monitor.analyze_funding_rate('BTC-PERP', 0.0005)
    print("\n=== 资金费率分析 ===")
    print(f"当前费率: {funding_analysis['current_rate_pct']:.4f}%")
    print(f"状态: {funding_analysis['state']}")
    print(f"信号: {funding_analysis['signal']}")
    print(f"解释: {funding_analysis['interpretation']}")
    
    # 测试未平仓量
    oi_analysis = monitor.analyze_open_interest('BTC-PERP', 1000000000, price_change_pct=2.5)
    print("\n=== 未平仓量分析 ===")
    print(f"信号: {oi_analysis['signal']}")
    print(f"解释: {oi_analysis['interpretation']}")
    
    # 测试多空比
    ls_analysis = monitor.analyze_long_short_ratio('BTC-PERP', 0.65, 0.35)
    print("\n=== 多空比分析 ===")
    print(f"多空比: {ls_analysis['ls_ratio']:.2f}:1")
    print(f"情绪: {ls_analysis['sentiment']}")
    print(f"解释: {ls_analysis['interpretation']}")
