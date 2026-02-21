#!/usr/bin/env python3
"""
美股和港股数据获取器
- 美股: 优先 Alpaca WebSocket 实时推送（免费 IEX，<1秒延迟）
        回退 Finnhub REST（免费版 NYSE 有 15 分钟延迟）
- 港股: 优先 FUTU OpenAPI WebSocket 实时推送（免费，<1秒延迟）
        回退 yfinance（15 分钟延迟）
"""
import asyncio
import os
from typing import Dict, List, Optional, Any
from loguru import logger

try:
    from openclaw.skills.data_collection.alpaca_ws_client import AlpacaWSClient
    ALPACA_WS_AVAILABLE = True
except ImportError:
    ALPACA_WS_AVAILABLE = False

try:
    from openclaw.skills.data_collection.futu_hk_client import FutuHKClient
    FUTU_AVAILABLE = True
except ImportError:
    FUTU_AVAILABLE = False

try:
    import finnhub
    FINNHUB_AVAILABLE = True
except ImportError:
    FINNHUB_AVAILABLE = False
    logger.warning("finnhub未安装，请运行: pip install finnhub-python")

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance未安装（港股数据源），请运行: pip install yfinance")


class USHKStockFetcher:
    """美股和港股数据获取器
    美股: Alpaca WS → Finnhub REST
    港股: FUTU WS → yfinance
    """
    
    # 常用美股符号
    US_STOCKS = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 
        'NFLX', 'AMD', 'INTC', 'JPM', 'BAC', 'GS', 'V', 'MA',
        'DIS', 'NIKE', 'MCD', 'SBUX', 'KO', 'PEP', 'WMT', 'HD',
        'UNH', 'JNJ', 'PFE', 'MRNA', 'XOM', 'CVX', 'COP'
    ]
    
    # 常用港股符号（yfinance格式）
    HK_STOCKS = [
        '0700.HK',   # 腾讯
        '9988.HK',   # 阿里巴巴
        '3690.HK',   # 美团
        '9618.HK',   # 京东
        '1810.HK',   # 小米
        '2318.HK',   # 中国平安
        '1299.HK',   # 友邦保险
        '0939.HK',   # 建设银行
        '3988.HK',   # 中国银行
        '0941.HK',   # 中国移动
    ]
    
    def __init__(self):
        """初始化数据获取器"""
        self.finnhub_available = FINNHUB_AVAILABLE
        self.yfinance_available = YFINANCE_AVAILABLE
        self.available = self.finnhub_available or self.yfinance_available
        self.finnhub_client = None

        # ── Alpaca WebSocket 客户端（美股实时推送，优先级最高）──
        self.alpaca_ws: Optional['AlpacaWSClient'] = None
        if ALPACA_WS_AVAILABLE:
            ak = os.getenv('ALPACA_API_KEY', '')
            sk = os.getenv('ALPACA_SECRET_KEY', '')
            if ak and sk and ak != 'your_alpaca_api_key':
                self.alpaca_ws = AlpacaWSClient(ak, sk)
                logger.info("✅ AlpacaWSClient 已创建（调用 start_alpaca_ws() 启动推送）")
            else:
                logger.info("ℹ️  未配置 ALPACA_API_KEY，美股将使用 Finnhub REST")

        # ── Finnhub（美股 REST 兜底）──
        if self.finnhub_available:
            api_key = os.getenv('FINNHUB_API_KEY')
            if api_key:
                try:
                    self.finnhub_client = finnhub.Client(api_key=api_key)
                    logger.info("✅ Finnhub客户端初始化成功（美股 REST 兜底）")
                except Exception as e:
                    logger.error(f"Finnhub客户端初始化失败: {e}")
                    self.finnhub_available = False
            else:
                logger.warning("未找到FINNHUB_API_KEY环境变量")
                self.finnhub_available = False

        # ── FUTU OpenAPI（港股实时推送，优先级最高）──
        self.futu_client: Optional['FutuHKClient'] = None
        if FUTU_AVAILABLE:
            futu_host = os.getenv('FUTU_OPEND_HOST', '127.0.0.1')
            futu_port = int(os.getenv('FUTU_OPEND_PORT', '11111'))
            self.futu_client = FutuHKClient(host=futu_host, port=futu_port)
            logger.info("✅ FutuHKClient 已创建（调用 start_futu_ws() 启动推送）")

        # ── yfinance（港股 REST 兜底）──
        if self.yfinance_available:
            logger.info("✅ yfinance可用（港股 REST 兜底）")

        if not self.available:
            logger.error("无可用的数据源")
    
    async def start_alpaca_ws(self, symbols: Optional[List[str]] = None) -> None:
        """
        启动 Alpaca WebSocket 后台推送任务。
        应在 bot 的 async run() 方法内调用，确保处于 asyncio 事件循环中。

        Args:
            symbols: 要订阅的美股代码列表，默认使用 US_STOCKS 常用列表
        """
        if not self.alpaca_ws:
            logger.info("Alpaca WS 未配置，跳过启动")
            return
        if self.alpaca_ws.is_running:
            logger.info("Alpaca WS 已在运行")
            return

        target_symbols = [s.upper() for s in (symbols or self.US_STOCKS)]

        # 从 Finnhub REST 预取前收盘价，供 WS 计算涨跌幅
        if self.finnhub_client:
            logger.info(f"预取 {len(target_symbols)} 只股票前收盘价...")
            for sym in target_symbols[:20]:   # 只预取常用的前20只，避免超限
                try:
                    q = await asyncio.to_thread(self.finnhub_client.quote, sym)
                    pc = q.get('pc', 0)
                    if pc:
                        self.alpaca_ws.set_prev_close(sym, pc)
                except Exception:
                    pass
                await asyncio.sleep(0.05)   # 60次/分钟限速

        self.alpaca_ws.start(target_symbols)
        logger.info(f"✅ Alpaca WebSocket 实时推送已启动，订阅 {len(target_symbols)} 只美股")

    def start_futu_ws(self, symbols: Optional[List[str]] = None) -> None:
        """
        启动 FUTU 港股实时推送（后台线程，非 async）。
        在 bot 启动时调用即可，FutuOpenD 必须已在本机运行。

        Args:
            symbols: 要订阅的港股代码列表，默认使用 HK_STOCKS 常用列表
        """
        if not self.futu_client:
            logger.info("FUTU 客户端未初始化（futu-api 未安装或配置缺失），跳过")
            return
        if self.futu_client.is_running:
            logger.info("FUTU 客户端已在运行")
            return

        target = symbols or [
            s.replace('.HK', '').replace('0700', '00700') for s in self.HK_STOCKS
        ]
        self.futu_client.start(target)

    def _format_hk_symbol(self, symbol: str) -> str:
        """格式化港股符号（yfinance格式）
        
        Args:
            symbol: 港股代码，如 '00700', '0700', '700' 或 '0700.HK'
            
        Returns:
            yfinance格式，如 '0700.HK'
        """
        # 移除HK后缀（如果有）
        symbol = symbol.replace('.HK', '').replace('.hk', '')
        
        # 移除前导零后再格式化
        if symbol.isdigit():
            symbol = str(int(symbol))  # 去掉前导零
        
        return f"{symbol}.HK"
    
    def get_us_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取美股信息。

        优先级：
          1. Alpaca WebSocket 实时缓存（<1秒，IEX 数据）
          2. Finnhub REST 兜底（免费版 NYSE 延迟 15 分钟）

        Args:
            symbol: 美股代码，如 'AAPL'

        Returns:
            股票信息字典，或 None（两个数据源均不可用时）
        """
        sym = symbol.upper()

        # ── 优先：Alpaca WebSocket 缓存 ──
        if self.alpaca_ws and self.alpaca_ws.is_running:
            cached = self.alpaca_ws.get_cached_price(sym)
            if cached:
                price      = cached['price']
                change_pct = cached['change_pct']
                prev_close = self.alpaca_ws._prev_close.get(sym, price)
                change     = price - prev_close
                logger.debug(f"[Alpaca-WS] {sym} ₩{price} ({change_pct:+.2f}%) 来源={cached['source']}")
                return {
                    'symbol':         sym,
                    'name':           sym,
                    'price':          price,
                    'change':         change,
                    'change_percent': change_pct,
                    'volume':         cached.get('volume', 0),
                    'market_cap':     0,
                    'high':           cached.get('high', 0),
                    'low':            cached.get('low', 0),
                    'open':           cached.get('open', 0),
                    'prev_close':     prev_close,
                    'currency':       'USD',
                    'exchange':       'IEX',
                    'source':         cached['source'],
                }
            # WS 在运行但该 symbol 尚无缓存（刚订阅或市场收盘）
            # → 同时将其加入订阅，下次就有了
            self.alpaca_ws.subscribe([sym])

        # ── 兜底：Finnhub REST ──
        if not self.finnhub_available or not self.finnhub_client:
            logger.warning(f"Finnhub不可用，且Alpaca WS无缓存，无法获取 {sym} 价格")
            return None

        try:
            # 获取实时报价
            quote = self.finnhub_client.quote(sym)

            # 获取公司信息（含交易所、市值）
            try:
                profile   = self.finnhub_client.company_profile2(symbol=sym)
                name      = profile.get('name', sym)
                market_cap = profile.get('marketCapitalization', 0) * 1_000_000
                exchange  = profile.get('exchange', 'NASDAQ/NYSE')
            except Exception:
                name       = sym
                market_cap = 0
                exchange   = 'NASDAQ/NYSE'

            current_price = quote.get('c', 0)
            if not current_price:
                logger.warning(f"Finnhub返回 {sym} 价格为0")
                return None

            prev_close    = quote.get('pc', current_price)
            change        = current_price - prev_close
            change_percent = (change / prev_close * 100) if prev_close > 0 else 0

            # 把前收盘价写入 Alpaca WS，供下次 WS 推送计算涨跌幅
            if self.alpaca_ws:
                self.alpaca_ws.set_prev_close(sym, prev_close)

            return {
                'symbol':         sym,
                'name':           name,
                'price':          current_price,
                'change':         change,
                'change_percent': change_percent,
                'volume':         quote.get('v', 0),
                'market_cap':     market_cap,
                'high':           quote.get('h', 0),
                'low':            quote.get('l', 0),
                'open':           quote.get('o', 0),
                'prev_close':     prev_close,
                'currency':       'USD',
                'exchange':       exchange,
                'source':         'Finnhub-REST',
            }
        except Exception as e:
            logger.error(f"Finnhub获取美股 {sym} 失败: {e}")
            return None
    
    def get_hk_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取港股信息。

        优先级：
          1. FUTU WebSocket 实时缓存（<1秒，港交所实时）
          2. yfinance REST 兜底（15分钟延迟）

        Args:
            symbol: 港股代码，如 '00700', '0700', '700' 或 '0700.HK'

        Returns:
            股票信息字典，或 None
        """
        # ── 优先：FUTU WebSocket 缓存 ──
        if self.futu_client and self.futu_client.is_running:
            cached = self.futu_client.get_cached_price(symbol)
            if not cached:
                # 缓存没有 → 主动拉一次快照（同时会写入 prev_close 供后续推送计算涨跌）
                cached = self.futu_client.get_snapshot(symbol)
            if cached:
                price    = cached['price']
                chg_pct  = cached['change_pct']
                logger.debug(f"[FUTU] {symbol} HK${price} ({chg_pct:+.2f}%) 来源={cached['source']}")
                return {
                    'symbol':         symbol,
                    'name':           cached.get('name', symbol),
                    'price':          price,
                    'change':         0,
                    'change_percent': chg_pct,
                    'volume':         cached.get('volume', 0),
                    'market_cap':     0,
                    'high':           cached.get('high', 0),
                    'low':            cached.get('low', 0),
                    'open':           cached.get('open', 0),
                    'prev_close':     0,
                    'currency':       'HKD',
                    'exchange':       'HKEX',
                    'source':         cached['source'],
                }
            # FUTU 在运行但无数据（收盘或刚订阅）→ 追加订阅并降级 yfinance
            self.futu_client.subscribe([symbol])

        # ── 兜底：yfinance ──
        if not self.yfinance_available:
            logger.warning(f"yfinance 不可用，且 FUTU 无缓存，无法获取 {symbol}")
            return None

        try:
            yf_symbol = self._format_hk_symbol(symbol)
            ticker    = yf.Ticker(yf_symbol)
            info      = ticker.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            if not current_price:
                logger.warning(f"yfinance 未返回 {symbol} 的价格数据")
                return None
            return {
                'symbol':         symbol,
                'yf_symbol':      yf_symbol,
                'name':           info.get('longName', symbol),
                'price':          current_price,
                'change':         info.get('regularMarketChange'),
                'change_percent': info.get('regularMarketChangePercent'),
                'volume':         info.get('volume'),
                'market_cap':     info.get('marketCap'),
                'high':           info.get('dayHigh'),
                'low':            info.get('dayLow'),
                'open':           info.get('open'),
                'prev_close':     info.get('previousClose'),
                'currency':       'HKD',
                'exchange':       'HKEX',
                'source':         'yfinance',
            }
        except Exception as e:
            logger.error(f"yfinance 获取港股 {symbol} 失败: {e}")
            return None
    
    async def get_us_market_summary(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取美股市场摘要
        
        Args:
            limit: 返回股票数量
            
        Returns:
            股票信息列表
        """
        if not self.available:
            return []
        
        try:
            stocks = []
            for symbol in self.US_STOCKS[:limit]:
                info = await asyncio.to_thread(self.get_us_stock_info, symbol)
                if info:
                    stocks.append(info)
                # 添加小延迟避免rate limit
                await asyncio.sleep(0.1)
            
            return stocks
        except Exception as e:
            logger.error(f"获取美股市场摘要失败: {e}")
            return []
    
    async def get_hk_market_summary(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取港股市场摘要
        
        Args:
            limit: 返回股票数量
            
        Returns:
            股票信息列表
        """
        if not self.available:
            return []
        
        try:
            stocks = []
            for symbol in self.HK_STOCKS[:limit]:
                info = await asyncio.to_thread(self.get_hk_stock_info, symbol)
                if info:
                    stocks.append(info)
                # 添加小延迟避免rate limit
                await asyncio.sleep(0.1)
            
            return stocks
        except Exception as e:
            logger.error(f"获取港股市场摘要失败: {e}")
            return []
    
    def is_us_stock(self, symbol: str) -> bool:
        """判断是否为美股符号
        
        Args:
            symbol: 股票符号
            
        Returns:
            是否为美股
        """
        # 美股一般是1-5个大写字母
        return symbol.isupper() and symbol.isalpha() and 1 <= len(symbol) <= 5
    
    def is_hk_stock(self, symbol: str) -> bool:
        """判断是否为港股符号
        
        Args:
            symbol: 股票符号
            
        Returns:
            是否为港股
        """
        # 港股一般是3-5位数字，或带.HK后缀
        clean_symbol = symbol.replace('.HK', '').replace('.hk', '')
        return (clean_symbol.isdigit() and 3 <= len(clean_symbol) <= 5) or '.HK' in symbol.upper()


async def test_fetcher():
    """测试数据获取器（美股用Finnhub，港股用yfinance）"""
    fetcher = USHKStockFetcher()
    
    if not fetcher.available:
        print("❌ 无可用数据源")
        return
    
    print("=" * 70)
    print("✅ 数据源已就绪")
    if fetcher.finnhub_available:
        print("   📊 Finnhub: 美股数据源")
    if fetcher.yfinance_available:
        print("   📊 yfinance: 港股数据源（Finnhub免费版不支持港股）")
    print("=" * 70)
    
    # 测试美股（Finnhub）
    if fetcher.finnhub_available:
        print("\n📈 测试美股（Finnhub API）")
        print("-" * 70)
        for symbol in ['AAPL', 'TSLA', 'NVDA']:
            info = fetcher.get_us_stock_info(symbol)
            if info:
                print(f"  ✅ {symbol:6s} {info['name']:25s} ${info['price']:9.2f} ({info['change_percent']:+6.2f}%)")
            else:
                print(f"  ❌ {symbol:6s} 获取失败")
            await asyncio.sleep(0.2)
    
    # 测试港股（yfinance）
    if fetcher.yfinance_available:
        print("\n📊 测试港股（yfinance - Finnhub免费版不支持）")
        print("-" * 70)
        for symbol in ['00700', '09988', '01810']:
            info = fetcher.get_hk_stock_info(symbol)
            if info:
                print(f"  ✅ {symbol:6s} {info['name']:25s} HK${info['price']:9.2f} ({info['change_percent']:+6.2f}%)")
            else:
                print(f"  ❌ {symbol:6s} 获取失败")
            await asyncio.sleep(0.2)
    
    print("\n" + "=" * 70)
    print("✅ 测试完成")
    print("💡 策略: 美股用Finnhub（高质量，无rate limit），港股用yfinance（免费）")
    print("=" * 70)


if __name__ == '__main__':
    asyncio.run(test_fetcher())
