"""
Stock monitor for Yahoo Finance API
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not available")


class StockMonitor:
    """
    Monitors stock prices using Yahoo Finance
    
    Rate Limit: 2000 requests/hour
    Update Frequency: 15 seconds
    """
    
    def __init__(self, symbols: List[str], rate_limit: int = 2000):
        """
        Initialize stock monitor
        
        Args:
            symbols: List of stock symbols to monitor
            rate_limit: Maximum requests per hour
        """
        self.symbols = symbols
        self.rate_limit = rate_limit
        self.last_data: Dict[str, Dict[str, Any]] = {}
        self.request_count = 0
        self.last_reset = datetime.now()
    
    async def fetch_stock_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current stock data
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Stock data dictionary
        """
        if not YFINANCE_AVAILABLE:
            return self._generate_mock_data(symbol)
        
        try:
            # Check rate limit
            if not self._check_rate_limit():
                logger.warning(f"Rate limit reached for Yahoo Finance API")
                return self.last_data.get(symbol)
            
            ticker = yf.Ticker(symbol)
            info = ticker.info
            history = ticker.history(period="1d", interval="1m")
            
            if history.empty:
                return None
            
            current_price = history['Close'].iloc[-1]
            open_price = history['Open'].iloc[0]
            high_price = history['High'].max()
            low_price = history['Low'].min()
            volume = history['Volume'].sum()
            
            data = {
                "symbol": symbol,
                "current_price": float(current_price),
                "open": float(open_price),
                "high": float(high_price),
                "low": float(low_price),
                "volume": int(volume),
                "change": float(current_price - open_price),
                "change_pct": float((current_price - open_price) / open_price * 100),
                "timestamp": datetime.now().isoformat(),
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", 0)
            }
            
            self.last_data[symbol] = data
            self.request_count += 1
            
            return data
        
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            return self.last_data.get(symbol)
    
    async def fetch_all_stocks(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch data for all monitored stocks
        
        Returns:
            Dictionary mapping symbols to their data
        """
        tasks = [self.fetch_stock_data(symbol) for symbol in self.symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        stock_data = {}
        for symbol, result in zip(self.symbols, results):
            if isinstance(result, dict):
                stock_data[symbol] = result
            elif result is not None:
                logger.error(f"Error fetching {symbol}: {result}")
        
        return stock_data
    
    def _check_rate_limit(self) -> bool:
        """
        Check if within rate limit
        
        Returns:
            True if can make request
        """
        now = datetime.now()
        elapsed_hours = (now - self.last_reset).total_seconds() / 3600
        
        if elapsed_hours >= 1.0:
            self.request_count = 0
            self.last_reset = now
            return True
        
        return self.request_count < self.rate_limit
    
    def _generate_mock_data(self, symbol: str) -> Dict[str, Any]:
        """Generate mock data for testing"""
        import random
        
        base_price = 100.0
        change_pct = random.uniform(-3, 3)
        current_price = base_price * (1 + change_pct / 100)
        
        return {
            "symbol": symbol,
            "current_price": current_price,
            "open": base_price,
            "high": current_price * 1.02,
            "low": current_price * 0.98,
            "volume": random.randint(1000000, 10000000),
            "change": current_price - base_price,
            "change_pct": change_pct,
            "timestamp": datetime.now().isoformat(),
            "market_cap": 1000000000,
            "pe_ratio": 20.0,
            "mock": True
        }
    
    def get_historical_prices(self, symbol: str, period: str = "1d") -> List[float]:
        """
        Get historical prices
        
        Args:
            symbol: Stock symbol
            period: Time period (1d, 5d, 1mo, etc.)
        
        Returns:
            List of historical prices
        """
        if not YFINANCE_AVAILABLE:
            return [100.0] * 50
        
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(period=period)
            return history['Close'].tolist()
        except Exception as e:
            logger.error(f"Failed to fetch historical data for {symbol}: {e}")
            return []
