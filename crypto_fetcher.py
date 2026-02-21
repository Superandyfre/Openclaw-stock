#!/usr/bin/env python3
"""
韩国加密货币数据获取器
支持 Upbit (업비트) 和 Bithumb (비썸)
"""
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger

# Upbit
try:
    import pyupbit
    UPBIT_AVAILABLE = True
except ImportError:
    UPBIT_AVAILABLE = False
    logger.error("pyupbit 未安装")

# Bithumb
try:
    import pybithumb
    BITHUMB_AVAILABLE = True
except ImportError:
    BITHUMB_AVAILABLE = False
    logger.error("pybithumb 未安装")


class CryptoDataFetcher:
    """加密货币数据获取器"""
    
    def __init__(self):
        self.upbit_available = UPBIT_AVAILABLE
        self.bithumb_available = BITHUMB_AVAILABLE
        
        # 缓存
        self.upbit_markets_cache = None
        self.bithumb_markets_cache = None
        
        # 统计
        self.stats = {
            'upbit_calls': 0,
            'upbit_success': 0,
            'bithumb_calls': 0,
            'bithumb_success': 0,
        }
        
        logger.info("✅ CryptoDataFetcher 初始化成功")
        logger.info(f"   Upbit: {'✅' if self.upbit_available else '❌'}")
        logger.info(f"   Bithumb: {'✅' if self.bithumb_available else '❌'}")
    
    # ==========================================
    # Upbit (업비트)
    # ==========================================
    
    async def get_upbit_markets(self) -> List[str]:
        """获取 Upbit 所有 KRW 交易对"""
        if not self.upbit_available:
            return []
        
        if self.upbit_markets_cache:
            return self.upbit_markets_cache
        
        try:
            # 获取所有市场
            all_markets = await asyncio.to_thread(pyupbit.get_tickers, fiat="KRW")
            
            self.upbit_markets_cache = all_markets
            logger.info(f"✅ Upbit: 发现 {len(all_markets)} 个 KRW 交易对")
            
            return all_markets
            
        except Exception as e:
            logger.error(f"获取 Upbit 市场列表失败: {e}")
            return []
    
    async def get_upbit_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取 Upbit 单个币种价格"""
        if not self.upbit_available:
            return None
        
        try:
            self.stats['upbit_calls'] += 1
            
            # 确保格式正确 (KRW-BTC)
            if not symbol.startswith('KRW-'):
                symbol = f'KRW-{symbol}'
            
            # 获取当前价格
            ticker = await asyncio.to_thread(pyupbit.get_current_price, symbol)
            
            if ticker is None:
                return None
            
            # 获取 OHLCV 数据（用于计算涨跌幅）
            df = await asyncio.to_thread(
                pyupbit.get_ohlcv,
                symbol,
                interval="day",
                count=2
            )
            
            if df is None or df.empty:
                change_pct = 0
            else:
                if len(df) >= 2:
                    prev_close = df.iloc[-2]['close']
                    curr_close = df.iloc[-1]['close']
                    change_pct = ((curr_close - prev_close) / prev_close) * 100
                else:
                    change_pct = 0
            
            price_data = {
                'symbol': symbol,
                'exchange': 'upbit',
                'price': float(ticker),
                'change': round(change_pct, 2),
                'volume': 0,  # Upbit API 限制
                'timestamp': datetime.now().isoformat(),
            }
            
            self.stats['upbit_success'] += 1
            return price_data
            
        except Exception as e:
            logger.debug(f"Upbit {symbol} 获取失败: {e}")
            return None
    
    async def get_upbit_all_prices(self) -> Dict[str, Dict[str, Any]]:
        """获取 Upbit 所有币种价格"""
        if not self.upbit_available:
            return {}
        
        try:
            # 获取所有市场
            markets = await self.get_upbit_markets()
            
            if not markets:
                return {}
            
            logger.info(f"📊 Upbit: 开始获取 {len(markets)} 个交易对价格...")
            
            # 批量获取当前价格
            tickers = await asyncio.to_thread(pyupbit.get_current_price, markets)
            
            if not tickers:
                return {}
            
            # 获取前一天收盘价（用于计算涨跌幅）
            prices = {}
            
            for symbol, price in tickers.items():
                if price is None:
                    continue
                
                try:
                    # 获取历史数据计算涨跌幅
                    df = await asyncio.to_thread(
                        pyupbit.get_ohlcv,
                        symbol,
                        interval="day",
                        count=2
                    )
                    
                    if df is not None and not df.empty and len(df) >= 2:
                        prev_close = df.iloc[-2]['close']
                        change_pct = ((price - prev_close) / prev_close) * 100
                        volume = df.iloc[-1]['volume']
                    else:
                        change_pct = 0
                        volume = 0
                    
                    prices[symbol] = {
                        'symbol': symbol,
                        'exchange': 'upbit',
                        'price': float(price),
                        'change': round(change_pct, 2),
                        'volume': float(volume),
                        'timestamp': datetime.now().isoformat(),
                    }
                    
                    self.stats['upbit_success'] += 1
                    
                except Exception as e:
                    logger.debug(f"Upbit {symbol} 处理失败: {e}")
                    continue
            
            logger.info(f"✅ Upbit: 成功获取 {len(prices)} 个交易对价格")
            return prices
            
        except Exception as e:
            logger.error(f"Upbit 批量获取失败: {e}")
            return {}
    
    # ==========================================
    # Bithumb (비썸)
    # ==========================================
    
    async def get_bithumb_markets(self) -> List[str]:
        """获取 Bithumb 所有交易对"""
        if not self.bithumb_available:
            return []
        
        if self.bithumb_markets_cache:
            return self.bithumb_markets_cache
        
        try:
            # Bithumb 支持的币种
            all_coins = await asyncio.to_thread(pybithumb.get_tickers)
            
            self.bithumb_markets_cache = all_coins
            logger.info(f"✅ Bithumb: 发现 {len(all_coins)} 个交易对")
            
            return all_coins
            
        except Exception as e:
            logger.error(f"获取 Bithumb 市场列表失败: {e}")
            return []
    
    async def get_bithumb_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取 Bithumb 单个币种实时价格（优先尝试 ALL 接口，失败则降级查询单币）"""
        if not self.bithumb_available:
            return None

        try:
            self.stats['bithumb_calls'] += 1
            clean_symbol = symbol.replace('KRW-', '').upper()

            # 1. 尝试调用 ALL 接口（为了获取涨跌幅等详细数据）
            try:
                raw = await asyncio.to_thread(pybithumb.get_current_price, 'ALL')
            except Exception:
                raw = None

            price = 0.0
            change_pct = 0.0
            volume = 0.0

            # 2. 从 ALL 数据中提取
            if isinstance(raw, dict) and clean_symbol in raw:
                data = raw[clean_symbol]
                price = float(data.get('closing_price', 0))
                # Bithumb API 返回的是 24H 变动率 ('24H_fluctate_rate')
                # 或者手动计算: (closing - prev_closing) / prev_closing
                prev_close = float(data.get('prev_closing_price', 0))
                if prev_close > 0:
                    change_pct = ((price - prev_close) / prev_close * 100)
                else:
                    change_pct = float(data.get('24H_fluctate_rate', 0))
                
                volume = float(data.get('units_traded_24H', 0)) # 24H 成交量(币)
            
            # 3. 如果 ALL 接口失败或未找到，尝试单独查询该币种
            if price <= 0:
                try:
                    # pybithumb.get_current_price(sym) 只返回价格 float
                    single_price = await asyncio.to_thread(pybithumb.get_current_price, clean_symbol)
                    if single_price is not None:
                        price = float(single_price)
                        # 单独查询时难以获取涨跌幅，尝试获取市场详情 (get_market_detail)
                        # 注意：get_market_detail 可能比较慢，这就作为兜底
                        detail = await asyncio.to_thread(pybithumb.get_market_detail, clean_symbol)
                        # detail returns (open, high, low, close, volume)
                        if detail:
                            # detail[0]=open, [1]=high, [2]=low, [3]=close, [4]=volume
                            open_price = float(detail[0])
                            if open_price > 0:
                                change_pct = ((price - open_price) / open_price * 100)
                            volume = float(detail[4])
                except Exception as _detail_e:
                    logger.debug(f"Bithumb 单币查询详情失败: {_detail_e}")

            if price <= 0:
                # 最后的尝试：如果是 'SNX' 这种 Bithumb 有但暂时查不到的，也不要轻易放弃，
                # 但如果连价格都拿不到，实在没办法，只能返回 None 让上层切 Upbit
                return None

            self.stats['bithumb_success'] += 1
            return {
                'symbol':     f'KRW-{clean_symbol}',
                'exchange':   'bithumb',
                'price':      price,
                'change_pct': round(change_pct, 2),
                'change':     round(change_pct, 2),
                'volume':     volume,
                'timestamp':  datetime.now().isoformat(),
            }

        except Exception as e:
            logger.debug(f"Bithumb {symbol} 获取失败: {e}")
            return None
    
    async def get_bithumb_all_prices(self) -> Dict[str, Dict[str, Any]]:
        """获取 Bithumb 所有币种价格"""
        if not self.bithumb_available:
            return {}
        
        try:
            # 获取所有市场
            markets = await self.get_bithumb_markets()
            
            if not markets:
                return {}
            
            logger.info(f"📊 Bithumb: 开始获取 {len(markets)} 个交易对价格...")
            
            prices = {}
            
            # Bithumb 批量获取
            tasks = []
            for symbol in markets:
                tasks.append(self.get_bithumb_price(symbol))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for symbol, result in zip(markets, results):
                if isinstance(result, dict):
                    prices[result['symbol']] = result
            
            logger.info(f"✅ Bithumb: 成功获取 {len(prices)} 个交易对价格")
            return prices
            
        except Exception as e:
            logger.error(f"Bithumb 批量获取失败: {e}")
            return {}
    
    # ==========================================
    # 综合功能
    # ==========================================
    
    async def get_all_crypto_prices(self) -> Dict[str, Dict[str, Any]]:
        """获取所有交易所的所有加密货币价格"""
        logger.info("🚀 开始获取所有加密货币价格...")
        
        # 并发获取两个交易所的数据
        tasks = []
        
        if self.upbit_available:
            tasks.append(self.get_upbit_all_prices())
        
        if self.bithumb_available:
            tasks.append(self.get_bithumb_all_prices())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 合并结果
        all_prices = {}
        
        for result in results:
            if isinstance(result, dict):
                all_prices.update(result)
        
        logger.info(f"✅ 总共获取 {len(all_prices)} 个加密货币价格")
        
        return all_prices
    
    async def get_top_cryptos(self, limit: int = 50) -> Dict[str, Dict[str, Any]]:
        """获取市值排名前 N 的加密货币"""
        all_prices = await self.get_all_crypto_prices()
        
        # 按价格*交易量排序（粗略估算市值）
        sorted_prices = sorted(
            all_prices.items(),
            key=lambda x: x[1].get('price', 0) * x[1].get('volume', 0),
            reverse=True
        )
        
        # 返回前 N 个
        top_prices = dict(sorted_prices[:limit])
        
        logger.info(f"✅ 返回市值前 {len(top_prices)} 的加密货币")
        
        return top_prices
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            'upbit_success_rate': (
                self.stats['upbit_success'] / self.stats['upbit_calls'] * 100
                if self.stats['upbit_calls'] > 0 else 0
            ),
            'bithumb_success_rate': (
                self.stats['bithumb_success'] / self.stats['bithumb_calls'] * 100
                if self.stats['bithumb_calls'] > 0 else 0
            )
        }


