#!/usr/bin/env python3
"""
韩股实时监控系统
30秒高频轮询 + Telegram 告警
"""
import os
import sys
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from pykrx import stock as pykrx_stock
    PYKRX_AVAILABLE = True
except ImportError:
    PYKRX_AVAILABLE = False
    logger.error("pykrx 未安装")

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis 未安装，将无法使用缓存")

from telegram_bot_standalone import OpenClawTelegramBot
from openclaw.skills.execution.position_tracker import PositionTracker


class KoreanStockMonitor:
    """韩股实时监控器"""
    
    def __init__(
        self,
        watch_list: List[str],
        poll_interval: int = 30,
        alert_threshold: float = 2.0,
        tracker: Optional[PositionTracker] = None,
        telegram_bot: Optional[OpenClawTelegramBot] = None,
        redis_client: Optional[redis.Redis] = None
    ):
        """
        初始化监控器
        
        Args:
            watch_list: 监控股票列表
            poll_interval: 轮询间隔（秒）
            alert_threshold: 告警阈值（涨跌幅 %）
            tracker: 持仓追踪器
            telegram_bot: Telegram Bot
            redis_client: Redis 客户端
        """
        self.watch_list = watch_list
        self.poll_interval = poll_interval
        self.alert_threshold = alert_threshold
        self.tracker = tracker
        self.telegram_bot = telegram_bot
        self.redis = redis_client
        
        # 股票名称缓存
        self.stock_names = {}
        
        # 价格历史（用于计算涨跌幅）
        self.price_history: Dict[str, List[Dict]] = {}
        
        # 上次告警时间（防止频繁告警）
        self.last_alert_time: Dict[str, datetime] = {}
        
        # 统计信息
        self.stats = {
            'total_polls': 0,
            'successful_polls': 0,
            'failed_polls': 0,
            'alerts_sent': 0,
            'start_time': datetime.now()
        }
        
        logger.info("✅ 韩股监控器初始化成功")
        logger.info(f"   监控列表: {len(watch_list)} 只股票")
        logger.info(f"   轮询间隔: {poll_interval}秒")
        logger.info(f"   告警阈值: ±{alert_threshold}%")
    
    # ==========================================
    # 数据获取
    # ==========================================
    
    async def get_stock_name(self, symbol: str) -> str:
        """获取股票名称"""
        if symbol in self.stock_names:
            return self.stock_names[symbol]
        
        try:
            name = await asyncio.to_thread(
                pykrx_stock.get_market_ticker_name, symbol
            )
            if name:
                self.stock_names[symbol] = name
                return name
        except Exception as e:
            logger.debug(f"获取名称失败 {symbol}: {e}")
        
        return symbol
    
    async def get_stock_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取股票实时价格"""
        try:
            # 获取今天和前几天的数据
            today = datetime.now()
            days_ago = today - timedelta(days=7)
            
            today_str = today.strftime("%Y%m%d")
            days_ago_str = days_ago.strftime("%Y%m%d")
            
            # 从 pykrx 获取数据
            df = await asyncio.to_thread(
                pykrx_stock.get_market_ohlcv_by_date,
                days_ago_str, today_str, symbol
            )
            
            if df.empty:
                logger.warning(f"无数据: {symbol}")
                return None
            
            # 获取最新数据
            latest = df.iloc[-1]
            latest_date = df.index[-1]
            
            # 计算涨跌幅
            if len(df) >= 2:
                prev_close = df.iloc[-2]['종가']
                change_pct = ((latest['종가'] - prev_close) / prev_close) * 100
            else:
                change_pct = 0
            
            price_data = {
                'symbol': symbol,
                'price': int(latest['종가']),
                'open': int(latest['시가']),
                'high': int(latest['고가']),
                'low': int(latest['저가']),
                'volume': int(latest['거래량']),
                'change': round(change_pct, 2),
                'date': latest_date.strftime('%Y-%m-%d'),
                'timestamp': datetime.now().isoformat(),
                'source': 'pykrx'
            }
            
            return price_data
            
        except Exception as e:
            logger.error(f"获取价格失败 {symbol}: {e}")
            return None
    
    async def get_all_prices(self) -> Dict[str, Dict[str, Any]]:
        """批量获取所有股票价格"""
        logger.info(f"开始获取 {len(self.watch_list)} 只股票价格...")
        
        tasks = []
        for symbol in self.watch_list:
            tasks.append(self.get_stock_price(symbol))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        prices = {}
        for symbol, result in zip(self.watch_list, results):
            if isinstance(result, dict):
                prices[symbol] = result
            elif isinstance(result, Exception):
                logger.error(f"{symbol} 获取失败: {result}")
        
        logger.info(f"✅ 成功获取 {len(prices)}/{len(self.watch_list)} 只股票价格")
        
        return prices
    
    # ==========================================
    # 监控逻辑
    # ==========================================
    
    def should_alert(self, symbol: str, change_pct: float) -> bool:
        """判断是否应该发送告警"""
        # 1. 检查涨跌幅是否超过阈值
        if abs(change_pct) < self.alert_threshold:
            return False
        
        # 2. 检查是否在冷却期（避免频繁告警，5分钟内不重复）
        if symbol in self.last_alert_time:
            time_since_last = datetime.now() - self.last_alert_time[symbol]
            if time_since_last < timedelta(minutes=5):
                return False
        
        return True
    
    async def check_alerts(self, prices: Dict[str, Dict[str, Any]]):
        """检查并发送告警"""
        for symbol, price_data in prices.items():
            change_pct = price_data.get('change', 0)
            
            if self.should_alert(symbol, change_pct):
                await self.send_alert(symbol, price_data)
    
    async def send_alert(self, symbol: str, price_data: Dict[str, Any]):
        """发送告警"""
        try:
            # 获取股票名称
            name = await self.get_stock_name(symbol)
            
            # 构建告警数据
            alert_data = {
                'symbol': symbol,
                'name': name,
                'price_data': price_data
            }
            
            # 发送到 Telegram
            if self.telegram_bot:
                await self.telegram_bot.send_alert(alert_data)
            else:
                # 如果没有 Telegram Bot，输出到控制台
                change = price_data['change']
                price = price_data['price']
                emoji = "🟢" if change > 0 else "🔴"
                
                logger.warning(
                    f"🚨 {emoji} {name} ({symbol}): "
                    f"₩{price:,} ({change:+.2f}%)"
                )
            
            # 更新告警时间
            self.last_alert_time[symbol] = datetime.now()
            self.stats['alerts_sent'] += 1
            
        except Exception as e:
            logger.error(f"发送告警失败 {symbol}: {e}")
    
    # ==========================================
    # 价格历史管理
    # ==========================================
    
    def update_price_history(self, symbol: str, price_data: Dict[str, Any]):
        """更新价格历史"""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append({
            'timestamp': datetime.now(),
            'price': price_data['price'],
            'change': price_data['change']
        })
        
        # 只保留最近1小时的数据
        cutoff_time = datetime.now() - timedelta(hours=1)
        self.price_history[symbol] = [
            item for item in self.price_history[symbol]
            if item['timestamp'] > cutoff_time
        ]
    
    # ==========================================
    # 监控循环
    # ==========================================
    
    async def monitor_loop(self):
        """主监控循环"""
        logger.info("🚀 开始监控...")
        
        while True:
            try:
                loop_start = datetime.now()
                
                # 1. 获取所有价格
                prices = await self.get_all_prices()
                
                if prices:
                    self.stats['successful_polls'] += 1
                    
                    # 2. 更新价格历史
                    for symbol, price_data in prices.items():
                        self.update_price_history(symbol, price_data)
                    
                    # 3. 检查告警
                    await self.check_alerts(prices)
                    
                    # 4. 显示当前价格
                    self.display_current_prices(prices)
                else:
                    self.stats['failed_polls'] += 1
                    logger.warning("本次轮询未获取到任何数据")
                
                self.stats['total_polls'] += 1
                
                # 5. 等待下次轮询
                loop_duration = (datetime.now() - loop_start).total_seconds()
                sleep_time = max(0, self.poll_interval - loop_duration)
                
                if sleep_time > 0:
                    logger.info(f"⏳ 等待 {sleep_time:.1f}秒后继续...")
                    await asyncio.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("🛑 收到停止信号")
                break
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                self.stats['failed_polls'] += 1
                await asyncio.sleep(self.poll_interval)
    
    def display_current_prices(self, prices: Dict[str, Dict[str, Any]]):
        """显示当前价格"""
        logger.info("="*70)
        logger.info(f"📊 当前价格 ({datetime.now().strftime('%H:%M:%S')})")
        logger.info("-"*70)
        
        for symbol, price_data in sorted(prices.items()):
            name = self.stock_names.get(symbol, symbol)
            price = price_data['price']
            change = price_data['change']
            
            emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
            alert_flag = "🚨" if abs(change) >= self.alert_threshold else "  "
            
            logger.info(
                f"{alert_flag} {emoji} {name:12s} ({symbol:6s}): "
                f"₩{price:>10,} ({change:+6.2f}%)"
            )
        
        logger.info("="*70)
    
    # ==========================================
    # 统计信息
    # ==========================================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = datetime.now() - self.stats['start_time']
        
        return {
            **self.stats,
            'uptime_seconds': uptime.total_seconds(),
            'uptime_formatted': str(uptime).split('.')[0],
            'success_rate': (
                self.stats['successful_polls'] / self.stats['total_polls'] * 100
                if self.stats['total_polls'] > 0 else 0
            )
        }
    
    def display_stats(self):
        """显示统计信息"""
        stats = self.get_stats()
        
        logger.info("="*70)
        logger.info("📈 监控统计")
        logger.info("-"*70)
        logger.info(f"运行时间: {stats['uptime_formatted']}")
        logger.info(f"总轮询次数: {stats['total_polls']}")
        logger.info(f"成功次数: {stats['successful_polls']}")
        logger.info(f"失败次数: {stats['failed_polls']}")
        logger.info(f"成功率: {stats['success_rate']:.1f}%")
        logger.info(f"告警次数: {stats['alerts_sent']}")
        logger.info("="*70)
    
    # ==========================================
    # 运行
    # ==========================================
    
    async def run(self):
        """运行监控器"""
        logger.info("="*70)
        logger.info("🦞 OpenClaw 韩股实时监控系统")
        logger.info("="*70)
        logger.info(f"监控列表: {', '.join(self.watch_list)}")
        logger.info(f"轮询间隔: {self.poll_interval}秒")
        logger.info(f"告警阈值: ±{self.alert_threshold}%")
        logger.info(f"Telegram Bot: {'已启用 ✅' if self.telegram_bot else '未启用 ⏸️'}")
        logger.info("="*70)
        
        # 预加载股票名称
        logger.info("预加载股票名称...")
        for symbol in self.watch_list:
            name = await self.get_stock_name(symbol)
            logger.info(f"  {symbol}: {name}")
        
        logger.info("✅ 准备完成")
        logger.info("")
        
        try:
            await self.monitor_loop()
        except KeyboardInterrupt:
            logger.info("\n🛑 监控已停止")
        finally:
            self.display_stats()


# ==========================================
# 主程序
# ==========================================

async def main():
    """主函数"""
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # 配置
    WATCH_LIST = os.getenv('KR_STOCK_WATCHLIST', '005930,035420,035720,051910').split(',')
    POLL_INTERVAL = int(os.getenv('KR_STOCK_MONITOR_INTERVAL', '30'))
    ALERT_THRESHOLD = float(os.getenv('KR_STOCK_ALERT_THRESHOLD', '2.0'))
    
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    ENABLE_TELEGRAM = os.getenv('ENABLE_TELEGRAM_BOT', 'false').lower() == 'true'
    
    # 读取授权用户列表（用于Telegram Bot访问控制）
    authorized_users_str = os.getenv('TELEGRAM_AUTHORIZED_USERS', '')
    authorized_users = None
    if authorized_users_str:
        try:
            authorized_users = [int(uid.strip()) for uid in authorized_users_str.split(',') if uid.strip()]
            logger.info(f"✅ 已启用Telegram用户验证，授权用户数: {len(authorized_users)}")
        except ValueError:
            logger.error("❌ TELEGRAM_AUTHORIZED_USERS 格式错误，应为逗号分隔的数字")
    else:
        logger.warning("⚠️ 未设置TELEGRAM_AUTHORIZED_USERS，任何人都可以使用bot！")
    
    # 创建持仓追踪器（如果需要）
    tracker = PositionTracker(initial_capital=10000000)
    
    # 添加一些测试持仓
    tracker.open_position('005930', 10, 181200)
    tracker.open_position('035420', 5, 252500)
    
    # 创建 Telegram Bot（如果启用）
    telegram_bot = None
    if ENABLE_TELEGRAM and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        telegram_bot = OpenClawTelegramBot(
            token=TELEGRAM_BOT_TOKEN,
            chat_id=TELEGRAM_CHAT_ID,
            tracker=tracker,
            authorized_users=authorized_users  # 传入授权用户列表
        )
        logger.info("✅ Telegram Bot 已启用")
        
        # 在后台启动 Bot
        asyncio.create_task(telegram_bot.run())
        await asyncio.sleep(2)  # 等待 Bot 启动
    
    # 创建监控器
    monitor = KoreanStockMonitor(
        watch_list=WATCH_LIST,
        poll_interval=POLL_INTERVAL,
        alert_threshold=ALERT_THRESHOLD,
        tracker=tracker,
        telegram_bot=telegram_bot
    )
    
    # 运行
    await monitor.run()


if __name__ == '__main__':
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    asyncio.run(main())
