#!/usr/bin/env python3
"""
统一监控系统
韩国股票 (pykrx) + 加密货币 (Upbit + Bithumb)
"""
import os
import sys
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入模块
from pykrx import stock as pykrx_stock
from crypto_fetcher import CryptoDataFetcher
from telegram_bot_standalone import OpenClawTelegramBot
from openclaw.skills.execution.position_tracker import PositionTracker


class UnifiedMarketMonitor:
    """统一市场监控器"""
    
    def __init__(
        self,
        stock_watch_list: List[str],
        crypto_watch_mode: str = 'top50',
        crypto_custom_list: Optional[List[str]] = None,
        poll_interval: int = 30,
        alert_threshold: float = 2.0,
        tracker: Optional[PositionTracker] = None,
        telegram_bot: Optional[OpenClawTelegramBot] = None
    ):
        self.stock_watch_list = stock_watch_list
        self.crypto_watch_mode = crypto_watch_mode
        self.crypto_custom_list = crypto_custom_list or []
        self.poll_interval = poll_interval
        self.alert_threshold = alert_threshold
        self.tracker = tracker
        self.telegram_bot = telegram_bot
        
        self.crypto_fetcher = CryptoDataFetcher()
        
        self.stock_names = {}
        self.crypto_names = {}
        
        self.last_alert_time: Dict[str, datetime] = {}
        
        self.stats = {
            'total_polls': 0,
            'successful_polls': 0,
            'failed_polls': 0,
            'alerts_sent': 0,
            'stocks_monitored': len(stock_watch_list),
            'cryptos_monitored': 0,
            'start_time': datetime.now()
        }
        
        logger.info("✅ 统一市场监控器初始化成功")
    
    async def get_stock_name(self, symbol: str) -> str:
        if symbol in self.stock_names:
            return self.stock_names[symbol]
        
        try:
            name = await asyncio.to_thread(
                pykrx_stock.get_market_ticker_name, symbol
            )
            if name:
                self.stock_names[symbol] = name
                return name
        except:
            pass
        
        return symbol
    
    async def get_stock_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            today = datetime.now()
            week_ago = today - timedelta(days=7)
            
            today_str = today.strftime("%Y%m%d")
            week_ago_str = week_ago.strftime("%Y%m%d")
            
            df = await asyncio.to_thread(
                pykrx_stock.get_market_ohlcv_by_date,
                week_ago_str, today_str, symbol
            )
            
            if df.empty:
                return None
            
            latest = df.iloc[-1]
            
            if len(df) >= 2:
                prev_close = df.iloc[-2]['종가']
                change_pct = ((latest['종가'] - prev_close) / prev_close) * 100
            else:
                change_pct = 0
            
            return {
                'symbol': symbol,
                'type': 'stock',
                'exchange': 'pykrx',
                'price': int(latest['종가']),
                'change': round(change_pct, 2),
                'volume': int(latest['거래량']),
                'high': int(latest['고가']),
                'low': int(latest['저가']),
                'timestamp': datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.debug(f"Stock {symbol} 获取失败: {e}")
            return None
    
    async def get_all_stock_prices(self) -> Dict[str, Dict[str, Any]]:
        tasks = [self.get_stock_price(symbol) for symbol in self.stock_watch_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        prices = {}
        for symbol, result in zip(self.stock_watch_list, results):
            if isinstance(result, dict):
                prices[symbol] = result
        
        return prices
    
    async def get_crypto_watch_list(self) -> List[str]:
        if self.crypto_watch_mode == 'all':
            upbit_markets = await self.crypto_fetcher.get_upbit_markets()
            bithumb_markets = await self.crypto_fetcher.get_bithumb_markets()
            
            all_markets = list(set(upbit_markets + [f'KRW-{m}' for m in bithumb_markets]))
            
            return all_markets
            
        elif self.crypto_watch_mode == 'top50':
            top_cryptos = await self.crypto_fetcher.get_top_cryptos(limit=50)
            return list(top_cryptos.keys())
            
        elif self.crypto_watch_mode == 'top100':
            top_cryptos = await self.crypto_fetcher.get_top_cryptos(limit=100)
            return list(top_cryptos.keys())
            
        elif self.crypto_watch_mode == 'custom':
            return self.crypto_custom_list
        
        return []
    
    async def get_all_crypto_prices(self) -> Dict[str, Dict[str, Any]]:
        if self.crypto_watch_mode == 'all':
            prices = await self.crypto_fetcher.get_all_crypto_prices()
        elif self.crypto_watch_mode in ['top50', 'top100']:
            limit = 50 if self.crypto_watch_mode == 'top50' else 100
            prices = await self.crypto_fetcher.get_top_cryptos(limit=limit)
        else:
            prices = {}
            for symbol in self.crypto_custom_list:
                price_data = await self.crypto_fetcher.get_upbit_price(symbol)
                if not price_data:
                    price_data = await self.crypto_fetcher.get_bithumb_price(symbol)
                
                if price_data:
                    prices[symbol] = price_data
        
        for symbol, data in prices.items():
            data['type'] = 'crypto'
        
        return prices
    
    async def get_all_prices(self) -> Dict[str, Dict[str, Any]]:
        logger.info("📊 开始获取价格...")
        
        stock_task = self.get_all_stock_prices()
        crypto_task = self.get_all_crypto_prices()
        
        stock_prices, crypto_prices = await asyncio.gather(
            stock_task, crypto_task, return_exceptions=True
        )
        
        all_prices = {}
        
        if isinstance(stock_prices, dict):
            all_prices.update(stock_prices)
        
        if isinstance(crypto_prices, dict):
            all_prices.update(crypto_prices)
            self.stats['cryptos_monitored'] = len(crypto_prices)
        
        logger.info(f"✅ 股票: {len(stock_prices) if isinstance(stock_prices, dict) else 0}")
        logger.info(f"✅ 加密: {len(crypto_prices) if isinstance(crypto_prices, dict) else 0}")
        logger.info(f"✅ 总计: {len(all_prices)}")
        
        return all_prices
    
    def should_alert(self, symbol: str, change_pct: float) -> bool:
        if abs(change_pct) < self.alert_threshold:
            return False
        
        if symbol in self.last_alert_time:
            time_since_last = datetime.now() - self.last_alert_time[symbol]
            if time_since_last < timedelta(minutes=5):
                return False
        
        return True
    
    async def check_alerts(self, prices: Dict[str, Dict[str, Any]]):
        for symbol, price_data in prices.items():
            change_pct = price_data.get('change', 0)
            
            if self.should_alert(symbol, change_pct):
                await self.send_alert(symbol, price_data)
    
    async def send_alert(self, symbol: str, price_data: Dict[str, Any]):
        try:
            if price_data['type'] == 'stock':
                name = await self.get_stock_name(symbol)
            else:
                name = symbol.replace('KRW-', '')
            
            alert_data = {
                'symbol': symbol,
                'name': name,
                'price_data': price_data
            }
            
            if self.telegram_bot:
                await self.telegram_bot.send_alert(alert_data)
            else:
                change = price_data['change']
                price = price_data['price']
                asset_type = price_data['type']
                emoji = "🟢" if change > 0 else "🔴"
                type_emoji = "🇰🇷" if asset_type == 'stock' else "🪙"
                
                logger.warning(
                    f"🚨 {type_emoji} {emoji} {name} ({symbol}): "
                    f"₩{price:,} ({change:+.2f}%) [{price_data['exchange']}]"
                )
            
            self.last_alert_time[symbol] = datetime.now()
            self.stats['alerts_sent'] += 1
            
        except Exception as e:
            logger.error(f"发送告警失败 {symbol}: {e}")
    
    def display_current_prices(self, prices: Dict[str, Dict[str, Any]]):
        logger.info("="*80)
        logger.info(f"📊 当前价格 ({datetime.now().strftime('%H:%M:%S')})")
        logger.info("-"*80)
        
        stocks = {k: v for k, v in prices.items() if v.get('type') == 'stock'}
        cryptos = {k: v for k, v in prices.items() if v.get('type') == 'crypto'}
        
        if stocks:
            logger.info("🇰🇷 韩国股票:")
            for symbol, data in sorted(stocks.items()):
                name = self.stock_names.get(symbol, symbol)
                price = data['price']
                change = data['change']
                
                emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                alert_flag = "🚨" if abs(change) >= self.alert_threshold else "  "
                
                logger.info(
                    f"{alert_flag} {emoji} {name:12s} ({symbol:6s}): "
                    f"₩{price:>12,} ({change:+6.2f}%)"
                )
        
        if cryptos:
            logger.info("\n🪙 加密货币 (涨跌幅前10):")
            sorted_cryptos = sorted(
                cryptos.items(),
                key=lambda x: abs(x[1].get('change', 0)),
                reverse=True
            )[:10]
            
            for symbol, data in sorted_cryptos:
                name = symbol.replace('KRW-', '')
                price = data['price']
                change = data['change']
                exchange = data.get('exchange', 'unknown')
                
                emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                alert_flag = "🚨" if abs(change) >= self.alert_threshold else "  "
                
                logger.info(
                    f"{alert_flag} {emoji} {name:12s} ({exchange:8s}): "
                    f"₩{price:>15,.2f} ({change:+6.2f}%)"
                )
        
        logger.info("="*80)
    
    async def monitor_loop(self):
        logger.info("🚀 开始监控...")
        
        while True:
            try:
                loop_start = datetime.now()
                
                prices = await self.get_all_prices()
                
                if prices:
                    self.stats['successful_polls'] += 1
                    await self.check_alerts(prices)
                    self.display_current_prices(prices)
                else:
                    self.stats['failed_polls'] += 1
                
                self.stats['total_polls'] += 1
                
                loop_duration = (datetime.now() - loop_start).total_seconds()
                sleep_time = max(0, self.poll_interval - loop_duration)
                
                if sleep_time > 0:
                    logger.info(f"⏳ 等待 {sleep_time:.1f}秒...")
                    await asyncio.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("🛑 收到停止信号")
                break
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                import traceback
                traceback.print_exc()
                self.stats['failed_polls'] += 1
                await asyncio.sleep(self.poll_interval)
    
    def display_stats(self):
        uptime = datetime.now() - self.stats['start_time']
        
        logger.info("="*80)
        logger.info("📈 监控统计")
        logger.info("-"*80)
        logger.info(f"运行时间: {str(uptime).split('.')[0]}")
        logger.info(f"总轮询: {self.stats['total_polls']}")
        logger.info(f"成功: {self.stats['successful_polls']}")
        logger.info(f"失败: {self.stats['failed_polls']}")
        success_rate = (
            self.stats['successful_polls'] / self.stats['total_polls'] * 100
            if self.stats['total_polls'] > 0 else 0
        )
        logger.info(f"成功率: {success_rate:.1f}%")
        logger.info(f"告警: {self.stats['alerts_sent']}")
        logger.info(f"监控股票: {self.stats['stocks_monitored']}")
        logger.info(f"监控加密: {self.stats['cryptos_monitored']}")
        logger.info("="*80)
    
    async def run(self):
        logger.info("="*80)
        logger.info("🦞 OpenClaw 统一市场监控系统")
        logger.info("="*80)
        logger.info(f"📊 韩国股票: {len(self.stock_watch_list)} 只")
        logger.info(f"🪙 加密货币: {self.crypto_watch_mode}")
        logger.info(f"⏱️  轮询间隔: {self.poll_interval}秒")
        logger.info(f"🚨 告警阈值: ±{self.alert_threshold}%")
        logger.info(f"📱 Telegram: {'✅' if self.telegram_bot else '❌'}")
        logger.info("="*80)
        
        try:
            await self.monitor_loop()
        except KeyboardInterrupt:
            logger.info("\n🛑 监控已停止")
        finally:
            self.display_stats()


async def main():
    from dotenv import load_dotenv
    
    load_dotenv()
    
    STOCK_WATCHLIST = os.getenv('KR_STOCK_WATCHLIST', '005930,035420,035720').split(',')
    CRYPTO_WATCH_MODE = os.getenv('CRYPTO_WATCH_MODE', 'top50')
    POLL_INTERVAL = int(os.getenv('MONITOR_INTERVAL', '30'))
    ALERT_THRESHOLD = float(os.getenv('ALERT_THRESHOLD', '2.0'))
    
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    ENABLE_TELEGRAM = os.getenv('ENABLE_TELEGRAM_BOT', 'false').lower() == 'true'
    
    tracker = PositionTracker(initial_capital=10000000)
    tracker.open_position('005930', 10, 181200)
    tracker.open_position('KRW-BTC', 0.05, 60000000)
    
    telegram_bot = None
    if ENABLE_TELEGRAM and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        telegram_bot = OpenClawTelegramBot(
            token=TELEGRAM_BOT_TOKEN,
            chat_id=TELEGRAM_CHAT_ID,
            tracker=tracker
        )
        asyncio.create_task(telegram_bot.run())
        await asyncio.sleep(2)
    
    monitor = UnifiedMarketMonitor(
        stock_watch_list=STOCK_WATCHLIST,
        crypto_watch_mode=CRYPTO_WATCH_MODE,
        poll_interval=POLL_INTERVAL,
        alert_threshold=ALERT_THRESHOLD,
        tracker=tracker,
        telegram_bot=telegram_bot
    )
    
    await monitor.run()


if __name__ == '__main__':
    import sys
    
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    asyncio.run(main())