# ==========================================
# 测试
# ==========================================

async def test():
    """测试加密货币数据获取"""
    print("🧪 测试加密货币数据获取器")
    print("="*70)
    
    fetcher = CryptoDataFetcher()
    
    # 测试 1: 获取市场列表
    print("\n1️⃣ 获取市场列表:")
    upbit_markets = await fetcher.get_upbit_markets()
    print(f"   Upbit: {len(upbit_markets)} 个交易对")
    if upbit_markets:
        print(f"   示例: {', '.join(upbit_markets[:5])}")
    
    bithumb_markets = await fetcher.get_bithumb_markets()
    print(f"   Bithumb: {len(bithumb_markets)} 个交易对")
    if bithumb_markets:
        print(f"   示例: {', '.join(bithumb_markets[:5])}")
    
    # 测��� 2: 获取单个价格
    print("\n2️⃣ 获取单个价格:")
    
    btc_upbit = await fetcher.get_upbit_price('KRW-BTC')
    if btc_upbit:
        print(f"   Upbit BTC: ₩{btc_upbit['price']:,.0f} ({btc_upbit['change']:+.2f}%)")
    
    btc_bithumb = await fetcher.get_bithumb_price('BTC')
    if btc_bithumb:
        print(f"   Bithumb BTC: ₩{btc_bithumb['price']:,.0f} ({btc_bithumb['change']:+.2f}%)")
    
    # 测试 3: 获取前 20 名
    print("\n3️⃣ 获取市值前 20 名:")
    top_20 = await fetcher.get_top_cryptos(limit=20)
    
    for i, (symbol, data) in enumerate(top_20.items(), 1):
        emoji = "🟢" if data['change'] > 0 else "🔴" if data['change'] < 0 else "⚪"
        print(f"   {i:2d}. {emoji} {symbol:15s} ({data['exchange']:8s}): "
              f"₩{data['price']:>12,.0f} ({data['change']:+6.2f}%)")
    
    # 统计
    print("\n4️⃣ 统计信息:")
    stats = fetcher.get_stats()
    print(f"   Upbit 调用: {stats['upbit_calls']} 次，成功率: {stats['upbit_success_rate']:.1f}%")
    print(f"   Bithumb 调用: {stats['bithumb_calls']} 次，成功率: {stats['bithumb_success_rate']:.1f}%")
    
    print("\n" + "="*70)
    print("✅ 测试完成")


if __name__ == '__main__':
    import sys
    from loguru import logger
    
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    asyncio.run(test())
