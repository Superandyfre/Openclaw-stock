"""
Korean Stock Data Fetcher V2 (pykrx-dominant architecture)

Design Principles:
- pykrx is the ONLY high-frequency data source (99%+ usage)
- Yahoo Finance only used when pykrx completely fails (for names only)
- All price queries use pykrx exclusively
- Yahoo queries are tracked and limited to once per stock
"""
from typing import Dict, Optional, Any, List, Set
from datetime import datetime, timedelta
from loguru import logger
import asyncio
import json

try:
    import pykrx.stock as pykrx_stock
    PYKRX_AVAILABLE = True
except ImportError:
    PYKRX_AVAILABLE = False
    logger.warning("pykrx not available - Korean stock data will be limited")

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not available - fallback for stock names disabled")

from openclaw.core.database import DatabaseManager


class KoreanStockFetcherV2:
    """
    Korean Stock Data Fetcher V2 (pykrx-dominant)
    
    Data Source Priority:
    1. pykrx (99%+) - All price queries, most name queries
    2. Redis Cache - 30s for prices, 24h for names
    3. Local Mapping - 25+ major stocks as fallback
    4. Yahoo Finance (<1%) - Only for unknown stock names (one-time)
    """
    
    # Enhanced local stock name mapping (25+ major Korean stocks)
    STOCK_NAMES_KR = {
        '005930': '삼성전자',
        '000660': 'SK하이닉스',
        '035420': 'NAVER',
        '035720': '카카오',
        '051910': 'LG화학',
        '207940': '삼성바이오로직스',
        '006400': '삼성SDI',
        '068270': '셀트리온',
        '005380': '현대자동차',
        '000270': '기아',
        '105560': 'KB금융',
        '055550': '신한지주',
        '003670': '포스코퓨처엠',
        '096770': 'SK이노베이션',
        '012330': '현대모비스',
        '028260': '삼성물산',
        '066570': 'LG전자',
        '034730': 'SK',
        '009150': '삼성전기',
        '017670': 'SK텔레콤',
        '018260': '삼성에스디에스',
        '032830': '삼성생명',
        '003550': 'LG',
        '015760': '한국전력',
        '033780': 'KT&G',
    }
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        Initialize Korean Stock Fetcher V2
        
        Args:
            db_manager: Database manager for Redis caching
        """
        self.db = db_manager or DatabaseManager()
        
        # Cache configuration
        self.price_cache_ttl = 30  # 30 seconds for high-frequency
        self.name_cache_ttl = 86400  # 1 day (24 hours) for names
        
        # Track Yahoo Finance usage (ensure max 1 query per stock)
        self.yahoo_queried: Set[str] = set()
        
        # Statistics tracking
        self.stats = {
            'pykrx_calls': 0,
            'pykrx_success': 0,
            'cache_hits': 0,
            'local_fallback': 0,
            'yahoo_fallback': 0,
        }
        
        if not PYKRX_AVAILABLE:
            logger.error("pykrx is not installed! Install with: pip install pykrx>=1.0.46")
    
    def _get_base_code(self, symbol: str) -> str:
        """Extract base stock code from symbol (removes .KS/.KQ suffix)"""
        if symbol.endswith('.KS') or symbol.endswith('.KQ'):
            return symbol.split('.')[0]
        return symbol
    
    def _get_cache_key(self, key_type: str, code: str) -> str:
        """Get cache key for Redis"""
        return f"kr_stock_{key_type}_v2:{code}"
    
    def _get_price_from_cache(self, code: str) -> Optional[Dict[str, Any]]:
        """Get price data from cache"""
        cache_key = self._get_cache_key('price', code)
        cached = self.db.get(cache_key)
        if cached:
            self.stats['cache_hits'] += 1
            logger.debug(f"Cache hit for price: {code}")
            return cached
        return None
    
    def _save_price_to_cache(self, code: str, price_data: Dict[str, Any]):
        """Save price data to cache"""
        cache_key = self._get_cache_key('price', code)
        self.db.set(cache_key, price_data, expiry=self.price_cache_ttl)
    
    def _get_name_from_cache(self, code: str) -> Optional[str]:
        """Get stock name from cache"""
        cache_key = self._get_cache_key('name', code)
        cached = self.db.get(cache_key)
        if cached:
            self.stats['cache_hits'] += 1
            logger.debug(f"Cache hit for name: {code}")
            return cached
        return None
    
    def _save_name_to_cache(self, code: str, name: str):
        """Save stock name to cache"""
        cache_key = self._get_cache_key('name', code)
        self.db.set(cache_key, name, expiry=self.name_cache_ttl)
    
    async def _get_price_from_pykrx(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Get stock price from pykrx
        
        Args:
            code: Stock code (e.g., '005930')
        
        Returns:
            Price data dictionary or None
        """
        if not PYKRX_AVAILABLE:
            return None
        
        self.stats['pykrx_calls'] += 1
        
        try:
            # Get today's date
            today = datetime.now().strftime("%Y%m%d")
            
            # Get OHLCV data for today
            # Note: pykrx returns DataFrame, we need to run in executor for async
            df = await asyncio.to_thread(
                pykrx_stock.get_market_ohlcv_by_date,
                today,
                today,
                code
            )
            
            if df is None or df.empty:
                logger.debug(f"No data from pykrx for {code}")
                return None
            
            # Extract the latest row
            latest = df.iloc[-1]
            
            # Get previous close for change calculation
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
            prev_df = await asyncio.to_thread(
                pykrx_stock.get_market_ohlcv_by_date,
                yesterday,
                yesterday,
                code
            )
            
            prev_close = prev_df.iloc[-1]['종가'] if prev_df is not None and not prev_df.empty else latest['시가']
            
            # Calculate change
            current_price = float(latest['종가'])
            change = current_price - prev_close
            change_percent = (change / prev_close * 100) if prev_close > 0 else 0
            
            price_data = {
                'price': current_price,
                'open': float(latest['시가']),
                'high': float(latest['고가']),
                'low': float(latest['저가']),
                'volume': int(latest['거래량']),
                'change': change,
                'change_percent': change_percent,
                'source': 'pykrx',
                'timestamp': datetime.now().isoformat()
            }
            
            self.stats['pykrx_success'] += 1
            logger.debug(f"Successfully fetched price from pykrx for {code}: ₩{current_price:,.0f}")
            return price_data
            
        except Exception as e:
            logger.warning(f"pykrx failed for {code}: {e}")
            return None
    
    async def _get_name_from_pykrx(self, code: str) -> Optional[str]:
        """
        Get stock name from pykrx
        
        Args:
            code: Stock code (e.g., '005930')
        
        Returns:
            Stock name (Korean) or None
        """
        if not PYKRX_AVAILABLE:
            return None
        
        try:
            # Get stock name from pykrx
            name = await asyncio.to_thread(
                pykrx_stock.get_market_ticker_name,
                code
            )
            
            if name:
                logger.debug(f"Got name from pykrx for {code}: {name}")
                return name
            
        except Exception as e:
            logger.debug(f"pykrx name fetch failed for {code}: {e}")
        
        return None
    
    async def _get_name_from_yahoo_once(self, symbol: str) -> str:
        """
        Get stock name from Yahoo Finance (ONE-TIME ONLY per stock)
        
        Args:
            symbol: Stock symbol with suffix (e.g., '005930.KS')
        
        Returns:
            Stock name or fallback
        """
        base_code = self._get_base_code(symbol)
        
        if base_code in self.yahoo_queried:
            logger.debug(f"Already queried Yahoo for {base_code}, using fallback")
            return f"Unknown Company ({base_code})"
        
        if not YFINANCE_AVAILABLE:
            return f"Unknown Company ({base_code})"
        
        try:
            # Mark as queried BEFORE making the request
            self.yahoo_queried.add(base_code)
            self.stats['yahoo_fallback'] += 1
            
            logger.warning(f"🚨 LAST RESORT: Querying Yahoo Finance for {symbol} (one-time only)")
            
            # Query Yahoo Finance
            ticker = await asyncio.to_thread(yf.Ticker, symbol)
            info = await asyncio.to_thread(lambda: ticker.info)
            
            name = info.get('longName') or info.get('shortName') or info.get('displayName')
            
            if name:
                logger.info(f"Got name from Yahoo (one-time): {symbol} -> {name}")
                # Cache it permanently
                self._save_name_to_cache(base_code, name)
                return name
            
        except Exception as e:
            logger.warning(f"Yahoo Finance failed for {symbol}: {e}")
        
        return f"Unknown Company ({base_code})"
    
    async def get_stock_name(self, symbol: str) -> str:
        """
        Get stock name with strict priority:
        1. Redis cache (1 day TTL)
        2. pykrx real-time query
        3. Local mapping (preferred over Yahoo)
        4. Yahoo Finance (absolute last resort, one-time only)
        
        Args:
            symbol: Stock symbol (e.g., '005930.KS' or '005930')
        
        Returns:
            Stock name (Korean or English)
        """
        base_code = self._get_base_code(symbol)
        
        # 1. Check cache
        cached = self._get_name_from_cache(base_code)
        if cached:
            return cached
        
        # 2. Try pykrx (primary)
        name = await self._get_name_from_pykrx(base_code)
        if name:
            self._save_name_to_cache(base_code, name)
            return name
        
        # 3. Use local mapping (preferred over Yahoo)
        if base_code in self.STOCK_NAMES_KR:
            self.stats['local_fallback'] += 1
            name = self.STOCK_NAMES_KR[base_code]
            logger.info(f"Using local mapping for {base_code}: {name}")
            self._save_name_to_cache(base_code, name)
            return name
        
        # 4. Yahoo Finance (one-time query only)
        # Only query if we haven't already queried this stock
        if YFINANCE_AVAILABLE and base_code not in self.yahoo_queried:
            # Add .KS suffix if not present
            yahoo_symbol = symbol if symbol.endswith(('.KS', '.KQ')) else f"{symbol}.KS"
            return await self._get_name_from_yahoo_once(yahoo_symbol)
        
        # Complete failure
        name = f"Unknown Company ({base_code})"
        self._save_name_to_cache(base_code, name)
        return name
    
    async def get_stock_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get real-time stock price (pykrx ONLY)
        
        Yahoo Finance is NEVER used for price queries!
        
        Args:
            symbol: Stock symbol (e.g., '005930.KS' or '005930')
        
        Returns:
            Price data dictionary or None if failed
        """
        base_code = self._get_base_code(symbol)
        
        # 1. Check cache (30s TTL)
        cached = self._get_price_from_cache(base_code)
        if cached:
            return cached
        
        # 2. Get from pykrx (ONLY price data source)
        price_data = await self._get_price_from_pykrx(base_code)
        
        if price_data:
            self._save_price_to_cache(base_code, price_data)
            return price_data
        
        # 3. Complete failure (NO Yahoo fallback for prices)
        logger.error(f"pykrx failed to get price for {base_code} - no fallback available")
        return None
    
    async def get_multiple_stocks(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Batch fetch stock data (prices and names)
        
        Args:
            symbols: List of stock symbols
        
        Returns:
            Dictionary mapping symbols to stock data
        """
        results = {}
        
        # Fetch all data concurrently
        tasks = []
        for symbol in symbols:
            tasks.append(self._fetch_stock_data(symbol))
        
        stock_data_list = await asyncio.gather(*tasks)
        
        # Build results dictionary
        for symbol, data in zip(symbols, stock_data_list):
            if data:
                results[symbol] = data
        
        return results
    
    async def _fetch_stock_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch both price and name for a stock"""
        try:
            # Fetch price and name concurrently
            price_data, name = await asyncio.gather(
                self.get_stock_price(symbol),
                self.get_stock_name(symbol)
            )
            
            if price_data:
                return {
                    'symbol': symbol,
                    'name': name,
                    'price_data': price_data
                }
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
        
        return None
    
    def is_trading_time(self) -> bool:
        """
        Check if within Korean trading hours
        
        Korean market: 09:00-15:30 KST
        Beijing time: 08:00-14:30 CST (same timezone as KST)
        
        Returns:
            True if within trading hours
        """
        now = datetime.now()
        hour, minute = now.hour, now.minute
        
        # Weekend check
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Market hours: 08:00-14:30 (Beijing/KST time)
        if hour < 8 or hour > 14:
            return False
        if hour == 14 and minute > 30:
            return False
        
        return True
    
    async def monitor_stocks_high_frequency(
        self,
        symbols: List[str],
        callback,
        interval: int = 30,
        threshold: float = 2.0
    ):
        """
        High-frequency monitoring (100% pykrx)
        
        Features:
        - 30-second polling (safe with pykrx, no rate limits)
        - Trading hours detection (08:00-14:30 Beijing time)
        - Cache warming on startup
        - Detailed statistics logging
        
        Args:
            symbols: List of stock symbols to monitor
            callback: Async function to call on alerts
            interval: Polling interval in seconds (default: 30)
            threshold: Change threshold for alerts (default: 2.0%)
        """
        logger.info(f"🚀 Starting high-frequency monitoring (pykrx-dominant)")
        logger.info(f"   Symbols: {symbols}")
        logger.info(f"   Interval: {interval}s")
        logger.info(f"   Threshold: ±{threshold}%")
        
        # Warm up cache (get all stock names)
        logger.info("Warming up cache...")
        await self.get_multiple_stocks(symbols)
        logger.info("✅ Cache warmed up")
        
        cycle = 0
        while True:
            cycle += 1
            
            # Check trading hours
            if not self.is_trading_time():
                logger.debug("Outside trading hours, checking every 5 minutes")
                await asyncio.sleep(300)  # Check every 5 minutes
                continue
            
            logger.debug(f"Cycle {cycle}: Fetching prices for {len(symbols)} stocks")
            
            # Batch fetch prices (all via pykrx)
            stock_data = await self.get_multiple_stocks(symbols)
            
            # Check for anomalies
            for symbol, data in stock_data.items():
                price_data = data['price_data']
                change_percent = price_data.get('change_percent', 0)
                
                if abs(change_percent) >= threshold:
                    logger.warning(
                        f"🚨 Alert: {data['name']} ({symbol}) "
                        f"{change_percent:+.2f}% (₩{price_data['price']:,.0f})"
                    )
                    await callback({
                        'symbol': symbol,
                        'name': data['name'],
                        'price_data': price_data,
                        'alert_type': 'threshold_breach'
                    })
            
            # Log statistics every 10 cycles
            if cycle % 10 == 0:
                self._log_stats()
            
            await asyncio.sleep(interval)
    
    def _log_stats(self):
        """Log data source usage statistics"""
        total = self.stats['pykrx_calls'] + self.stats['cache_hits']
        if total == 0:
            return
        
        pykrx_success_rate = (self.stats['pykrx_success'] / self.stats['pykrx_calls'] * 100) if self.stats['pykrx_calls'] > 0 else 0
        cache_hit_rate = (self.stats['cache_hits'] / total * 100) if total > 0 else 0
        yahoo_usage_rate = (self.stats['yahoo_fallback'] / total * 100) if total > 0 else 0
        
        logger.info(
            f"📊 Stats: pykrx={self.stats['pykrx_calls']} calls "
            f"(success {pykrx_success_rate:.1f}%) "
            f"cache_hits={self.stats['cache_hits']} "
            f"(hit rate {cache_hit_rate:.1f}%) "
            f"local_fallback={self.stats['local_fallback']} "
            f"yahoo_fallback={self.stats['yahoo_fallback']} "
            f"(yahoo rate {yahoo_usage_rate:.1f}%)"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get detailed statistics
        
        Returns:
            Dictionary with statistics and calculated rates
        """
        total = self.stats['pykrx_calls'] + self.stats['cache_hits']
        
        return {
            **self.stats,
            'pykrx_success_rate': (self.stats['pykrx_success'] / self.stats['pykrx_calls'] * 100) if self.stats['pykrx_calls'] > 0 else 0,
            'cache_hit_rate': (self.stats['cache_hits'] / total * 100) if total > 0 else 0,
            'yahoo_usage_rate': (self.stats['yahoo_fallback'] / total * 100) if total > 0 else 0,
        }
