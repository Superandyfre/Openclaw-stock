"""
Korean Stock Monitor V2 (100% pykrx)

High-frequency monitoring of Korean stocks using pykrx-dominant architecture
"""
from typing import Optional, List, Dict, Any
from loguru import logger
import asyncio

from openclaw.core.database import DatabaseManager
from openclaw.skills.monitoring.korean_stock_fetcher_v2 import KoreanStockFetcherV2


class KoreanStockMonitorV2:
    """
    Korean Stock Monitor V2 (100% pykrx for prices)
    
    Features:
    - High-frequency monitoring (30-second intervals)
    - pykrx-dominant data fetching
    - Zero Yahoo Finance usage for price queries
    - Telegram alert integration (optional)
    """
    
    # Default watch list (major Korean stocks)
    DEFAULT_WATCH_LIST = [
        '005930',  # 삼성전자
        '000660',  # SK하이닉스
        '035420',  # NAVER
        '035720',  # 카카오
        '051910',  # LG화학
        '207940',  # 삼성바이오로직스
    ]
    
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        telegram_bot: Optional[Any] = None,
        watch_list: Optional[List[str]] = None,
        threshold: float = 2.0,
        interval: int = 30
    ):
        """
        Initialize Korean Stock Monitor V2
        
        Args:
            db_manager: Database manager for caching
            telegram_bot: Telegram bot for alerts (optional)
            watch_list: List of stock codes to monitor
            threshold: Price change threshold for alerts (%)
            interval: Monitoring interval in seconds
        """
        self.db = db_manager or DatabaseManager()
        self.fetcher = KoreanStockFetcherV2(self.db)
        self.telegram_bot = telegram_bot
        
        self.watch_list = watch_list or self.DEFAULT_WATCH_LIST
        self.threshold = threshold
        self.interval = interval
        
        self._running = False
    
    async def _on_alert(self, alert_data: Dict[str, Any]):
        """
        Handle alert callback
        
        Args:
            alert_data: Alert information
        """
        symbol = alert_data['symbol']
        name = alert_data['name']
        price_data = alert_data['price_data']
        
        # Format alert message
        change_percent = price_data.get('change_percent', 0)
        price = price_data.get('price', 0)
        
        alert_msg = (
            f"🚨 Korean Stock Alert\n\n"
            f"📊 {name} ({symbol})\n"
            f"💰 Price: ₩{price:,.0f}\n"
            f"📈 Change: {change_percent:+.2f}%\n"
            f"🔔 Alert Type: {alert_data.get('alert_type', 'unknown')}"
        )
        
        logger.warning(alert_msg)
        
        # Send to Telegram if available
        if self.telegram_bot:
            try:
                await self.telegram_bot.send_message(alert_msg)
            except Exception as e:
                logger.error(f"Failed to send Telegram alert: {e}")
    
    async def start(self):
        """Start monitoring Korean stocks"""
        if self._running:
            logger.warning("Monitor already running")
            return
        
        self._running = True
        
        logger.info("=" * 60)
        logger.info("🚀 Starting Korean Stock Monitor V2")
        logger.info("=" * 60)
        logger.info(f"   Data source: pykrx (100% for prices)")
        logger.info(f"   Yahoo: Disabled for high-frequency (names only, <1%)")
        logger.info(f"   Watch list: {len(self.watch_list)} stocks")
        logger.info(f"   Polling interval: {self.interval}s")
        logger.info(f"   Threshold: ±{self.threshold}%")
        logger.info("=" * 60)
        
        try:
            await self.fetcher.monitor_stocks_high_frequency(
                symbols=self.watch_list,
                callback=self._on_alert,
                interval=self.interval,
                threshold=self.threshold
            )
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
        except Exception as e:
            logger.error(f"Monitor error: {e}")
        finally:
            self._running = False
    
    def stop(self):
        """Stop monitoring"""
        self._running = False
        logger.info("Stopping Korean Stock Monitor V2")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get monitoring statistics
        
        Returns:
            Statistics dictionary
        """
        return self.fetcher.get_stats()


# Example usage
async def main():
    """Example usage of KoreanStockMonitorV2"""
    from openclaw.core.database import DatabaseManager
    
    # Initialize database
    db = DatabaseManager()
    
    # Create monitor
    monitor = KoreanStockMonitorV2(
        db_manager=db,
        watch_list=['005930', '035420', '000660'],  # Samsung, NAVER, SK Hynix
        threshold=2.0,
        interval=30
    )
    
    # Start monitoring
    await monitor.start()


if __name__ == '__main__':
    asyncio.run(main())
