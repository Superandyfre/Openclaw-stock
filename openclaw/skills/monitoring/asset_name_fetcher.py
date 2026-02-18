"""
Real-time asset name fetcher for stocks and cryptocurrencies
"""
from typing import Dict, Optional
import aiohttp
import asyncio
from loguru import logger
from openclaw.core.database import DatabaseManager


class AssetNameFetcher:
    """
    Real-time asset name fetcher
    
    Features:
    - Yahoo Finance for Korean stocks (.KS, .KQ)
    - CoinGecko for cryptocurrencies
    - Redis caching (24h TTL)
    - Async batch fetching
    """
    
    # Fallback mappings when API fails
    KR_STOCK_FALLBACK = {
        '005930': 'Samsung Electronics',
        '000660': 'SK Hynix',
        '035420': 'NAVER Corporation',
        '035720': 'Kakao Corporation',
        '051910': 'LG Chem',
        '006400': 'Samsung SDI',
        '207940': 'Samsung Biologics',
        '068270': 'Celltrion',
        '005380': 'Hyundai Motor',
        '000270': 'Kia Corporation',
    }
    
    CRYPTO_FALLBACK = {
        'BTC': 'Bitcoin',
        'ETH': 'Ethereum',
        'SOL': 'Solana',
        'XRP': 'Ripple',
        'ADA': 'Cardano',
        'DOGE': 'Dogecoin',
    }
    
    CACHE_TTL = 86400  # 24 hours in seconds
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        Initialize asset name fetcher
        
        Args:
            db_manager: Database manager for caching (optional)
        """
        self.db = db_manager or DatabaseManager()
        self.session: Optional[aiohttp.ClientSession] = None
        self._crypto_cache: Dict[str, str] = {}  # In-memory cache for CoinGecko list
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _get_cache_key(self, symbol: str) -> str:
        """Get cache key for symbol"""
        return f"asset_name:{symbol}"
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol format"""
        symbol = symbol.upper().strip()
        
        # Handle Upbit format (KRW-BTC -> BTC)
        if symbol.startswith('KRW-'):
            symbol = symbol[4:]
        
        return symbol
    
    def _is_korean_stock(self, symbol: str) -> bool:
        """Check if symbol is a Korean stock"""
        return symbol.endswith('.KS') or symbol.endswith('.KQ')
    
    def _is_crypto(self, symbol: str) -> bool:
        """Check if symbol is a cryptocurrency"""
        normalized = self._normalize_symbol(symbol)
        # Check if it's a known crypto or not a stock
        return (normalized in self.CRYPTO_FALLBACK or 
                not self._is_korean_stock(symbol))
    
    async def _fetch_korean_stock_name(self, symbol: str) -> Optional[str]:
        """
        Fetch Korean stock name from Yahoo Finance
        
        Args:
            symbol: Stock symbol (e.g., '005930.KS')
        
        Returns:
            Stock name or None if failed
        """
        if not self.session:
            return None
        
        try:
            url = "https://query1.finance.yahoo.com/v7/finance/quote"
            params = {"symbols": symbol}
            
            async with self.session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if (data.get('quoteResponse') and 
                        data['quoteResponse'].get('result') and 
                        len(data['quoteResponse']['result']) > 0):
                        
                        result = data['quoteResponse']['result'][0]
                        # Try multiple name fields
                        name = (result.get('longName') or 
                               result.get('shortName') or 
                               result.get('displayName'))
                        
                        if name:
                            logger.debug(f"Fetched name for {symbol}: {name}")
                            return name
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching name for {symbol} from Yahoo Finance")
        except Exception as e:
            logger.warning(f"Error fetching name for {symbol}: {e}")
        
        return None
    
    async def _fetch_crypto_list(self) -> Dict[str, str]:
        """
        Fetch cryptocurrency list from CoinGecko
        
        Returns:
            Dictionary mapping symbol to name
        """
        if not self.session:
            return {}
        
        # Check in-memory cache first
        if self._crypto_cache:
            return self._crypto_cache
        
        try:
            url = "https://api.coingecko.com/api/v3/coins/list"
            
            async with self.session.get(url, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Build symbol -> name mapping
                    crypto_map = {}
                    for coin in data:
                        symbol = coin.get('symbol', '').upper()
                        name = coin.get('name', '')
                        if symbol and name:
                            crypto_map[symbol] = name
                    
                    # Cache in memory for the session
                    self._crypto_cache = crypto_map
                    logger.info(f"Fetched {len(crypto_map)} cryptocurrencies from CoinGecko")
                    return crypto_map
        except asyncio.TimeoutError:
            logger.warning("Timeout fetching crypto list from CoinGecko")
        except Exception as e:
            logger.warning(f"Error fetching crypto list: {e}")
        
        return {}
    
    async def _fetch_crypto_name(self, symbol: str) -> Optional[str]:
        """
        Fetch cryptocurrency name from CoinGecko
        
        Args:
            symbol: Crypto symbol (e.g., 'BTC', 'KRW-BTC')
        
        Returns:
            Crypto name or None if failed
        """
        normalized = self._normalize_symbol(symbol)
        
        # Fetch the crypto list
        crypto_map = await self._fetch_crypto_list()
        
        # Look up the name
        return crypto_map.get(normalized)
    
    async def get_asset_name(self, symbol: str) -> str:
        """
        Get full asset name with caching
        
        Args:
            symbol: Asset symbol
        
        Returns:
            Full asset name (e.g., 'Samsung Electronics Co., Ltd.')
        """
        # Check cache first
        cache_key = self._get_cache_key(symbol)
        cached_name = self.db.get(cache_key)
        if cached_name:
            return cached_name
        
        name = None
        
        # Determine asset type and fetch name
        if self._is_korean_stock(symbol):
            # Try Yahoo Finance
            name = await self._fetch_korean_stock_name(symbol)
            
            # Fallback to local mapping
            if not name:
                stock_code = symbol.split('.')[0]
                name = self.KR_STOCK_FALLBACK.get(stock_code)
        else:
            # Try CoinGecko
            name = await self._fetch_crypto_name(symbol)
            
            # Fallback to local mapping
            if not name:
                normalized = self._normalize_symbol(symbol)
                name = self.CRYPTO_FALLBACK.get(normalized)
        
        # Default fallback
        if not name:
            name = f"Unknown Asset ({symbol})"
            logger.warning(f"Could not fetch name for {symbol}, using default")
        
        # Cache the result
        self.db.set(cache_key, name, expiry=self.CACHE_TTL)
        
        return name
    
    async def get_multiple_names(self, symbols: list[str]) -> Dict[str, str]:
        """
        Batch fetch asset names
        
        Args:
            symbols: List of asset symbols
        
        Returns:
            Dictionary mapping symbols to names
        """
        # Fetch all names concurrently
        tasks = [self.get_asset_name(symbol) for symbol in symbols]
        names = await asyncio.gather(*tasks)
        
        # Build result dictionary
        return {symbol: name for symbol, name in zip(symbols, names)}
