"""
高级技术指标监控

功能：
- 资金流监控 (Money Flow Index, OBV等)
- 波动率压缩突破检测 (Bollinger Bands Squeeze)
- 成交量异常检测
- 价格动量异常
- 市场状态识别（趋势/震荡/反转）
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
from loguru import logger


class AdvancedIndicatorMonitor:
    """
    高级技术指标监控器
    
    实时计算和监控多种技术指标，识别交易机会
    """
    
    def __init__(self):
        """初始化指标监控器"""
        # 配置参数
        self.volume_anomaly_threshold = 2.5  # 成交量异常倍数
        self.volatility_compression_threshold = 0.5  # 波动率压缩阈值
        self.mfi_overbought = 80  # MFI超买阈值
        self.mfi_oversold = 20  # MFI超卖阈值
        
        # 数据缓存
        self.price_history: Dict[str, List[Dict[str, Any]]] = {}
        self.indicator_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info("✅ AdvancedIndicatorMonitor 初始化成功")
    
    def update_price_data(
        self,
        symbol: str,
        candle: Dict[str, Any]
    ):
        """
        更新价格数据
        
        Args:
            symbol: 交易对
            candle: K线数据 {timestamp, open, high, low, close, volume}
        """
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append(candle)
        
        # 限制历史长度（保留最近200根K线）
        if len(self.price_history[symbol]) > 200:
            self.price_history[symbol] = self.price_history[symbol][-200:]
    
    def analyze_all_indicators(self, symbol: str) -> Dict[str, Any]:
        """
        分析所有指标
        
        Args:
            symbol: 交易对
        
        Returns:
            所有指标的分析结果
        """
        if symbol not in self.price_history or len(self.price_history[symbol]) < 20:
            return {"error": "数据不足，需要至少20根K线"}
        
        data = self.price_history[symbol]
        df = pd.DataFrame(data)
        
        try:
            # 1. 资金流指标
            money_flow = self._calculate_money_flow(df)
            
            # 2. 波动率指标
            volatility = self._calculate_volatility_indicators(df)
            
            # 3. 成交量指标
            volume = self._calculate_volume_indicators(df)
            
            # 4. 动量指标
            momentum = self._calculate_momentum_indicators(df)
            
            # 5. 趋势指标
            trend = self._calculate_trend_indicators(df)
            
            # 6. 综合市场状态
            market_state = self._identify_market_state(df, volatility, volume, momentum)
            
            # 7. 交易信号
            signals = self._generate_trading_signals(
                money_flow, volatility, volume, momentum, trend, market_state
            )
            
            analysis = {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'money_flow': money_flow,
                'volatility': volatility,
                'volume': volume,
                'momentum': momentum,
                'trend': trend,
                'market_state': market_state,
                'signals': signals
            }
            
            # 缓存结果
            self.indicator_cache[symbol] = analysis
            
            return analysis
        
        except Exception as e:
            logger.error(f"指标分析失败 {symbol}: {e}")
            return {"error": str(e)}
    
    def _calculate_money_flow(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        计算资金流指标
        
        - MFI (Money Flow Index)
        - OBV (On-Balance Volume)
        - CMF (Chaikin Money Flow)
        """
        # Typical Price
        df['tp'] = (df['high'] + df['low'] + df['close']) / 3
        
        # Raw Money Flow
        df['rmf'] = df['tp'] * df['volume']
        
        # Money Flow Ratio (14期)
        period = min(14, len(df))
        df['mf_sign'] = np.where(df['tp'] > df['tp'].shift(1), 1, -1)
        
        positive_mf = []
        negative_mf = []
        
        for i in range(len(df)):
            mf = df.iloc[i]['rmf']
            sign = df.iloc[i]['mf_sign']
            
            if sign > 0:
                positive_mf.append(mf)
                negative_mf.append(0)
            else:
                positive_mf.append(0)
                negative_mf.append(mf)
        
        df['positive_mf'] = positive_mf
        df['negative_mf'] = negative_mf
        
        # MFI计算
        if len(df) >= period:
            pos_sum = df['positive_mf'].rolling(period).sum().iloc[-1]
            neg_sum = df['negative_mf'].rolling(period).sum().iloc[-1]
            
            if neg_sum == 0:
                mfi = 100
            else:
                mfr = pos_sum / neg_sum
                mfi = 100 - (100 / (1 + mfr))
        else:
            mfi = 50
        
        # OBV计算
        obv = df.apply(
            lambda row: row['volume'] if row['close'] > row['open'] else -row['volume'],
            axis=1
        ).cumsum().iloc[-1]
        
        # CMF计算 (21期)
        cmf_period = min(21, len(df))
        if len(df) >= cmf_period:
            df['mf_multiplier'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
            df['mf_volume'] = df['mf_multiplier'] * df['volume']
            
            cmf = df['mf_volume'].rolling(cmf_period).sum().iloc[-1] / df['volume'].rolling(cmf_period).sum().iloc[-1]
        else:
            cmf = 0
        
        # 判断资金流状态
        if mfi > self.mfi_overbought:
            mfi_signal = 'OVERBOUGHT'
        elif mfi < self.mfi_oversold:
            mfi_signal = 'OVERSOLD'
        else:
            mfi_signal = 'NEUTRAL'
        
        obv_trend = 'BULLISH' if obv > 0 else 'BEARISH'
        cmf_signal = 'BULLISH' if cmf > 0.1 else ('BEARISH' if cmf < -0.1 else 'NEUTRAL')
        
        return {
            'mfi': mfi,
            'mfi_signal': mfi_signal,
            'obv': obv,
            'obv_trend': obv_trend,
            'cmf': cmf,
            'cmf_signal': cmf_signal,
            'overall_flow': 'POSITIVE' if (cmf > 0 and obv > 0) else ('NEGATIVE' if (cmf < 0 and obv < 0) else 'MIXED')
        }
    
    def _calculate_volatility_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        计算波动率指标
        
        - Bollinger Bands Squeeze (波动率压缩)
        - ATR (Average True Range)
        - Historical Volatility
        """
        period = min(20, len(df))
        
        # Bollinger Bands
        df['ma20'] = df['close'].rolling(period).mean()
        df['std20'] = df['close'].rolling(period).std()
        df['bb_upper'] = df['ma20'] + 2 * df['std20']
        df['bb_lower'] = df['ma20'] - 2 * df['std20']
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['ma20']
        
        # BB Squeeze检测
        if len(df) >= period:
            current_width = df['bb_width'].iloc[-1]
            avg_width = df['bb_width'].rolling(period).mean().iloc[-1]
            
            # 波动率压缩：当前宽度 < 平均宽度 * 阈值
            is_squeezed = current_width < avg_width * self.volatility_compression_threshold
            
            # 检测突破方向
            if is_squeezed and len(df) >= 2:
                prev_close = df['close'].iloc[-2]
                curr_close = df['close'].iloc[-1]
                bb_mid = df['ma20'].iloc[-1]
                
                if curr_close > bb_mid and prev_close <= bb_mid:
                    squeeze_breakout = 'BULLISH'
                elif curr_close < bb_mid and prev_close >= bb_mid:
                    squeeze_breakout = 'BEARISH'
                else:
                    squeeze_breakout = 'PENDING'
            else:
                squeeze_breakout = 'NONE'
        else:
            is_squeezed = False
            squeeze_breakout = 'NONE'
            current_width = 0
            avg_width = 0
        
        # ATR计算
        if len(df) >= 14:
            df['tr'] = pd.concat([
                df['high'] - df['low'],
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            ], axis=1).max(axis=1)
            
            atr = df['tr'].rolling(14).mean().iloc[-1]
            atr_pct = (atr / df['close'].iloc[-1]) * 100
        else:
            atr = 0
            atr_pct = 0
        
        # Historical Volatility (20期)
        if len(df) >= 20:
            returns = np.log(df['close'] / df['close'].shift(1))
            hist_vol = returns.rolling(20).std().iloc[-1] * np.sqrt(252) * 100  # 年化波动率
        else:
            hist_vol = 0
        
        return {
            'bollinger_squeeze': {
                'is_squeezed': is_squeezed,
                'breakout_direction': squeeze_breakout,
                'bb_width': current_width,
                'avg_bb_width': avg_width,
                'compression_ratio': current_width / avg_width if avg_width > 0 else 0
            },
            'atr': atr,
            'atr_percent': atr_pct,
            'historical_volatility': hist_vol,
            'volatility_state': 'LOW' if is_squeezed else ('HIGH' if atr_pct > 5 else 'NORMAL')
        }
    
    def _calculate_volume_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        计算成交量指标
        
        - Volume异常检测
        - Volume Profile
        - Volume Trend
        """
        period = min(20, len(df))
        
        # 成交量统计
        avg_volume = df['volume'].rolling(period).mean().iloc[-1]
        current_volume = df['volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        # 异常检测
        is_anomaly = volume_ratio > self.volume_anomaly_threshold
        
        # Volume Trend (最近5期)
        if len(df) >= 5:
            recent_volumes = df['volume'].tail(5).values
            volume_trend = 'INCREASING' if np.all(np.diff(recent_volumes) > 0) else (
                'DECREASING' if np.all(np.diff(recent_volumes) < 0) else 'MIXED'
            )
        else:
            volume_trend = 'UNKNOWN'
        
        # Volume-Price Divergence
        if len(df) >= 5:
            price_change = (df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5]
            volume_change = (current_volume - df['volume'].iloc[-5]) / df['volume'].iloc[-5]
            
            # 量价背离：价格上涨但成交量下降（或反之）
            if price_change > 0.02 and volume_change < -0.2:
                divergence = 'BEARISH'
            elif price_change < -0.02 and volume_change < -0.2:
                divergence = 'BULLISH'
            else:
                divergence = 'NONE'
        else:
            divergence = 'UNKNOWN'
        
        return {
            'current_volume': current_volume,
            'avg_volume': avg_volume,
            'volume_ratio': volume_ratio,
            'is_anomaly': is_anomaly,
            'anomaly_level': 'EXTREME' if volume_ratio > 5 else ('HIGH' if is_anomaly else 'NORMAL'),
            'volume_trend': volume_trend,
            'price_volume_divergence': divergence
        }
    
    def _calculate_momentum_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        计算动量指标
        
        - RSI
        - MACD
        - ROC (Rate of Change)
        """
        # RSI (14期)
        if len(df) >= 14:
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            rsi_value = rsi.iloc[-1]
            
            if rsi_value > 70:
                rsi_signal = 'OVERBOUGHT'
            elif rsi_value < 30:
                rsi_signal = 'OVERSOLD'
            else:
                rsi_signal = 'NEUTRAL'
        else:
            rsi_value = 50
            rsi_signal = 'NEUTRAL'
        
        # MACD
        if len(df) >= 26:
            ema12 = df['close'].ewm(span=12, adjust=False).mean()
            ema26 = df['close'].ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_histogram = macd_line - signal_line
            
            macd_value = macd_line.iloc[-1]
            signal_value = signal_line.iloc[-1]
            histogram_value = macd_histogram.iloc[-1]
            
            # MACD信号
            if len(df) >= 27:
                prev_macd = macd_line.iloc[-2]
                prev_signal = signal_line.iloc[-2]
                
                if macd_value > signal_value and prev_macd <= prev_signal:
                    macd_signal = 'BULLISH_CROSS'
                elif macd_value < signal_value and prev_macd >= prev_signal:
                    macd_signal = 'BEARISH_CROSS'
                else:
                    macd_signal = 'BULLISH' if macd_value > signal_value else 'BEARISH'
            else:
                macd_signal = 'NEUTRAL'
        else:
            macd_value = 0
            signal_value = 0
            histogram_value = 0
            macd_signal = 'NEUTRAL'
        
        # ROC (10期)
        if len(df) >= 10:
            roc = ((df['close'].iloc[-1] - df['close'].iloc[-10]) / df['close'].iloc[-10]) * 100
        else:
            roc = 0
        
        return {
            'rsi': rsi_value,
            'rsi_signal': rsi_signal,
            'macd': {
                'macd_line': macd_value,
                'signal_line': signal_value,
                'histogram': histogram_value,
                'signal': macd_signal
            },
            'roc': roc,
            'momentum_strength': 'STRONG' if abs(roc) > 5 else ('MODERATE' if abs(roc) > 2 else 'WEAK')
        }
    
    def _calculate_trend_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        计算趋势指标
        
        - EMA Crossovers
        - ADX (Average Directional Index)
        - Trend Strength
        """
        # EMA (5, 10, 20, 50)
        ema_periods = [5, 10, 20, 50]
        emas = {}
        
        for period in ema_periods:
            if len(df) >= period:
                emas[f'ema{period}'] = df['close'].ewm(span=period, adjust=False).mean().iloc[-1]
        
        # EMA排列
        if len(emas) >= 3:
            ema_values = list(emas.values())
            is_bullish_alignment = all(ema_values[i] > ema_values[i+1] for i in range(len(ema_values)-1))
            is_bearish_alignment = all(ema_values[i] < ema_values[i+1] for i in range(len(ema_values)-1))
            
            if is_bullish_alignment:
                ema_alignment = 'BULLISH'
            elif is_bearish_alignment:
                ema_alignment = 'BEARISH'
            else:
                ema_alignment = 'MIXED'
        else:
            ema_alignment = 'UNKNOWN'
        
        # ADX (14期) - 简化版本
        if len(df) >= 14:
            # 计算+DI和-DI
            df['high_diff'] = df['high'].diff()
            df['low_diff'] = -df['low'].diff()
            
            df['plus_dm'] = np.where((df['high_diff'] > df['low_diff']) & (df['high_diff'] > 0), df['high_diff'], 0)
            df['minus_dm'] = np.where((df['low_diff'] > df['high_diff']) & (df['low_diff'] > 0), df['low_diff'], 0)
            
            df['tr'] = pd.concat([
                df['high'] - df['low'],
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            ], axis=1).max(axis=1)
            
            atr = df['tr'].rolling(14).mean().iloc[-1]
            plus_di = (df['plus_dm'].rolling(14).mean().iloc[-1] / atr) * 100 if atr > 0 else 0
            minus_di = (df['minus_dm'].rolling(14).mean().iloc[-1] / atr) * 100 if atr > 0 else 0
            
            dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
            
            adx = dx  # 简化：实际ADX需要对DX平滑
            
            if adx > 25:
                trend_strength = 'STRONG'
            elif adx > 20:
                trend_strength = 'MODERATE'
            else:
                trend_strength = 'WEAK'
        else:
            adx = 0
            plus_di = 0
            minus_di = 0
            trend_strength = 'UNKNOWN'
        
        return {
            'emas': emas,
            'ema_alignment': ema_alignment,
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'trend_strength': trend_strength,
            'trend_direction': 'BULLISH' if plus_di > minus_di else 'BEARISH'
        }
    
    def _identify_market_state(
        self,
        df: pd.DataFrame,
        volatility: Dict[str, Any],
        volume: Dict[str, Any],
        momentum: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        识别市场状态
        
        - TRENDING (趋势)
        - RANGING (震荡)
        - VOLATILE (高波动)
        - BREAKOUT (突破)
        """
        states = []
        
        # 1. 波动率压缩 + 突破 = BREAKOUT
        if volatility['bollinger_squeeze']['is_squeezed']:
            breakout = volatility['bollinger_squeeze']['breakout_direction']
            if breakout != 'NONE' and breakout != 'PENDING':
                states.append('BREAKOUT')
        
        # 2. 成交量异常 = VOLATILE / BREAKOUT
        if volume['is_anomaly']:
            states.append('VOLATILE')
        
        # 3. 动量强 = TRENDING
        if momentum['momentum_strength'] in ['STRONG', 'MODERATE']:
            states.append('TRENDING')
        
        # 4. 低波动 + 低成交量 = RANGING
        if volatility['volatility_state'] == 'LOW' and not volume['is_anomaly']:
            states.append('RANGING')
        
        # 综合判断
        if 'BREAKOUT' in states:
            primary_state = 'BREAKOUT'
        elif 'TRENDING' in states and 'VOLATILE' not in states:
            primary_state = 'TRENDING'
        elif 'RANGING' in states:
            primary_state = 'RANGING'
        elif 'VOLATILE' in states:
            primary_state = 'VOLATILE'
        else:
            primary_state = 'UNCERTAIN'
        
        return {
            'primary_state': primary_state,
            'substates': states,
            'confidence': len(states) / 4  # 最多4个状态
        }
    
    def _generate_trading_signals(
        self,
        money_flow: Dict[str, Any],
        volatility: Dict[str, Any],
        volume: Dict[str, Any],
        momentum: Dict[str, Any],
        trend: Dict[str, Any],
        market_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成综合交易信号"""
        buy_signals = []
        sell_signals = []
        signal_strengths = []
        
        # 1. 资金流信号
        if money_flow['overall_flow'] == 'POSITIVE':
            buy_signals.append('资金流入')
            signal_strengths.append(0.7)
        elif money_flow['overall_flow'] == 'NEGATIVE':
            sell_signals.append('资金流出')
            signal_strengths.append(0.7)
        
        # 2. 波动率压缩突破
        breakout = volatility['bollinger_squeeze']['breakout_direction']
        if breakout == 'BULLISH':
            buy_signals.append('波动率突破向上')
            signal_strengths.append(0.9)
        elif breakout == 'BEARISH':
            sell_signals.append('波动率突破向下')
            signal_strengths.append(0.9)
        
        # 3. 成交量异常
        if volume['is_anomaly']:
            if volume['price_volume_divergence'] == 'BULLISH':
                buy_signals.append('量价背离（看涨）')
                signal_strengths.append(0.6)
            elif volume['price_volume_divergence'] == 'BEARISH':
                sell_signals.append('量价背离（看跌）')
                signal_strengths.append(0.6)
        
        # 4. 动量信号
        if momentum['macd']['signal'] == 'BULLISH_CROSS':
            buy_signals.append('MACD金叉')
            signal_strengths.append(0.8)
        elif momentum['macd']['signal'] == 'BEARISH_CROSS':
            sell_signals.append('MACD死叉')
            signal_strengths.append(0.8)
        
        if momentum['rsi_signal'] == 'OVERSOLD':
            buy_signals.append('RSI超卖')
            signal_strengths.append(0.7)
        elif momentum['rsi_signal'] == 'OVERBOUGHT':
            sell_signals.append('RSI超买')
            signal_strengths.append(0.7)
        
        # 5. 趋势信号
        if trend['ema_alignment'] == 'BULLISH' and trend['trend_strength'] in ['STRONG', 'MODERATE']:
            buy_signals.append('多头排列')
            signal_strengths.append(0.8)
        elif trend['ema_alignment'] == 'BEARISH' and trend['trend_strength'] in ['STRONG', 'MODERATE']:
            sell_signals.append('空头排列')
            signal_strengths.append(0.8)
        
        # 综合判断
        buy_count = len(buy_signals)
        sell_count = len(sell_signals)
        
        if buy_count > sell_count + 1:
            action = 'BUY'
            confidence = np.mean(signal_strengths[:buy_count]) if signal_strengths else 0
        elif sell_count > buy_count + 1:
            action = 'SELL'
            confidence = np.mean(signal_strengths[buy_count:]) if signal_strengths else 0
        else:
            action = 'HOLD'
            confidence = 0
        
        return {
            'action': action,
            'confidence': confidence,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'signal_count': {
                'buy': buy_count,
                'sell': sell_count
            },
            'market_condition': market_state['primary_state']
        }
    
    def get_summary_report(self, symbol: str) -> str:
        """生成摘要报告"""
        if symbol not in self.indicator_cache:
            return f"❌ 暂无 {symbol} 的指标数据"
        
        analysis = self.indicator_cache[symbol]
        
        report = f"\n=== {symbol} 技术指标分析 ===\n\n"
        
        # 市场状态
        market_state = analysis['market_state']
        report += f"【市场状态】{market_state['primary_state']}\n"
        
        # 资金流
        mf = analysis['money_flow']
        report += f"【资金流】{mf['overall_flow']} (MFI: {mf['mfi']:.1f}, CMF: {mf['cmf']:+.3f})\n"
        
        # 波动率
        vol = analysis['volatility']
        squeeze = vol['bollinger_squeeze']
        if squeeze['is_squeezed']:
            report += f"【波动率】压缩中 ({squeeze['breakout_direction']})\n"
        else:
            report += f"【波动率】{vol['volatility_state']} (ATR: {vol['atr_percent']:.2f}%)\n"
        
        # 成交量
        volume = analysis['volume']
        if volume['is_anomaly']:
            report += f"【成交量】异常 ({volume['volume_ratio']:.1f}倍平均量)\n"
        else:
            report += f"【成交量】正常 ({volume['volume_trend']})\n"
        
        # 动量
        momentum = analysis['momentum']
        report += f"【动量】RSI: {momentum['rsi']:.1f} ({momentum['rsi_signal']})\n"
        report += f"       MACD: {momentum['macd']['signal']}\n"
        
        # 趋势
        trend = analysis['trend']
        report += f"【趋势】{trend['ema_alignment']} ({trend['trend_strength']})\n"
        
        # 交易信号
        signals = analysis['signals']
        report += f"\n【交易建议】{signals['action']} (置信度: {signals['confidence']:.0%})\n"
        
        if signals['buy_signals']:
            report += f"看涨因素: {', '.join(signals['buy_signals'])}\n"
        if signals['sell_signals']:
            report += f"看跌因素: {', '.join(signals['sell_signals'])}\n"
        
        return report


if __name__ == '__main__':
    # 测试
    monitor = AdvancedIndicatorMonitor()
    
    # 模拟价格数据
    import random
    base_price = 50000
    
    for i in range(50):
        price = base_price + random.randint(-1000, 1000)
        candle = {
            'timestamp': f'2024-02-{i+1:02d}',
            'open': price,
            'high': price + random.randint(0, 500),
            'low': price - random.randint(0, 500),
            'close': price + random.randint(-200, 200),
            'volume': 1000 + random.randint(0, 500)
        }
        monitor.update_price_data('BTC-USDT', candle)
    
    analysis = monitor.analyze_all_indicators('BTC-USDT')
    print(monitor.get_summary_report('BTC-USDT'))
