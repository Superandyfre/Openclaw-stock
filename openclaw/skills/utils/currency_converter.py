"""
Currency Converter for OpenClaw Trading System
Converts all prices to Korean Won (KRW) with real-time exchange rates
"""
import asyncio
import re
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import yaml
import os
from loguru import logger

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning("aiohttp not available, exchange rates will use fallback only")


class CurrencyConverter:
    """
    Currency converter with real-time exchange rates
    
    Features:
    - Real-time exchange rate fetching from free APIs
    - Hourly rate caching to minimize API calls
    - Automatic asset currency detection
    - Fallback rates when API unavailable
    - KRW formatting with thousand separators
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize currency converter
        
        Args:
            config_path: Path to currency_config.yaml
        """
        # Load configuration
        if config_path is None:
            # Default path relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(base_dir, "config", "currency_config.yaml")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # Exchange rates cache
        self.exchange_rates: Dict[str, float] = {}
        self.last_update: Optional[datetime] = None
        
        # Configuration shortcuts
        self.primary_currency = self.config.get('primary_currency', 'KRW')
        self.currency_symbol = self.config.get('currency_symbol', '₩')
        self.fallback_rates = self.config['exchange_rate']['fallback_rates']
        self.cache_duration = timedelta(
            hours=self.config['exchange_rate']['cache_duration_hours']
        )
        
        # Asset patterns for currency detection
        self.asset_patterns = self.config['asset_currency_mapping']['patterns']
        self.default_currency = self.config['asset_currency_mapping']['default']
        
        logger.info(f"💱 Currency converter initialized (target: {self.primary_currency})")
    
    async def update_rates(self, force: bool = False) -> bool:
        """
        Update exchange rates from API
        
        Args:
            force: Force update even if cache is valid
        
        Returns:
            True if rates updated successfully, False if using fallback
        """
        # Check if cache is still valid
        if not force and self.last_update:
            if datetime.now() - self.last_update < self.cache_duration:
                logger.debug("Using cached exchange rates")
                return True
        
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available, using fallback rates")
            self.exchange_rates = self.fallback_rates.copy()
            self.last_update = datetime.now()
            return False
        
        # Try primary API
        success = await self._fetch_from_primary_api()
        
        # Try backup API if primary fails
        if not success:
            logger.warning("Primary API failed, trying backup...")
            success = await self._fetch_from_backup_api()
        
        # Use fallback rates if all APIs fail
        if not success:
            logger.warning("All APIs failed, using fallback rates")
            self.exchange_rates = self.fallback_rates.copy()
            self.last_update = datetime.now()
            return False
        
        self.last_update = datetime.now()
        logger.info(f"✅ Exchange rates updated: {len(self.exchange_rates)} currencies")
        return True
    
    async def _fetch_from_primary_api(self) -> bool:
        """Fetch rates from primary API"""
        try:
            api_url = self.config['exchange_rate']['primary_api']
            timeout = self.config['exchange_rate']['timeout_seconds']
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # API returns rates FROM KRW to other currencies
                        # We need rates TO KRW (inverse)
                        rates = data.get('rates', {})
                        
                        # Invert rates: if 1 KRW = 0.00075 USD, then 1 USD = 1333.33 KRW
                        self.exchange_rates = {
                            currency: 1.0 / rate if rate != 0 else 0
                            for currency, rate in rates.items()
                        }
                        
                        logger.debug(f"Fetched rates from primary API: {len(self.exchange_rates)} currencies")
                        return True
        
        except Exception as e:
            logger.warning(f"Primary API fetch failed: {e}")
        
        return False
    
    async def _fetch_from_backup_api(self) -> bool:
        """Fetch rates from backup API"""
        try:
            api_url = self.config['exchange_rate']['backup_api']
            timeout = self.config['exchange_rate']['timeout_seconds']
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        rates = data.get('rates', {})
                        
                        # Invert rates
                        self.exchange_rates = {
                            currency: 1.0 / rate if rate != 0 else 0
                            for currency, rate in rates.items()
                        }
                        
                        logger.debug(f"Fetched rates from backup API: {len(self.exchange_rates)} currencies")
                        return True
        
        except Exception as e:
            logger.warning(f"Backup API fetch failed: {e}")
        
        return False
    
    def get_asset_currency(self, symbol: str) -> str:
        """
        Detect asset's native currency from symbol
        
        Args:
            symbol: Asset symbol (e.g., "AAPL", "005930.KS", "BTC-USD")
        
        Returns:
            Currency code (e.g., "USD", "KRW")
        
        Examples:
            >>> converter.get_asset_currency("005930.KS")
            'KRW'
            >>> converter.get_asset_currency("AAPL")
            'USD'
            >>> converter.get_asset_currency("BTC-USD")
            'USD'
        """
        # Try each pattern
        for pattern_config in self.asset_patterns:
            pattern = pattern_config['pattern']
            if re.match(pattern, symbol):
                currency = pattern_config['currency']
                logger.debug(f"Asset {symbol} -> {currency} (matched: {pattern})")
                return currency
        
        # Default currency
        logger.debug(f"Asset {symbol} -> {self.default_currency} (default)")
        return self.default_currency
    
    async def convert_to_krw(
        self,
        amount: float,
        from_currency: str
    ) -> float:
        """
        Convert amount from any currency to KRW
        
        Args:
            amount: Amount in original currency
            from_currency: Source currency code (e.g., "USD")
        
        Returns:
            Amount in KRW
        
        Examples:
            >>> await converter.convert_to_krw(100, "USD")
            133500.0  # 100 USD = 133,500 KRW
        """
        # If already in KRW, return as-is
        if from_currency == 'KRW':
            return amount
        
        # Ensure rates are loaded
        if not self.exchange_rates:
            await self.update_rates()
        
        # Get exchange rate
        rate = self.exchange_rates.get(from_currency)
        
        if rate is None:
            logger.warning(
                f"No exchange rate for {from_currency}, using fallback"
            )
            rate = self.fallback_rates.get(from_currency, 1.0)
        
        # Convert: amount * rate = KRW
        krw_amount = amount * rate
        
        logger.debug(f"{amount} {from_currency} -> {krw_amount:.2f} KRW (rate: {rate})")
        return krw_amount
    
    async def convert_price(
        self,
        symbol: str,
        price: float
    ) -> float:
        """
        Convert asset price to KRW (auto-detect currency)
        
        Args:
            symbol: Asset symbol
            price: Price in asset's native currency
        
        Returns:
            Price in KRW
        
        Examples:
            >>> await converter.convert_price("AAPL", 178.50)
            238297.5  # $178.50 = ₩238,298
            >>> await converter.convert_price("005930.KS", 75000)
            75000.0  # Already in KRW
        """
        currency = self.get_asset_currency(symbol)
        return await self.convert_to_krw(price, currency)
    
    def format_krw(self, amount: float) -> str:
        """
        Format KRW amount with currency symbol and thousand separators
        
        Args:
            amount: Amount in KRW
        
        Returns:
            Formatted string
        
        Examples:
            >>> converter.format_krw(89445000)
            '₩89,445,000'
            >>> converter.format_krw(1234.56)
            '₩1,235'
        """
        # Round to integer (no decimals for KRW)
        amount_int = int(round(amount))
        
        # Format with thousand separators
        formatted = f"{amount_int:,}"
        
        # Add currency symbol
        return f"{self.currency_symbol}{formatted}"
    
    def format_change(self, change_pct: float) -> str:
        """
        Format percentage change with sign
        
        Args:
            change_pct: Percentage change (e.g., 0.0235 for +2.35%)
        
        Returns:
            Formatted percentage string
        
        Examples:
            >>> converter.format_change(0.0235)
            '+2.35%'
            >>> converter.format_change(-0.0147)
            '-1.47%'
        """
        # Get decimal places from config
        decimal_places = self.config['formatting']['percentage']['decimal_places']
        show_positive_sign = self.config['formatting']['percentage']['show_positive_sign']
        
        # Convert to percentage
        pct = change_pct * 100
        
        # Format with appropriate sign
        if pct >= 0 and show_positive_sign:
            return f"+{pct:.{decimal_places}f}%"
        else:
            return f"{pct:.{decimal_places}f}%"
    
    async def convert_context_to_krw(
        self,
        symbol: str,
        context: Dict
    ) -> Dict:
        """
        Convert all price fields in context dict to KRW
        
        Args:
            symbol: Asset symbol
            context: Context dict with price fields
        
        Returns:
            Context dict with prices in KRW
        """
        # Detect asset currency
        currency = self.get_asset_currency(symbol)
        
        # Fields to convert
        price_fields = [
            'current_price', 'price', 'open', 'high', 'low', 'close',
            'ma5', 'ma15', 'ma20', 'ma50', 'ma200',
            'support', 'resistance',
            'stop_loss', 'take_profit', 'take_profit_1', 'take_profit_2',
            'entry_price', 'exit_price'
        ]
        
        # Convert each price field
        converted = context.copy()
        for field in price_fields:
            if field in converted and converted[field] is not None:
                try:
                    original = float(converted[field])
                    converted[field] = await self.convert_to_krw(original, currency)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to convert {field}: {e}")
        
        return converted


