"""
韩国股票数据获取器 V2（pykrx 主导版）
"""
import asyncio
import redis
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger

try:
    from pykrx import stock as pykrx_stock
    PYKRX_AVAILABLE = True
    logger.info("✅ pykrx 已加载")
except ImportError:
    PYKRX_AVAILABLE = False
    logger.error("❌ pykrx 未安装")
    raise ImportError("pykrx is required")

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


class KoreanStockFetcherV2:
    """韩国股票数据获取器 V2"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.price_cache_ttl = timedelta(seconds=30)
        self.name_cache_ttl = timedelta(days=1)
        
        self.yahoo_queried = set()
        
        self.stock_names_kr = {
            '005930': '삼성전자',
            '000660': 'SK하이닉스',
            '035420': 'NAVER',
            '035720': '카카오',
            '051910': 'LG화학',
        }
        
        self.stats = {
            'pykrx_calls': 0,
            'pykrx_success': 0,
            'cache_hits': 0,
            'local_fallback': 0,
            'yahoo_fallback': 0,
        }
        
        logger.info("✅ KoreanStockFetcherV2 初始化")
    
    async def get_stock_name(self, symbol: str) -> str:
        """获取股票名称"""
        base_code = symbol.replace('.KS', '').replace('.KQ', '').upper()
        
        # 1. 缓存
        cached = self._get_name_from_cache(base_code)
        if cached:
            self.stats['cache_hits'] += 1
            return cached
        
        # 2. pykrx
        try:
            name = await asyncio.to_thread(
                pykrx_stock.get_market_ticker_name, base_code
            )
            if name:
                self._save_name_to_cache(base_code, name)
                self.stats['pykrx_success'] += 1
                return name
        except:
            pass
        
        # 3. 本地映射
        if base_code in self.stock_names_kr:
            name = self.stock_names_kr[base_code]
            self.stats['local_fallback'] += 1
            self._save_name_to_cache(base_code, name)
            return name
        
        return "Unknown"
    
    async def get_stock_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取股票价格"""
        base_code = symbol.replace('.KS', '').replace('.KQ', '').upper()
        
        # 1. 缓存
        cached = self._get_price_from_cache(base_code)
        if cached:
            self.stats['cache_hits'] += 1
            return cached
        
        # 2. pykrx
        self.stats['pykrx_calls'] += 1
        
        try:
            today = datetime.now().strftime("%Y%m%d")
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
            
            df = await asyncio.to_thread(
                pykrx_stock.get_market_ohlcv_by_date,
                week_ago, today, base_code
            )
            
            if not df.empty:
                latest = df.iloc[-1]
                
                # 计算涨跌幅
                if len(df) >= 2:
                    prev_close = df.iloc[-2]['종가']
                    change = ((latest['종가'] - prev_close) / prev_close) * 100
                else:
                    change = 0
                
                price_data = {
                    'price': int(latest['종가']),
                    'change': round(change, 2),
                    'volume': int(latest['거래량']),
                    'open': int(latest['시가']),
                    'high': int(latest['고가']),
                    'low': int(latest['저가']),
                    'market_cap': 0,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'source': 'pykrx'
                }
                
                self.stats['pykrx_success'] += 1
                self._save_price_to_cache(base_code, price_data)
                
                logger.info(f"✅ {base_code}: ₩{price_data['price']:,} ({price_data['change']:+.2f}%)")
                return price_data
        except Exception as e:
            logger.error(f"❌ {base_code} 价格获取失败: {e}")
        
        return None
    
    async def get_multiple_stocks(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量获取"""
        tasks = []
        for symbol in symbols:
            tasks.append(self._get_stock_full_data(symbol))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        stock_data = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, dict):
                stock_data[symbol] = result
        
        return stock_data
    
    async def _get_stock_full_data(self, symbol: str) -> Dict[str, Any]:
        """获取完整数据"""
        name_task = self.get_stock_name(symbol)
        price_task = self.get_stock_price(symbol)
        
        name, price_data = await asyncio.gather(name_task, price_task)
        
        return {
            'symbol': symbol,
            'name': name,
            'price_data': price_data
        }
    
    def _get_name_from_cache(self, code: str) -> Optional[str]:
        if not self.redis:
            return None
        try:
            return self.redis.get(f"kr_stock_name_v2:{code}")
        except:
            return None
    
    def _save_name_to_cache(self, code: str, name: str):
        if self.redis:
            try:
                self.redis.setex(f"kr_stock_name_v2:{code}", self.name_cache_ttl, name)
            except:
                pass
    
    def _get_price_from_cache(self, code: str) -> Optional[Dict[str, Any]]:
        if not self.redis:
            return None
        try:
            import json
            cached = self.redis.get(f"kr_stock_price_v2:{code}")
            if cached:
                return json.loads(cached)
        except:
            return None
    
    def _save_price_to_cache(self, code: str, price_data: Dict[str, Any]):
        if self.redis:
            try:
                import json
                self.redis.setex(
                    f"kr_stock_price_v2:{code}",
                    self.price_cache_ttl,
                    json.dumps(price_data)
                )
            except:
                pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        total = self.stats['pykrx_calls']
        return {
            **self.stats,
            'pykrx_success_rate': (self.stats['pykrx_success'] / total * 100) if total > 0 else 0,
        }


# 测试
if __name__ == '__main__':
    async def test():
        print("🧪 测试韩国股票数据获取器 V2")
        print("="*60)
        
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        fetcher = KoreanStockFetcherV2(r)
        
        test_stocks = ['005930', '035420', '035720']
        
        print("\n1️⃣ 测试名称获取:")
        for symbol in test_stocks:
            name = await fetcher.get_stock_name(symbol)
            print(f"   {symbol:8s} -> {name}")
        
        print("\n2️⃣ 测试价格获取:")
        for symbol in test_stocks:
            price_data = await fetcher.get_stock_price(symbol)
            if price_data:
                print(f"   {symbol:8s} -> ₩{price_data['price']:,} ({price_data['change']:+.2f}%)")
        
        print("\n3️⃣ 统计信息:")
        stats = fetcher.get_stats()
        print(f"   pykrx 调用: {stats['pykrx_calls']}次")
        print(f"   成功率: {stats['pykrx_success_rate']:.1f}%")
        print(f"   Yahoo 回退: {stats['yahoo_fallback']}次")
        
        print("\n" + "="*60)
        print("✅ 测试完成")
    
    asyncio.run(test())
