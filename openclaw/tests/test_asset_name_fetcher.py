"""
Test real-time asset name fetching
"""
import pytest
import asyncio
from openclaw.core.database import DatabaseManager
from openclaw.skills.monitoring.asset_name_fetcher import AssetNameFetcher


class TestAssetNameFetcher:
    """Test asset name fetching functionality"""
    
    @pytest.mark.asyncio
    async def test_korean_stock_names(self):
        """Test fetching Korean stock names from Yahoo Finance"""
        db = DatabaseManager()
        
        async with AssetNameFetcher(db) as fetcher:
            # Test individual fetch
            name = await fetcher.get_asset_name('005930.KS')
            assert name is not None
            assert isinstance(name, str)
            assert len(name) > 0
            # Should contain "Samsung" or use fallback
            assert 'Samsung' in name or 'Unknown' not in name
            
            print(f"✅ Samsung stock name: {name}")
    
    @pytest.mark.asyncio
    async def test_multiple_korean_stocks(self):
        """Test batch fetching of Korean stock names"""
        db = DatabaseManager()
        
        async with AssetNameFetcher(db) as fetcher:
            # Test batch fetch
            symbols = ['005930.KS', '035420.KS', '000660.KS']
            names = await fetcher.get_multiple_names(symbols)
            
            assert len(names) == 3
            assert all(symbol in names for symbol in symbols)
            assert all(names[symbol] for symbol in symbols)
            
            print("✅ Fetched multiple stock names:")
            for symbol, name in names.items():
                print(f"   {symbol}: {name}")
    
    @pytest.mark.asyncio
    async def test_crypto_names(self):
        """Test fetching cryptocurrency names from CoinGecko"""
        db = DatabaseManager()
        
        async with AssetNameFetcher(db) as fetcher:
            # Test Bitcoin
            btc_name = await fetcher.get_asset_name('BTC')
            assert btc_name is not None
            assert 'Bitcoin' in btc_name or btc_name == 'Bitcoin'
            
            print(f"✅ Bitcoin name: {btc_name}")
            
            # Test Ethereum with Upbit format
            eth_name = await fetcher.get_asset_name('KRW-ETH')
            assert eth_name is not None
            assert 'Ethereum' in eth_name or eth_name == 'Ethereum'
            
            print(f"✅ Ethereum name: {eth_name}")
    
    @pytest.mark.asyncio
    async def test_mixed_assets(self):
        """Test fetching mixed stock and crypto names"""
        db = DatabaseManager()
        
        async with AssetNameFetcher(db) as fetcher:
            symbols = ['005930.KS', 'KRW-BTC', 'ETH', '035420.KS']
            names = await fetcher.get_multiple_names(symbols)
            
            assert len(names) == 4
            assert all(names[symbol] for symbol in symbols)
            
            print("✅ Fetched mixed asset names:")
            for symbol, name in names.items():
                print(f"   {symbol}: {name}")
    
    @pytest.mark.asyncio
    async def test_caching(self):
        """Test Redis caching functionality"""
        db = DatabaseManager()
        
        async with AssetNameFetcher(db) as fetcher:
            symbol = '005930.KS'
            
            # First fetch (should hit API)
            name1 = await fetcher.get_asset_name(symbol)
            
            # Second fetch (should hit cache)
            name2 = await fetcher.get_asset_name(symbol)
            
            # Names should be identical
            assert name1 == name2
            
            # Check cache directly
            cache_key = fetcher._get_cache_key(symbol)
            cached_value = db.get(cache_key)
            assert cached_value == name1
            
            print(f"✅ Caching works: {name1}")
    
    @pytest.mark.asyncio
    async def test_fallback_mechanism(self):
        """Test fallback to local mappings"""
        db = DatabaseManager()
        
        async with AssetNameFetcher(db) as fetcher:
            # Test with invalid symbol that should use fallback
            # First, test that known fallback symbols work
            fallback_code = '005930'
            fallback_symbol = f'{fallback_code}.KS'
            
            name = await fetcher.get_asset_name(fallback_symbol)
            
            # Should get either API result or fallback, not "Unknown"
            assert name is not None
            assert len(name) > 0
            
            print(f"✅ Fallback test passed: {fallback_symbol} -> {name}")
    
    @pytest.mark.asyncio
    async def test_unknown_symbol(self):
        """Test handling of unknown symbols"""
        db = DatabaseManager()
        
        async with AssetNameFetcher(db) as fetcher:
            # Test with completely invalid symbol
            unknown_symbol = 'INVALID999.KS'
            name = await fetcher.get_asset_name(unknown_symbol)
            
            # Should get "Unknown Asset" message
            assert name is not None
            assert 'Unknown' in name or 'INVALID999' in name
            
            print(f"✅ Unknown symbol handled: {unknown_symbol} -> {name}")
    
    def test_symbol_normalization(self):
        """Test symbol normalization logic"""
        db = DatabaseManager()
        fetcher = AssetNameFetcher(db)
        
        # Test Upbit format normalization
        assert fetcher._normalize_symbol('KRW-BTC') == 'BTC'
        assert fetcher._normalize_symbol('krw-eth') == 'ETH'
        assert fetcher._normalize_symbol('BTC') == 'BTC'
        assert fetcher._normalize_symbol('005930.KS') == '005930.KS'
        
        print("✅ Symbol normalization works correctly")
    
    def test_asset_type_detection(self):
        """Test asset type detection logic"""
        db = DatabaseManager()
        fetcher = AssetNameFetcher(db)
        
        # Korean stocks
        assert fetcher._is_korean_stock('005930.KS') == True
        assert fetcher._is_korean_stock('035420.KQ') == True
        
        # Cryptocurrencies
        assert fetcher._is_crypto('BTC') == True
        assert fetcher._is_crypto('KRW-ETH') == True
        
        # Mixed
        assert fetcher._is_korean_stock('BTC') == False
        assert fetcher._is_crypto('005930.KS') == False
        
        print("✅ Asset type detection works correctly")


# Run individual test for debugging
if __name__ == '__main__':
    async def run_test():
        """Run a quick test"""
        db = DatabaseManager()
        async with AssetNameFetcher(db) as fetcher:
            # Test Korean stock
            samsung = await fetcher.get_asset_name('005930.KS')
            print(f"Samsung: {samsung}")
            
            # Test crypto
            btc = await fetcher.get_asset_name('BTC')
            print(f"Bitcoin: {btc}")
            
            # Test batch
            symbols = ['005930.KS', 'KRW-BTC', 'ETH']
            names = await fetcher.get_multiple_names(symbols)
            print("\nBatch fetch:")
            for sym, name in names.items():
                print(f"  {sym}: {name}")
    
    asyncio.run(run_test())
