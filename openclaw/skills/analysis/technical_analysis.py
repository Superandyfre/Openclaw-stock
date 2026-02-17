"""
Technical analysis indicators
Supports both long-term and short-term timeframes
"""
import numpy as np
from typing import List, Dict, Any, Tuple
from loguru import logger


class TechnicalAnalysis:
    """Technical indicators calculator"""
    
    # === SHORT-TERM INDICATORS ===
    
    @staticmethod
    def calculate_fast_rsi(prices: List[float], period: int = 5) -> float:
        """
        Calculate Fast RSI for short-term trading (5 period)
        
        Args:
            prices: List of prices
            period: Period for RSI calculation (default 5 for short-term)
        
        Returns:
            RSI value (0-100)
        """
        return TechnicalAnalysis.calculate_rsi(prices, period)
    
    @staticmethod
    def calculate_fast_macd(
        prices: List[float],
        fast_period: int = 5,
        slow_period: int = 10,
        signal_period: int = 5
    ) -> Dict[str, Any]:
        """
        Calculate Fast MACD for short-term trading (5,10,5)
        
        Args:
            prices: List of prices
            fast_period: Fast EMA period (default 5)
            slow_period: Slow EMA period (default 10)
            signal_period: Signal line period (default 5)
        
        Returns:
            MACD values
        """
        return TechnicalAnalysis.calculate_macd(prices, fast_period, slow_period, signal_period)
    
    @staticmethod
    def detect_intraday_high_low(
        prices: List[float],
        current_price: float,
        threshold: float = 0.005
    ) -> Dict[str, Any]:
        """
        Detect if current price is near intraday high or low
        
        Args:
            prices: Intraday price data
            current_price: Current price
            threshold: Threshold for proximity (default 0.5%)
        
        Returns:
            High/low detection results
        """
        if not prices:
            return {
                "near_high": False,
                "near_low": False,
                "intraday_high": 0,
                "intraday_low": 0
            }
        
        intraday_high = max(prices)
        intraday_low = min(prices)
        
        near_high = current_price >= intraday_high * (1 - threshold)
        near_low = current_price <= intraday_low * (1 + threshold)
        
        return {
            "near_high": near_high,
            "near_low": near_low,
            "intraday_high": intraday_high,
            "intraday_low": intraday_low,
            "distance_from_high_pct": (intraday_high - current_price) / intraday_high * 100,
            "distance_from_low_pct": (current_price - intraday_low) / intraday_low * 100
        }
    
    @staticmethod
    def detect_volume_anomaly(
        current_volume: float,
        historical_volumes: List[float],
        threshold: float = 2.5
    ) -> Dict[str, Any]:
        """
        Detect volume anomalies (spikes)
        
        Args:
            current_volume: Current volume
            historical_volumes: Historical volume data
            threshold: Multiplier threshold for anomaly (default 2.5x)
        
        Returns:
            Volume anomaly detection results
        """
        if not historical_volumes:
            return {
                "is_anomaly": False,
                "volume_ratio": 1.0,
                "avg_volume": current_volume
            }
        
        avg_volume = np.mean(historical_volumes)
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        is_anomaly = volume_ratio >= threshold
        
        return {
            "is_anomaly": is_anomaly,
            "volume_ratio": float(volume_ratio),
            "avg_volume": float(avg_volume),
            "current_volume": current_volume,
            "threshold": threshold
        }
    
    @staticmethod
    def calculate_minute_mas(prices: List[float]) -> Dict[str, float]:
        """
        Calculate minute-level moving averages (5, 10, 15, 30)
        
        Args:
            prices: List of minute prices
        
        Returns:
            Dictionary of minute MAs
        """
        result = {
            "ma_5": 0.0,
            "ma_10": 0.0,
            "ma_15": 0.0,
            "ma_30": 0.0
        }
        
        if len(prices) >= 5:
            result["ma_5"] = float(np.mean(prices[-5:]))
        
        if len(prices) >= 10:
            result["ma_10"] = float(np.mean(prices[-10:]))
        
        if len(prices) >= 15:
            result["ma_15"] = float(np.mean(prices[-15:]))
        
        if len(prices) >= 30:
            result["ma_30"] = float(np.mean(prices[-30:]))
        
        return result
    
    # === ORIGINAL INDICATORS ===
    
    @staticmethod
    def calculate_ma(prices: List[float], period: int) -> List[float]:
        """
        Calculate Simple Moving Average
        
        Args:
            prices: List of prices
            period: Period for MA
        
        Returns:
            Moving average values
        """
        if len(prices) < period:
            return []
        
        ma_values = []
        for i in range(period - 1, len(prices)):
            ma = sum(prices[i - period + 1:i + 1]) / period
            ma_values.append(ma)
        
        return ma_values
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> List[float]:
        """
        Calculate Exponential Moving Average
        
        Args:
            prices: List of prices
            period: Period for EMA
        
        Returns:
            EMA values
        """
        if len(prices) < period:
            return []
        
        multiplier = 2 / (period + 1)
        ema_values = []
        
        # Start with SMA
        sma = sum(prices[:period]) / period
        ema_values.append(sma)
        
        # Calculate EMA
        for price in prices[period:]:
            ema = (price - ema_values[-1]) * multiplier + ema_values[-1]
            ema_values.append(ema)
        
        return ema_values
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """
        Calculate Relative Strength Index
        
        Args:
            prices: List of prices
            period: Period for RSI calculation
        
        Returns:
            RSI value (0-100)
        """
        if len(prices) < period + 1:
            return 50.0
        
        # Calculate price changes
        deltas = np.diff(prices[-period - 1:])
        
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, Any]:
        """
        Calculate MACD (Moving Average Convergence Divergence)
        
        Args:
            prices: List of prices
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line period
        
        Returns:
            MACD values
        """
        if len(prices) < slow_period:
            return {"macd": 0, "signal": 0, "histogram": 0}
        
        # Calculate EMAs
        fast_ema = TechnicalAnalysis.calculate_ema(prices, fast_period)
        slow_ema = TechnicalAnalysis.calculate_ema(prices, slow_period)
        
        # MACD line
        min_len = min(len(fast_ema), len(slow_ema))
        macd_line = [fast_ema[-(min_len - i)] - slow_ema[-(min_len - i)] 
                     for i in range(min_len)]
        
        # Signal line
        signal_line = TechnicalAnalysis.calculate_ema(macd_line, signal_period)
        
        if not macd_line or not signal_line:
            return {"macd": 0, "signal": 0, "histogram": 0}
        
        # Histogram
        histogram = macd_line[-1] - signal_line[-1]
        
        return {
            "macd": macd_line[-1],
            "signal": signal_line[-1],
            "histogram": histogram
        }
    
    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Dict[str, float]:
        """
        Calculate Bollinger Bands
        
        Args:
            prices: List of prices
            period: Period for moving average
            std_dev: Standard deviation multiplier
        
        Returns:
            Upper, middle, and lower bands
        """
        if len(prices) < period:
            current_price = prices[-1] if prices else 0
            return {
                "upper": current_price,
                "middle": current_price,
                "lower": current_price
            }
        
        recent_prices = prices[-period:]
        middle_band = sum(recent_prices) / period
        
        # Calculate standard deviation
        variance = sum((p - middle_band) ** 2 for p in recent_prices) / period
        std = variance ** 0.5
        
        upper_band = middle_band + (std_dev * std)
        lower_band = middle_band - (std_dev * std)
        
        return {
            "upper": upper_band,
            "middle": middle_band,
            "lower": lower_band,
            "bandwidth": (upper_band - lower_band) / middle_band * 100
        }
    
    @staticmethod
    def identify_support_resistance(
        prices: List[float],
        window: int = 10
    ) -> Dict[str, List[float]]:
        """
        Identify support and resistance levels
        
        Args:
            prices: List of prices
            window: Window size for local extrema
        
        Returns:
            Support and resistance levels
        """
        if len(prices) < window * 2:
            return {"support": [], "resistance": []}
        
        support_levels = []
        resistance_levels = []
        
        for i in range(window, len(prices) - window):
            # Check if local minimum (support)
            is_support = all(prices[i] <= prices[i - j] for j in range(1, window + 1))
            is_support = is_support and all(prices[i] <= prices[i + j] for j in range(1, window + 1))
            
            if is_support:
                support_levels.append(prices[i])
            
            # Check if local maximum (resistance)
            is_resistance = all(prices[i] >= prices[i - j] for j in range(1, window + 1))
            is_resistance = is_resistance and all(prices[i] >= prices[i + j] for j in range(1, window + 1))
            
            if is_resistance:
                resistance_levels.append(prices[i])
        
        # Remove duplicates and sort
        support_levels = sorted(set(support_levels))
        resistance_levels = sorted(set(resistance_levels), reverse=True)
        
        return {
            "support": support_levels[:3],  # Top 3 support levels
            "resistance": resistance_levels[:3]  # Top 3 resistance levels
        }
    
    @staticmethod
    def analyze_trend(prices: List[float], period: int = 20) -> str:
        """
        Analyze price trend
        
        Args:
            prices: List of prices
            period: Period for trend analysis
        
        Returns:
            Trend direction (uptrend, downtrend, sideways)
        """
        if len(prices) < period:
            return "insufficient_data"
        
        recent_prices = prices[-period:]
        
        # Simple linear regression
        x = np.arange(len(recent_prices))
        coeffs = np.polyfit(x, recent_prices, deg=1)
        slope = coeffs[0]
        
        # Determine trend
        avg_price = np.mean(recent_prices)
        slope_pct = (slope / avg_price) * 100
        
        if slope_pct > 0.5:
            return "uptrend"
        elif slope_pct < -0.5:
            return "downtrend"
        else:
            return "sideways"
    
    @staticmethod
    def calculate_volatility(prices: List[float], period: int = 20) -> float:
        """
        Calculate historical volatility
        
        Args:
            prices: List of prices
            period: Period for calculation
        
        Returns:
            Volatility (annualized)
        """
        if len(prices) < period:
            return 0.0
        
        recent_prices = prices[-period:]
        returns = np.diff(np.log(recent_prices))
        volatility = np.std(returns) * np.sqrt(252)  # Annualized
        
        return float(volatility)
