"""
Strategy engine for trading signals
"""
from typing import Dict, List, Any
from datetime import datetime
from loguru import logger


class StrategyEngine:
    """Manages multiple trading strategies"""
    
    def __init__(self, strategies_config: List[Dict[str, Any]]):
        """
        Initialize strategy engine
        
        Args:
            strategies_config: List of strategy configurations
        """
        self.strategies = {
            s['name']: s for s in strategies_config if s.get('enabled', True)
        }
        self.signal_history: List[Dict[str, Any]] = []
    
    def generate_signals(
        self,
        symbol: str,
        price_data: Dict[str, Any],
        technical_indicators: Dict[str, Any],
        sentiment: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate trading signals from all strategies
        
        Args:
            symbol: Asset symbol
            price_data: Current price data
            technical_indicators: Technical analysis results
            sentiment: Sentiment analysis results
        
        Returns:
            List of trading signals
        """
        signals = []
        
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
    
    def aggregate_signals(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate multiple signals into a single decision
        
        Args:
            signals: List of trading signals
        
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
        
        # Calculate weighted confidence
        buy_confidence = sum(s['confidence'] for s in buy_signals) / len(signals) if buy_signals else 0
        sell_confidence = sum(s['confidence'] for s in sell_signals) / len(signals) if sell_signals else 0
        
        # Make decision
        if buy_confidence > sell_confidence and buy_confidence > 0.5:
            action = "BUY"
            confidence = buy_confidence
            reasons = [s['reason'] for s in buy_signals]
        elif sell_confidence > buy_confidence and sell_confidence > 0.5:
            action = "SELL"
            confidence = sell_confidence
            reasons = [s['reason'] for s in sell_signals]
        else:
            action = "HOLD"
            confidence = 0.5
            reasons = ["Conflicting or weak signals"]
        
        return {
            "action": action,
            "confidence": confidence,
            "reasons": reasons,
            "signal_count": len(signals),
            "buy_count": len(buy_signals),
            "sell_count": len(sell_signals)
        }
