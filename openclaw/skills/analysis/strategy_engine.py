"""
Strategy engine for trading signals
Supports both long-term and short-term trading strategies
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger


class StrategyEngine:
    """Manages multiple trading strategies"""
    
    def __init__(self, strategies_config: List[Dict[str, Any]], trading_mode: str = "short_term"):
        """
        Initialize strategy engine
        
        Args:
            strategies_config: List of strategy configurations
            trading_mode: Trading mode - "short_term" or "long_term"
        """
        self.trading_mode = trading_mode
        self.strategies = {
            s['name']: s for s in strategies_config if s.get('enabled', True)
        }
        self.signal_history: List[Dict[str, Any]] = []
        
        logger.info(f"Strategy Engine initialized in {trading_mode} mode with {len(self.strategies)} strategies")
        for name in self.strategies.keys():
            logger.info(f"  - {name} (weight: {self.strategies[name].get('weight', 1.0)})")
    
    def generate_signals(
        self,
        symbol: str,
        price_data: Dict[str, Any],
        technical_indicators: Dict[str, Any],
        sentiment: Dict[str, Any],
        minute_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate trading signals from all strategies
        
        Args:
            symbol: Asset symbol
            price_data: Current price data
            technical_indicators: Technical analysis results
            sentiment: Sentiment analysis results
            minute_data: Minute-level data for short-term strategies
        
        Returns:
            List of trading signals
        """
        signals = []
        
        # Short-term strategies
        if self.trading_mode == "short_term":
            # Intraday Breakout Strategy
            if 'Intraday Breakout' in self.strategies:
                signal = self._intraday_breakout_strategy(
                    symbol,
                    price_data,
                    technical_indicators,
                    self.strategies['Intraday Breakout']['parameters'],
                    minute_data
                )
                if signal:
                    signal['weight'] = self.strategies['Intraday Breakout'].get('weight', 1.0)
                    signals.append(signal)
            
            # Minute MA Cross Strategy
            if 'Minute MA Cross' in self.strategies:
                signal = self._minute_ma_cross_strategy(
                    symbol,
                    price_data,
                    technical_indicators,
                    self.strategies['Minute MA Cross']['parameters']
                )
                if signal:
                    signal['weight'] = self.strategies['Minute MA Cross'].get('weight', 1.0)
                    signals.append(signal)
            
            # Momentum Reversal Strategy
            if 'Momentum Reversal' in self.strategies:
                signal = self._momentum_reversal_strategy(
                    symbol,
                    price_data,
                    technical_indicators,
                    self.strategies['Momentum Reversal']['parameters']
                )
                if signal:
                    signal['weight'] = self.strategies['Momentum Reversal'].get('weight', 1.0)
                    signals.append(signal)
            
            # Order Flow Anomaly Strategy
            if 'Order Flow Anomaly' in self.strategies:
                signal = self._order_flow_anomaly_strategy(
                    symbol,
                    price_data,
                    technical_indicators,
                    self.strategies['Order Flow Anomaly']['parameters'],
                    minute_data
                )
                if signal:
                    signal['weight'] = self.strategies['Order Flow Anomaly'].get('weight', 1.0)
                    signals.append(signal)
            
            # News Momentum Strategy
            if 'News Momentum' in self.strategies:
                signal = self._news_momentum_strategy(
                    symbol,
                    price_data,
                    technical_indicators,
                    sentiment,
                    self.strategies['News Momentum']['parameters']
                )
                if signal:
                    signal['weight'] = self.strategies['News Momentum'].get('weight', 1.0)
                    signals.append(signal)
        
        else:  # Long-term strategies (legacy)
            # Trend Following Strategy
            if 'Trend Following' in self.strategies:
                signal = self._trend_following_strategy(
                    symbol,
                    price_data,
                    technical_indicators,
                    self.strategies['Trend Following']['parameters']
                )
                if signal:
                    signals.append(signal)
            
            # Mean Reversion Strategy
            if 'Mean Reversion' in self.strategies:
                signal = self._mean_reversion_strategy(
                    symbol,
                    price_data,
                    technical_indicators,
                    self.strategies['Mean Reversion']['parameters']
                )
                if signal:
                    signals.append(signal)
            
            # Momentum Strategy
            if 'Momentum' in self.strategies:
                signal = self._momentum_strategy(
                    symbol,
                    price_data,
                    technical_indicators,
                    sentiment,
                    self.strategies['Momentum']['parameters']
                )
                if signal:
                    signals.append(signal)
        
        # Store signals
        for signal in signals:
            self.signal_history.append(signal)
        
        return signals
    
    # === SHORT-TERM STRATEGIES ===
    
    def _intraday_breakout_strategy(
        self,
        symbol: str,
        price_data: Dict[str, Any],
        indicators: Dict[str, Any],
        params: Dict[str, Any],
        minute_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Intraday Breakout Strategy
        
        Triggers when price breaks the day's high/low with increased volume
        """
        current_price = price_data.get('current_price', 0)
        intraday_high = price_data.get('high', 0)
        intraday_low = price_data.get('low', 0)
        volume = price_data.get('volume', 0)
        avg_volume = minute_data.get('avg_volume', volume) if minute_data else volume
        
        breakout_threshold = params.get('breakout_threshold', 0.005)
        volume_multiplier = params.get('volume_multiplier', 2.0)
        
        # Check volume confirmation
        volume_confirmed = volume > avg_volume * volume_multiplier
        
        # Upside breakout
        if intraday_high > 0 and current_price > intraday_high * (1 + breakout_threshold) and volume_confirmed:
            stop_loss = current_price * (1 - params.get('stop_loss', 0.01))
            take_profit = current_price * (1 + params.get('take_profit', 0.02))
            
            return {
                "symbol": symbol,
                "strategy": "Intraday Breakout",
                "action": "BUY",
                "price": current_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "confidence": 0.75,
                "reason": f"Upside breakout: Price ${current_price:.2f} > High ${intraday_high:.2f} with {volume/avg_volume:.1f}x volume",
                "max_hold_hours": params.get('max_hold_time_hours', 24),
                "timestamp": datetime.now().isoformat()
            }
        
        # Downside breakout (short opportunity - for now just avoid/sell)
        elif intraday_low > 0 and current_price < intraday_low * (1 - breakout_threshold) and volume_confirmed:
            return {
                "symbol": symbol,
                "strategy": "Intraday Breakout",
                "action": "SELL",
                "price": current_price,
                "confidence": 0.70,
                "reason": f"Downside breakout: Price ${current_price:.2f} < Low ${intraday_low:.2f}",
                "timestamp": datetime.now().isoformat()
            }
        
        return None
    
    def _minute_ma_cross_strategy(
        self,
        symbol: str,
        price_data: Dict[str, Any],
        indicators: Dict[str, Any],
        params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Minute MA Cross Strategy
        
        5-minute MA crosses 15-minute MA with RSI confirmation
        """
        current_price = price_data.get('current_price', 0)
        ma_5 = indicators.get('ma_5', 0)
        ma_15 = indicators.get('ma_15', 0)
        rsi = indicators.get('rsi', 50)
        
        fast_ma = params.get('fast_ma', 5)
        slow_ma = params.get('slow_ma', 15)
        rsi_threshold = params.get('rsi_threshold', 70)
        
        if ma_5 == 0 or ma_15 == 0:
            return None
        
        # Bullish cross: MA5 > MA15 and price above MA5, RSI not overbought
        if ma_5 > ma_15 and current_price > ma_5 and rsi < rsi_threshold:
            stop_loss = current_price * (1 - params.get('stop_loss', 0.015))
            take_profit = current_price * (1 + params.get('take_profit', 0.025))
            
            return {
                "symbol": symbol,
                "strategy": "Minute MA Cross",
                "action": "BUY",
                "price": current_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "confidence": 0.70,
                "reason": f"Bullish MA cross: MA{fast_ma}=${ma_5:.2f} > MA{slow_ma}=${ma_15:.2f}, RSI={rsi:.1f}",
                "max_hold_hours": params.get('max_hold_time_hours', 12),
                "timestamp": datetime.now().isoformat()
            }
        
        # Bearish cross: MA5 < MA15 or RSI overbought
        elif ma_5 < ma_15 or rsi > 80:
            return {
                "symbol": symbol,
                "strategy": "Minute MA Cross",
                "action": "SELL",
                "price": current_price,
                "confidence": 0.65,
                "reason": f"Bearish MA cross or overbought: MA{fast_ma}=${ma_5:.2f} vs MA{slow_ma}=${ma_15:.2f}, RSI={rsi:.1f}",
                "timestamp": datetime.now().isoformat()
            }
        
        return None
    
    def _momentum_reversal_strategy(
        self,
        symbol: str,
        price_data: Dict[str, Any],
        indicators: Dict[str, Any],
        params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Momentum Reversal Strategy
        
        Catches oversold bounces with volume confirmation
        """
        current_price = price_data.get('current_price', 0)
        change_pct = price_data.get('change_pct', 0)
        volume = price_data.get('volume', 0)
        rsi = indicators.get('rsi', 50)
        
        reversal_threshold = params.get('reversal_threshold', 0.03)
        rsi_oversold = params.get('rsi_oversold', 30)
        volume_surge = params.get('volume_surge', 2.5)
        
        # Get average volume (simplified - would need historical data)
        avg_volume = price_data.get('avg_volume', volume / 2)
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1
        
        # Oversold reversal opportunity
        if change_pct < -reversal_threshold * 100 and rsi < rsi_oversold and volume_ratio > volume_surge:
            stop_loss = current_price * (1 - params.get('stop_loss', 0.02))
            take_profit = current_price * (1 + params.get('take_profit', 0.015))
            
            return {
                "symbol": symbol,
                "strategy": "Momentum Reversal",
                "action": "BUY",
                "price": current_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "confidence": 0.75,
                "reason": f"Oversold reversal: {change_pct:.2f}% drop, RSI={rsi:.1f}, Volume {volume_ratio:.1f}x",
                "max_hold_hours": params.get('max_hold_time_hours', 4),
                "timestamp": datetime.now().isoformat()
            }
        
        return None
    
    def _order_flow_anomaly_strategy(
        self,
        symbol: str,
        price_data: Dict[str, Any],
        indicators: Dict[str, Any],
        params: Dict[str, Any],
        minute_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Order Flow Anomaly Strategy
        
        Detects large order flow anomalies (requires order book data)
        """
        # This strategy requires real-time order flow data
        # For now, use volume spikes as a proxy
        
        if not minute_data:
            return None
        
        large_orders = minute_data.get('large_orders', [])
        order_count = len(large_orders)
        required_count = params.get('order_count', 3)
        
        current_price = price_data.get('current_price', 0)
        
        # If we detected multiple large buy orders
        if order_count >= required_count:
            buy_orders = [o for o in large_orders if o.get('side') == 'buy']
            
            if len(buy_orders) >= required_count:
                stop_loss = current_price * (1 - params.get('stop_loss', 0.01))
                take_profit = current_price * (1 + params.get('take_profit', 0.015))
                
                return {
                    "symbol": symbol,
                    "strategy": "Order Flow Anomaly",
                    "action": "BUY",
                    "price": current_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "confidence": 0.65,
                    "reason": f"Large order flow: {len(buy_orders)} large buy orders detected",
                    "max_hold_hours": params.get('max_hold_time_hours', 2),
                    "timestamp": datetime.now().isoformat()
                }
        
        return None
    
    def _news_momentum_strategy(
        self,
        symbol: str,
        price_data: Dict[str, Any],
        indicators: Dict[str, Any],
        sentiment: Dict[str, Any],
        params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        News Momentum Strategy
        
        Trades on strong positive news with price momentum
        """
        current_price = price_data.get('current_price', 0)
        change_pct = price_data.get('change_pct', 0)
        sentiment_score = sentiment.get('score', 0)
        
        sentiment_threshold = params.get('sentiment_threshold', 0.8)
        price_momentum = params.get('price_momentum', 0.01)
        news_age_minutes = params.get('news_age_minutes', 60)
        
        # Check if we have recent strong positive news
        recent_news = sentiment.get('recent_articles', [])
        has_recent_news = len(recent_news) > 0
        
        # Strong positive sentiment + price starting to move up
        if sentiment_score > sentiment_threshold and change_pct > price_momentum * 100 and has_recent_news:
            stop_loss = current_price * (1 - params.get('stop_loss', 0.02))
            take_profit = current_price * (1 + params.get('take_profit', 0.04))
            
            return {
                "symbol": symbol,
                "strategy": "News Momentum",
                "action": "BUY",
                "price": current_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "confidence": 0.70,
                "reason": f"Strong news momentum: Sentiment {sentiment_score:.2f}, Price +{change_pct:.2f}%",
                "max_hold_hours": params.get('max_hold_time_hours', 6),
                "timestamp": datetime.now().isoformat()
            }
        
        # Negative news + price decline = sell signal
        elif sentiment_score < -sentiment_threshold and change_pct < -price_momentum * 100:
            return {
                "symbol": symbol,
                "strategy": "News Momentum",
                "action": "SELL",
                "price": current_price,
                "confidence": 0.65,
                "reason": f"Negative news momentum: Sentiment {sentiment_score:.2f}",
                "timestamp": datetime.now().isoformat()
            }
        
        return None
    
    # === LEGACY LONG-TERM STRATEGIES ===
    
    def _trend_following_strategy(
        self,
        symbol: str,
        price_data: Dict[str, Any],
        indicators: Dict[str, Any],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trend following strategy based on moving averages"""
        ma_short = indicators.get('ma_short', 0)
        ma_long = indicators.get('ma_long', 0)
        current_price = price_data.get('current_price', 0)
        
        if ma_short == 0 or ma_long == 0:
            return None
        
        # Golden cross (short MA crosses above long MA)
        if ma_short > ma_long and current_price > ma_short:
            return {
                "symbol": symbol,
                "strategy": "Trend Following",
                "action": "BUY",
                "price": current_price,
                "confidence": 0.7,
                "reason": f"Golden cross: MA({params['ma_short']}) > MA({params['ma_long']})",
                "timestamp": datetime.now().isoformat()
            }
        
        # Death cross (short MA crosses below long MA)
        elif ma_short < ma_long and current_price < ma_short:
            return {
                "symbol": symbol,
                "strategy": "Trend Following",
                "action": "SELL",
                "price": current_price,
                "confidence": 0.7,
                "reason": f"Death cross: MA({params['ma_short']}) < MA({params['ma_long']})",
                "timestamp": datetime.now().isoformat()
            }
        
        return None
    
    def _mean_reversion_strategy(
        self,
        symbol: str,
        price_data: Dict[str, Any],
        indicators: Dict[str, Any],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Mean reversion strategy using Bollinger Bands"""
        bb = indicators.get('bollinger_bands', {})
        current_price = price_data.get('current_price', 0)
        
        upper = bb.get('upper', 0)
        lower = bb.get('lower', 0)
        middle = bb.get('middle', 0)
        
        if not upper or not lower:
            return None
        
        # Price below lower band - potential buy
        if current_price < lower:
            return {
                "symbol": symbol,
                "strategy": "Mean Reversion",
                "action": "BUY",
                "price": current_price,
                "confidence": 0.65,
                "reason": f"Price below lower Bollinger Band ({lower:.2f})",
                "target": middle,
                "timestamp": datetime.now().isoformat()
            }
        
        # Price above upper band - potential sell
        elif current_price > upper:
            return {
                "symbol": symbol,
                "strategy": "Mean Reversion",
                "action": "SELL",
                "price": current_price,
                "confidence": 0.65,
                "reason": f"Price above upper Bollinger Band ({upper:.2f})",
                "target": middle,
                "timestamp": datetime.now().isoformat()
            }
        
        return None
    
    def _momentum_strategy(
        self,
        symbol: str,
        price_data: Dict[str, Any],
        indicators: Dict[str, Any],
        sentiment: Dict[str, Any],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Momentum strategy using RSI and sentiment"""
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', {})
        current_price = price_data.get('current_price', 0)
        sentiment_score = sentiment.get('score', 0)
        
        rsi_oversold = params.get('rsi_oversold', 30)
        rsi_overbought = params.get('rsi_overbought', 70)
        
        # Oversold + positive sentiment
        if rsi < rsi_oversold and sentiment_score > 0:
            return {
                "symbol": symbol,
                "strategy": "Momentum",
                "action": "BUY",
                "price": current_price,
                "confidence": 0.75,
                "reason": f"RSI oversold ({rsi:.1f}) with positive sentiment",
                "timestamp": datetime.now().isoformat()
            }
        
        # Overbought + negative sentiment
        elif rsi > rsi_overbought and sentiment_score < 0:
            return {
                "symbol": symbol,
                "strategy": "Momentum",
                "action": "SELL",
                "price": current_price,
                "confidence": 0.75,
                "reason": f"RSI overbought ({rsi:.1f}) with negative sentiment",
                "timestamp": datetime.now().isoformat()
            }
        
        # MACD bullish crossover
        elif macd.get('histogram', 0) > 0 and sentiment_score > 0.3:
            return {
                "symbol": symbol,
                "strategy": "Momentum",
                "action": "BUY",
                "price": current_price,
                "confidence": 0.7,
                "reason": "MACD bullish crossover with strong sentiment",
                "timestamp": datetime.now().isoformat()
            }
        
        return None
    
    def aggregate_signals(
        self, 
        signals: List[Dict[str, Any]],
        min_confidence: float = 0.6,
        require_multi_strategy: bool = True
    ) -> Dict[str, Any]:
        """
        Aggregate multiple signals into a single decision using weighted voting
        
        Args:
            signals: List of trading signals
            min_confidence: Minimum confidence threshold
            require_multi_strategy: Require multiple strategies to agree
        
        Returns:
            Aggregated decision
        """
        if not signals:
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "reason": "No signals generated"
            }
        
        # Count buy/sell signals
        buy_signals = [s for s in signals if s['action'] == 'BUY']
        sell_signals = [s for s in signals if s['action'] == 'SELL']
        
        # Calculate weighted confidence (using strategy weights if available)
        total_buy_weight = sum(s.get('weight', 1.0) * s['confidence'] for s in buy_signals)
        total_sell_weight = sum(s.get('weight', 1.0) * s['confidence'] for s in sell_signals)
        total_weight = sum(s.get('weight', 1.0) for s in signals)
        
        buy_confidence = total_buy_weight / total_weight if total_weight > 0 else 0
        sell_confidence = total_sell_weight / total_weight if total_weight > 0 else 0
        
        # Multi-strategy requirement
        if require_multi_strategy:
            if len(buy_signals) < 2 and len(sell_signals) < 2:
                return {
                    "action": "HOLD",
                    "confidence": max(buy_confidence, sell_confidence),
                    "reason": "Insufficient strategy agreement (require multi-strategy confirmation)",
                    "signal_count": len(signals),
                    "buy_count": len(buy_signals),
                    "sell_count": len(sell_signals)
                }
        
        # Make decision based on weighted confidence
        if buy_confidence > sell_confidence and buy_confidence >= min_confidence:
            action = "BUY"
            confidence = buy_confidence
            reasons = [s['reason'] for s in buy_signals]
            # Get stop loss and take profit from signals (use tightest stop loss and average take profit)
            stop_loss_prices = [s.get('stop_loss') for s in buy_signals if s.get('stop_loss')]
            take_profit_prices = [s.get('take_profit') for s in buy_signals if s.get('take_profit')]
            max_hold_hours = min([s.get('max_hold_hours', 24) for s in buy_signals])
            
        elif sell_confidence > buy_confidence and sell_confidence >= min_confidence:
            action = "SELL"
            confidence = sell_confidence
            reasons = [s['reason'] for s in sell_signals]
            stop_loss_prices = []
            take_profit_prices = []
            max_hold_hours = None
            
        else:
            action = "HOLD"
            confidence = max(buy_confidence, sell_confidence)
            reasons = [f"Confidence below threshold: buy={buy_confidence:.2f}, sell={sell_confidence:.2f}"]
            stop_loss_prices = []
            take_profit_prices = []
            max_hold_hours = None
        
        result = {
            "action": action,
            "confidence": confidence,
            "reasons": reasons,
            "signal_count": len(signals),
            "buy_count": len(buy_signals),
            "sell_count": len(sell_signals),
            "buy_confidence": buy_confidence,
            "sell_confidence": sell_confidence
        }
        
        # Add execution parameters for buy signals
        if action == "BUY" and stop_loss_prices and take_profit_prices:
            result["stop_loss"] = max(stop_loss_prices)  # Tightest stop loss
            result["take_profit"] = sum(take_profit_prices) / len(take_profit_prices)  # Average take profit
            result["max_hold_hours"] = max_hold_hours
        
        return result