# Singleton instance
_converter_instance: Optional[CurrencyConverter] = None


def get_converter() -> CurrencyConverter:
    """
    Get singleton currency converter instance
    
    Returns:
        CurrencyConverter instance
    """
    global _converter_instance
    if _converter_instance is None:
        _converter_instance = CurrencyConverter()
    return _converter_instance


# Convenience functions
async def convert_to_krw(amount: float, from_currency: str) -> float:
    """Convert amount to KRW"""
    converter = get_converter()
    return await converter.convert_to_krw(amount, from_currency)


async def convert_price(symbol: str, price: float) -> float:
    """Convert asset price to KRW"""
    converter = get_converter()
    return await converter.convert_price(symbol, price)


def format_krw(amount: float) -> str:
    """Format KRW amount"""
    converter = get_converter()
    return converter.format_krw(amount)


def format_change(change_pct: float) -> str:
    """Format percentage change"""
    converter = get_converter()
    return converter.format_change(change_pct)


# CLI test
if __name__ == "__main__":
    async def test():
        """Test currency converter"""
        converter = CurrencyConverter()
        
        print("🧪 Testing Currency Converter\n")
        
        # Test 1: Update rates
        print("1️⃣ Updating exchange rates...")
        success = await converter.update_rates()
        print(f"   {'✅ Success' if success else '⚠️ Using fallback rates'}\n")
        
        # Test 2: Asset currency detection
        print("2️⃣ Testing asset currency detection:")
        test_symbols = ["AAPL", "005930.KS", "BTC-USD", "KRW-BTC"]
        for symbol in test_symbols:
            currency = converter.get_asset_currency(symbol)
            print(f"   {symbol} -> {currency}")
        print()
        
        # Test 3: Currency conversion
        print("3️⃣ Testing currency conversion:")
        test_amounts = [
            (100, "USD"),
            (178.50, "USD"),
            (75000, "KRW"),
            (10000, "JPY")
        ]
        for amount, currency in test_amounts:
            krw = await converter.convert_to_krw(amount, currency)
            formatted = converter.format_krw(krw)
            print(f"   {amount} {currency} = {formatted}")
        print()
        
        # Test 4: Price conversion
        print("4️⃣ Testing asset price conversion:")
        test_prices = [
            ("AAPL", 178.50),
            ("005930.KS", 75000),
            ("BTC-USD", 89445)
        ]
        for symbol, price in test_prices:
            krw = await converter.convert_price(symbol, price)
            formatted = converter.format_krw(krw)
            currency = converter.get_asset_currency(symbol)
            print(f"   {symbol}: {price} {currency} = {formatted}")
        print()
        
        # Test 5: Percentage formatting
        print("5️⃣ Testing percentage formatting:")
        test_pcts = [0.0235, -0.0147, 0.05, -0.02]
        for pct in test_pcts:
            formatted = converter.format_change(pct)
            print(f"   {pct} = {formatted}")
        print()
        
        print("✅ All tests completed!")
    
    asyncio.run(test())
