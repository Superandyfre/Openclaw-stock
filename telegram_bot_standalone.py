#!/usr/bin/env python3
"""
OpenClaw Telegram Bot (独立版 - 完整功能)
显示股票名称，集成告警功能
"""
import os
import sys
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from loguru import logger

try:
    from telegram import Update, Bot
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        filters,
        ContextTypes
    )
    from telegram.request import HTTPXRequest
    from telegram.request import HTTPXRequest
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.error("python-telegram-bot 未安装")

try:
    from pykrx import stock as pykrx_stock
    PYKRX_AVAILABLE = True
except ImportError:
    PYKRX_AVAILABLE = False

from openclaw.skills.execution.position_tracker import PositionTracker
from openclaw.skills.analysis.ai_trading_advisor import AITradingAdvisor
from openclaw.skills.analysis.conversation_handler import ConversationHandler

# 金额/价格格式化辅助（不四舍五入）
_fw  = ConversationHandler._fmt_price   # 无符号：₩1,234.5
_fws = ConversationHandler._fmt_signed  # 有符号：+₩1,234.5 / -₩1,234.5

# Crypto data fetcher
try:
    from crypto_fetcher import CryptoDataFetcher
    CRYPTO_FETCHER_AVAILABLE = True
except ImportError:
    CRYPTO_FETCHER_AVAILABLE = False
    logger.warning("crypto_fetcher 未找到")

# US/HK stock fetcher
try:
    from openclaw.skills.data_collection.us_hk_stock_fetcher import USHKStockFetcher
    USHK_FETCHER_AVAILABLE = True
except ImportError:
    USHK_FETCHER_AVAILABLE = False
    logger.warning("us_hk_stock_fetcher 未找到")

# K线与交易量数据
try:
    from openclaw.skills.data_collection.kline_fetcher import KlineFetcher
    KLINE_FETCHER_AVAILABLE = True
except ImportError:
    KLINE_FETCHER_AVAILABLE = False
    logger.warning("kline_fetcher 未找到")

# DART announcement monitor
try:
    from openclaw.skills.data_collection.announcement_monitor import AnnouncementMonitor
    ANNOUNCEMENT_MONITOR_AVAILABLE = True
except ImportError:
    ANNOUNCEMENT_MONITOR_AVAILABLE = False
    logger.warning("announcement_monitor 未找到")


class SimplePortfolioManager:
    """简化的组合管理器"""
    
    def __init__(self, tracker: PositionTracker):
        self.tracker = tracker
    
    def get_stock_positions(self) -> Dict:
        return {
            symbol: pos for symbol, pos in self.tracker.positions.items()
            if not symbol.startswith('KRW-') and not symbol.startswith('USDT-')
        }
    
    def get_crypto_positions(self) -> Dict:
        return {
            symbol: pos for symbol, pos in self.tracker.positions.items()
            if symbol.startswith('KRW-') or symbol.startswith('USDT-')
        }
    
    def get_portfolio_by_type(self, current_prices: Dict[str, float]) -> Dict:
        stock_positions = self.get_stock_positions()
        crypto_positions = self.get_crypto_positions()
        
        stocks_cost = sum(pos['total_cost'] for pos in stock_positions.values())
        stocks_value = sum(
            pos['quantity'] * current_prices.get(symbol, pos['avg_entry_price'])
            for symbol, pos in stock_positions.items()
        )
        stocks_pnl = stocks_value - stocks_cost
        stocks_pnl_pct = (stocks_pnl / stocks_cost * 100) if stocks_cost > 0 else 0
        
        crypto_cost = sum(pos['total_cost'] for pos in crypto_positions.values())
        crypto_value = sum(
            pos['quantity'] * current_prices.get(symbol, pos['avg_entry_price'])
            for symbol, pos in crypto_positions.items()
        )
        crypto_pnl = crypto_value - crypto_cost
        crypto_pnl_pct = (crypto_pnl / crypto_cost * 100) if crypto_cost > 0 else 0
        
        total_invested = stocks_cost + crypto_cost
        position_value = stocks_value + crypto_value
        total_pnl = position_value - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        
        return {
            'stocks': {
                'count': len(stock_positions),
                'total_cost': stocks_cost,
                'total_value': stocks_value,
                'unrealized_pnl': stocks_pnl,
                'unrealized_pnl_pct': stocks_pnl_pct,
                'positions': stock_positions
            },
            'crypto': {
                'count': len(crypto_positions),
                'total_cost': crypto_cost,
                'total_value': crypto_value,
                'unrealized_pnl': crypto_pnl,
                'unrealized_pnl_pct': crypto_pnl_pct,
                'positions': crypto_positions
            },
            'total': {
                'portfolio_value': self.tracker.cash + position_value,
                'cash': self.tracker.cash,
                'total_invested': total_invested,
                'position_value': position_value,
                'total_pnl': total_pnl,
                'total_pnl_pct': total_pnl_pct,
                'initial_capital': self.tracker.initial_capital
            }
        }


class OpenClawTelegramBot:
    """OpenClaw Telegram Bot"""
    
    def __init__(
        self,
        token: str,
        chat_id: str,
        tracker: Optional[PositionTracker] = None,
        authorized_users: Optional[list] = None,
        state_file: Optional[str] = None,
    ):
        if not TELEGRAM_AVAILABLE:
            raise ImportError("请安装: pip install python-telegram-bot")
        
        self.token = token
        self.chat_id = chat_id
        self.tracker = tracker
        self.pm = SimplePortfolioManager(tracker) if tracker else None
        
        # 用户白名单：只允许这些用户ID与bot交互
        # 如果为None或空列表，则允许所有用户（不推荐）
        self.authorized_users = set(authorized_users) if authorized_users else None

        # 广播目标：主 chat_id + 所有白名单用户（去重）
        _bcast_set: set = {str(chat_id)}
        if authorized_users:
            _bcast_set.update(str(uid) for uid in authorized_users)
        self.broadcast_ids: list = list(_bcast_set)
        
        self.bot = Bot(token=token)
        self.app = None
        
        self.stock_names_cache = {}
        # 置顶消息 ID：每个广播用户独立维护 {cid: message_id}
        self._pinned_msg_ids: dict = {}
        self.stock_names_map = {
            '005930': '삼성전자', '000660': 'SK하이닉스', '035420': 'NAVER',
            '035720': '카카오', '051910': 'LG화학', '006400': '삼성SDI',
            'KRW-BTC': 'Bitcoin', 'KRW-ETH': 'Ethereum',
        }
        
        # 初始化AI交易顾问
        self.ai_advisor = AITradingAdvisor()
        
        # 初始化加密货币数据获取器
        self.crypto_fetcher = None
        if CRYPTO_FETCHER_AVAILABLE:
            try:
                self.crypto_fetcher = CryptoDataFetcher()
                logger.info("✅ CryptoDataFetcher 初始化成功")
            except Exception as e:
                logger.error(f"CryptoDataFetcher 初始化失败: {e}")
        
        # 初始化美股港股数据获取器
        self.us_hk_fetcher = None
        if USHK_FETCHER_AVAILABLE:
            try:
                self.us_hk_fetcher = USHKStockFetcher()
                logger.info("✅ USHKStockFetcher 初始化成功")
            except Exception as e:
                logger.error(f"USHKStockFetcher 初始化失败: {e}")
        
        # 初始化DART公告监控器
        self.announcement_monitor = None
        if ANNOUNCEMENT_MONITOR_AVAILABLE:
            dart_api_key = os.getenv('DART_API_KEY')
            if dart_api_key:
                try:
                    self.announcement_monitor = AnnouncementMonitor(dart_api_key=dart_api_key)
                    logger.info("✅ DART公告监控器初始化成功")
                except Exception as e:
                    logger.error(f"DART公告监控器初始化失败: {e}")
            else:
                logger.warning("⚠️  DART_API_KEY未配置，公告监控功能不可用")

        # 初始化K线数据获取器
        self.kline_fetcher = None
        if KLINE_FETCHER_AVAILABLE:
            try:
                self.kline_fetcher = KlineFetcher(
                    finnhub_api_key=os.getenv('FINNHUB_API_KEY')
                )
            except Exception as e:
                logger.error(f"KlineFetcher 初始化失败: {e}")

        # 初始化对话处理器
        self.conversation_handler = ConversationHandler(
            tracker=tracker,
            ai_advisor=self.ai_advisor,
            crypto_fetcher=self.crypto_fetcher,
            us_hk_fetcher=self.us_hk_fetcher,
            announcement_monitor=self.announcement_monitor,
            kline_fetcher=self.kline_fetcher,
            state_file=state_file,
        )
        
        # 设置持仓告警回调（实时发送止损告警）
        if self.tracker:
            self.tracker.alert_callback = self._send_position_alert
            logger.info("✅ 止损告警系统已启用（-10%强制止损, -8%警告）")
        
        if self.authorized_users:
            logger.info(f"✅ Telegram Bot 初始化成功（已启用用户白名单，授权用户数: {len(self.authorized_users)}）")
        else:
            logger.warning("⚠️  Telegram Bot 初始化成功（未启用用户白名单，任何人都可以使用）")
    
    def _send_position_alert(self, alert: Dict[str, Any]):
        """
        发送持仓告警消息（强制止损红线）
        
        Args:
            alert: 告警信息字典
        """
        try:
            severity = alert.get('severity', 'INFO')
            message = alert.get('message', '')
            
            # 根据严重程度添加前缀
            if severity == 'CRITICAL':
                prefix = "🔴🔴🔴 紧急告警 🔴🔴🔴\n"
            elif severity == 'HIGH':
                prefix = "⚠️⚠️ 风险警告 \n"
            elif severity == 'SUCCESS':
                prefix = "✅✅ 推荐离场 \n"
            elif severity == 'GOOD_NEWS':
                prefix = "📈📈 利好通知 \n"
            else:
                prefix = "🔔 通知 \n"
            
            full_message = prefix + message
            
            # 挂到已运行的 event loop（不创建新 loop，避免连接池冲突）
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._broadcast(full_message))
            except RuntimeError:
                asyncio.run(self._broadcast(full_message))
            
            logger.info(f"📧 告警消息已发送: {alert['type']}")
            
        except Exception as e:
            logger.error(f"发送告警消息失败: {e}")
    
    async def _broadcast(self, text: str, **kwargs) -> None:
        """向所有白名单用户广播消息（主动推送专用，不影响回复类消息）"""
        _bot = self.app.bot if self.app else self.bot
        results = await asyncio.gather(
            *[_bot.send_message(chat_id=cid, text=text, **kwargs)
              for cid in self.broadcast_ids],
            return_exceptions=True,
        )
        for cid, r in zip(self.broadcast_ids, results):
            if isinstance(r, Exception):
                logger.warning(f"广播失败 chat_id={cid}: {r}")

    def _is_authorized(self, user_id: int) -> bool:
        """检查用户是否有权限使用bot"""
        if self.authorized_users is None:
            # 未设置白名单，允许所有用户
            return True
        return user_id in self.authorized_users
    
    async def _check_authorization(self, update: Update) -> bool:
        """检查并处理用户授权"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        
        if not self._is_authorized(user_id):
            logger.warning(f"❌ 未授权用户尝试访问: {username} (ID: {user_id})")
            await update.message.reply_text(
                "❌ 抱歉，您没有权限使用此bot。\n\n"
                f"您的用户ID: {user_id}\n\n"
                "如需访问权限，请联系bot管理员。"
            )
            return False
        
        logger.info(f"✅ 授权用户访问: {username} (ID: {user_id})")
        return True
    
    async def get_stock_name(self, symbol: str) -> str:
        if symbol in self.stock_names_cache:
            return self.stock_names_cache[symbol]
        
        if symbol in self.stock_names_map:
            self.stock_names_cache[symbol] = self.stock_names_map[symbol]
            return self.stock_names_map[symbol]
        
        if symbol.startswith('KRW-') or symbol.startswith('USDT-'):
            name = symbol.replace('KRW-', '').replace('USDT-', '')
            self.stock_names_cache[symbol] = name
            return name
        
        if PYKRX_AVAILABLE:
            try:
                name = await asyncio.to_thread(
                    pykrx_stock.get_market_ticker_name, symbol
                )
                if name:
                    self.stock_names_cache[symbol] = name
                    return name
            except Exception as e:
                logger.debug(f"pykrx 获取名称失败 {symbol}: {e}")
        
        return symbol
    
    def format_stock_display(self, symbol: str, name: str) -> str:
        if symbol == name:
            return f"{symbol}"
        elif symbol.startswith('KRW-'):
            return f"{name} ({symbol})"
        else:
            return f"{name} ({symbol})"
    
    def _is_trading_time(self) -> bool:
        now = datetime.now()
        hour, minute = now.hour, now.minute
        if hour < 8 or hour > 14:
            return False
        if hour == 14 and minute > 30:
            return False
        return True
    
    async def _get_current_prices(self) -> Dict[str, float]:
        prices = {}
        if self.tracker:
            for symbol, pos in self.tracker.positions.items():
                prices[symbol] = pos['avg_entry_price']
        return prices
    
    # ==========================================
    # 告警功能（核心）
    # ==========================================
    
    async def send_alert(self, alert_data: Dict[str, Any]):
        """发送异常波动告警"""
        try:
            symbol = alert_data.get('symbol', 'N/A')
            name = alert_data.get('name', '')
            price_data = alert_data.get('price_data', {})
            
            if not name:
                name = await self.get_stock_name(symbol)
            
            display_name = self.format_stock_display(symbol, name)
            
            price = price_data.get('price', 0)
            change = price_data.get('change', 0)
            volume = price_data.get('volume', 0)
            high = price_data.get('high', 0)
            low = price_data.get('low', 0)
            
            emoji = "🟢" if change > 0 else "🔴"
            
            message = f"""
🚨 异常波动告警

{emoji} {display_name}

💹 当前价格: ₩{price:,}
📊 涨跌幅: {change:+.2f}%
📈 最高: ₩{high:,}
📉 最低: ₩{low:,}
💼 成交量: {volume:,}
⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔍 数据源: {price_data.get('source', 'pykrx')}
            """
            
            await self._broadcast(message)
            
            logger.info(f"✅ 告警已发送: {display_name} {change:+.2f}%")
            
        except Exception as e:
            logger.error(f"发送告警失败: {e}")
            import traceback
            traceback.print_exc()
    
    async def send_daily_report(self):
        """发送每日报告"""
        if not self.tracker or not self.pm:
            return
        
        try:
            current_prices = await self._get_current_prices()
            portfolio = self.pm.get_portfolio_by_type(current_prices)
            
            total = portfolio['total']
            stocks = portfolio['stocks']
            crypto = portfolio['crypto']
            
            stock_list = ""
            if stocks['count'] > 0:
                for symbol in self.pm.get_stock_positions().keys():
                    name = await self.get_stock_name(symbol)
                    stock_list += f"  • {name} ({symbol})\n"
            
            crypto_list = ""
            if crypto['count'] > 0:
                for symbol in self.pm.get_crypto_positions().keys():
                    name = await self.get_stock_name(symbol)
                    crypto_list += f"  • {name}\n"
            
            message = f"""
📅 安诚科技 Ancent AI 每日报告
{datetime.now().strftime('%Y-%m-%d')}

💼 组合总览:
  组合总值: ₩{_fw(total['portfolio_value'])}
  总盈亏: ₩{_fws(total['total_pnl'])} ({total['total_pnl_pct']:+.2f}%)

🇰🇷 韩国股票 ({stocks['count']} 只):
{stock_list if stock_list else "  无持仓\n"}
  市值: ₩{_fw(stocks['total_value'])}
  盈亏: ₩{_fws(stocks['unrealized_pnl'])} ({stocks['unrealized_pnl_pct']:+.2f}%)

🪙 加密货币 ({crypto['count']} 个):
{crypto_list if crypto_list else "  无持仓\n"}
  市值: ₩{_fw(crypto['total_value'])}
  盈亏: ₩{_fws(crypto['unrealized_pnl'])} ({crypto['unrealized_pnl_pct']:+.2f}%)

💰 现金余额: ₩{_fw(total['cash'])}

✅ 系统运行正常
            """
            
            await self._broadcast(message)
            
            logger.info("✅ 每日报告已发送")
            
        except Exception as e:
            logger.error(f"发送每日报告失败: {e}")
    
    # ==========================================
    # 命令处理器
    # ==========================================
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # 验证用户权限
        if not await self._check_authorization(update):
            return
        
        await update.message.reply_text("""
� 欢迎使用 安诚科技 Ancent AI 交易系统！

📊 可用命令:
  /status - 系统状态
  /portfolio - 投资组合
  /positions - 当前持仓
  /stocks - 股票持仓
  /crypto - 加密货币持仓
  /performance - 绩效指标
  
🤖 AI交易建议:
  /analyze 股票代码 - 分析特定股票
  /advice - 分析当前持仓
  
💬 自然语言对话:
  你可以直接跟我对话！例如：
  • "买入三星电子 10股 价格75000"
  • "给我BTC的建议"
  • "我当前的持仓怎么样？"
  • "帮我分析一下市场走势"
  • "卖出NAVER 5股 价格250000"
  
  /help - 帮助信息
        """)
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # 验证用户权限
        if not await self._check_authorization(update):
            return
        
        await update.message.reply_text(f"""
📊 系统状态

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔧 系统:
  • 数据源: pykrx (100%)
  • 持仓追踪: {'✅' if self.tracker else '⏸️'}
  • 交易时段: {'🟢' if self._is_trading_time() else '🔴'}
  • 名称缓存: {len(self.stock_names_cache)} 个
        """)
    
    async def cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # 验证用户权限
        if not await self._check_authorization(update):
            return
        
        if not self.tracker or not self.pm:
            await update.message.reply_text("❌ 投资组合未初始化")
            return
        
        try:
            current_prices = await self._get_current_prices()
            portfolio = self.pm.get_portfolio_by_type(current_prices)
            
            total = portfolio['total']
            stocks = portfolio['stocks']
            crypto = portfolio['crypto']
            
            await update.message.reply_text(f"""
💼 投资组合总览

💰 资金:
  现金: ₩{_fw(total['cash'])}
  持仓: ₩{_fw(total['position_value'])}
  总值: ₩{_fw(total['portfolio_value'])}

📈 收益:
  盈亏: ₩{_fws(total['total_pnl'])}
  收益率: {total['total_pnl_pct']:+.2f}%

📊 分布:
  🇰🇷 股票: {stocks['count']} 只
  🪙 加密: {crypto['count']} 个

⏰ {datetime.now().strftime('%H:%M:%S')}
            """)
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # 验证用户权限
        if not await self._check_authorization(update):
            return
        
        if not self.tracker:
            await update.message.reply_text("❌ 持仓追踪未初始化")
            return
        
        try:
            current_prices = await self._get_current_prices()
            positions = self.tracker.positions
            
            if not positions:
                await update.message.reply_text("📭 当前无持仓")
                return
            
            message = "📊 当前持仓\n\n"
            
            stock_positions = self.pm.get_stock_positions()
            if stock_positions:
                message += "🇰🇷 韩国股票:\n━━━━━━━━━━━━━━\n"
                
                for symbol, pos in stock_positions.items():
                    name = await self.get_stock_name(symbol)
                    display = self.format_stock_display(symbol, name)
                    
                    curr_price = current_prices.get(symbol, pos['avg_entry_price'])
                    curr_value = pos['quantity'] * curr_price
                    pnl = curr_value - pos['total_cost']
                    pnl_pct = (pnl / pos['total_cost']) * 100
                    
                    emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                    
                    message += f"\n{emoji} {display}\n"
                    message += f"  {pos['quantity']:.0f}주 × ₩{curr_price:,}\n"
                    message += f"  盈亏: ₩{_fws(pnl)} ({pnl_pct:+.2f}%)\n"
            
            crypto_positions = self.pm.get_crypto_positions()
            if crypto_positions:
                message += "\n🪙 加密货币:\n━━━━━━━━━━━━━━\n"
                
                for symbol, pos in crypto_positions.items():
                    name = await self.get_stock_name(symbol)
                    display = self.format_stock_display(symbol, name)
                    
                    curr_price = current_prices.get(symbol, pos['avg_entry_price'])
                    curr_value = pos['quantity'] * curr_price
                    pnl = curr_value - pos['total_cost']
                    pnl_pct = (pnl / pos['total_cost']) * 100
                    
                    emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                    
                    message += f"\n{emoji} {display}\n"
                    message += f"  {pos['quantity']:.4f} × ₩{curr_price:,}\n"
                    message += f"  盈亏: ₩{_fws(pnl)} ({pnl_pct:+.2f}%)\n"
            
            message += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"
            
            await update.message.reply_text(message)
            
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
    
    async def cmd_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # 验证用户权限
        if not await self._check_authorization(update):
            return
        
        if not self.tracker:
            await update.message.reply_text("❌ 持仓追踪未初始化")
            return
        
        try:
            current_prices = await self._get_current_prices()
            metrics = self.tracker.calculate_performance_metrics(current_prices)
            
            await update.message.reply_text(f"""
📈 绩效分析

💰 收益:
  组合市值: ₩{_fw(metrics['portfolio_value'])}
  总收益: ₩{_fws(metrics['total_return'])}
  收益率: {metrics['total_return_pct']:.2f}%

📊 交易:
  持仓: {int(metrics['num_positions'])}
  已平仓: {int(metrics['num_closed_trades'])}
  胜率: {metrics['win_rate']:.1f}%

📉 风险:
  夏普比率: {metrics['sharpe_ratio']:.2f}
  最大回撤: {metrics['max_drawdown']:.2f}%

⏰ {datetime.now().strftime('%H:%M:%S')}
            """)
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")
    
    async def cmd_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """分析股票并给出AI交易建议"""
        # 验证用户权限
        if not await self._check_authorization(update):
            return
        
        # 获取股票代码参数
        if not context.args:
            await update.message.reply_text(
                "请提供股票代码\n\n"
                "用法: /analyze 股票代码\n"
                "示例: /analyze 005930"
            )
            return
        
        symbol = context.args[0].strip()
        
        try:
            await update.message.reply_text(f"🔍 正在分析 {symbol}，请稍候...")
            
            # 获取股票名称
            name = await self.get_stock_name(symbol)
            
            # 获取股票价格（使用pykrx）
            if PYKRX_AVAILABLE:
                try:
                    from datetime import datetime as dt, timedelta
                    today = dt.now().strftime('%Y%m%d')
                    yesterday = (dt.now() - timedelta(days=5)).strftime('%Y%m%d')
                    
                    # 获取价格数据
                    df = await asyncio.to_thread(
                        pykrx_stock.get_market_ohlcv_by_date,
                        yesterday, today, symbol
                    )
                    
                    if df is None or df.empty:
                        await update.message.reply_text(f"❌ 无法获取 {symbol} 的价格数据")
                        return
                    
                    latest = df.iloc[-1]
                    current_price = float(latest['종가'])
                    prev_close = float(df.iloc[-2]['종가']) if len(df) > 1 else current_price
                    change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
                    volume = float(latest['거래량'])
                    avg_volume = float(df['거래량'].mean())
                    volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
                    
                    price_data = {
                        'price': current_price,
                        'change_pct': change_pct,
                        'volume': volume,
                        'volume_ratio': volume_ratio,
                        'high': float(latest['고가']),
                        'low': float(latest['저가'])
                    }
                    
                    # 计算简单技术指标
                    prices = df['종가'].tolist()
                    rsi = self._calculate_simple_rsi(prices[-14:]) if len(prices) >= 14 else 50
                    
                    technical_indicators = {
                        'rsi': rsi,
                        'macd': {'macd': 0}
                    }
                    
                    # 基础情绪分析
                    sentiment = {
                        'overall_sentiment': 'neutral',
                        'score': 0.0,
                        'article_count': 0
                    }
                    
                    # 生成AI建议
                    advice = await self.ai_advisor.generate_trading_advice(
                        symbol=symbol,
                        name=name,
                        current_price=current_price,
                        price_data=price_data,
                        technical_indicators=technical_indicators,
                        sentiment=sentiment,
                        news=[],
                        strategy_signals=[]
                    )
                    
                    # 格式化并发送
                    message = self.ai_advisor.format_advice_for_telegram(advice)
                    await update.message.reply_text(message)
                    
                except Exception as e:
                    logger.error(f"分析失败: {e}")
                    import traceback
                    traceback.print_exc()
                    await update.message.reply_text(f"❌ 分析失败: {e}")
            else:
                await update.message.reply_text("❌ pykrx 未安装，无法获取价格数据")
                
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            await update.message.reply_text(f"❌ 分析出错: {e}")
    
    def _calculate_simple_rsi(self, prices: list, period: int = 14) -> float:
        """简单RSI计算"""
        if len(prices) < period:
            return 50.0
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    async def cmd_advice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """显示当前持仓的AI交易建议"""
        # 验证用户权限
        if not await self._check_authorization(update):
            return
        
        if not self.tracker or not self.pm:
            await update.message.reply_text("❌ 持仓追踪未初始化")
            return
        
        try:
            await update.message.reply_text("🤖 正在分析您的持仓，请稍候...")
            
            positions = self.tracker.positions
            if not positions:
                await update.message.reply_text("📭 当前无持仓，无法生成建议")
                return
            
            # 分析每个持仓（最多3个）
            count = 0
            for symbol, pos in list(positions.items())[:3]:
                count += 1
                
                name = await self.get_stock_name(symbol)
                current_price = pos['avg_entry_price']
                
                # 简化的分析
                advice = await self.ai_advisor.generate_trading_advice(
                    symbol=symbol,
                    name=name,
                    current_price=current_price,
                    price_data={'change_pct': 0, 'volume_ratio': 1.0},
                    technical_indicators={'rsi': 50, 'macd': {'macd': 0}},
                    sentiment={'overall_sentiment': 'neutral', 'score': 0, 'article_count': 0}
                )
                
                message = self.ai_advisor.format_advice_for_telegram(advice)
                await update.message.reply_text(message)
                
                # 短暂延迟避免刷屏
                if count < len(positions):
                    await asyncio.sleep(1)
            
            if len(positions) > 3:
                await update.message.reply_text(
                    f"ℹ️ 仅显示前3个持仓的建议\n"
                    f"总持仓数: {len(positions)}\n\n"
                    f"使用 /analyze 股票代码 分析特定股票"
                )
                
        except Exception as e:
            logger.error(f"Advice error: {e}")
            await update.message.reply_text(f"❌ 生成建议失败: {e}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理自然语言消息"""
        # 验证用户权限
        if not await self._check_authorization(update):
            return
        
        user_message = update.message.text
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        
        logger.info(f"收到消息 from {username} (ID: {user_id}): {user_message}")
        
        try:
            # 使用对话处理器处理消息（30秒全局超时，防止LLM/网络卡死阻塞后续消息）
            try:
                response = await asyncio.wait_for(
                    self.conversation_handler.process_message(user_message, user_id),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"⏱ 消息处理超时(30s): {user_message[:40]}")
                response = "⏱ 响应超时，请稍后重试"
            
            # 发送回复
            await update.message.reply_text(response)

            # 卖出/平仓后若持仓清空，立即取消置顶（不等30秒轮询）
            # 若仍有持仓（例如只卖了一部分或还有其他币），则立即刷新置顶内容
            has_pos = bool(
                self.conversation_handler.tracker
                and self.conversation_handler.tracker.positions
            )
            
            logger.debug(f"📌 检查持仓状态: has_pos={has_pos}, positions={self.conversation_handler.tracker.positions if self.conversation_handler.tracker else None}")
            
            if not has_pos:
                # 清仓：取消置顶
                # 确保当前聊天也在扫描列表内（兼容机器人重启后内存丢失的场景）
                current_chat_id = str(update.effective_chat.id)
                _unpin_targets = list(dict.fromkeys(
                    list(self.broadcast_ids) + [current_chat_id]
                ))
                logger.info(f"📌 持仓已清空，准备取消置顶。targets={_unpin_targets}, _pinned_msg_ids={self._pinned_msg_ids}")
                
                for cid in _unpin_targets:
                    mid = self._pinned_msg_ids.pop(cid, None)
                    if mid is not None:
                        try:
                            await self.app.bot.unpin_chat_message(chat_id=cid, message_id=mid)
                            logger.info(f"📌 平仓后立即取消置顶 cid={cid} mid={mid}")
                        except Exception as _upe:
                            logger.warning(f"取消置顶失败 cid={cid}: {_upe}，尝试删除消息")
                            try:
                                await self.app.bot.delete_message(chat_id=cid, message_id=mid)
                                logger.info(f"📌 置顶消息已删除 cid={cid} mid={mid}")
                            except Exception as _de:
                                logger.warning(f"删除置顶消息也失败 cid={cid}: {_de}")
                    else:
                        # 没有记录的消息ID → 兜底方案
                        logger.info(f"📌 _pinned_msg_ids无记录 cid={cid}，尝试多种方式取消置顶")
                        try:
                            # 私聊中：unpin_chat_message() 不传 message_id 会取消当前置顶的消息
                            await self.app.bot.unpin_chat_message(chat_id=cid)
                            logger.info(f"📌 已取消 cid={cid} 当前置顶消息（无message_id方式）")
                        except Exception as _upe1:
                            logger.debug(f"unpin_chat_message(无mid)失败: {_upe1}")
                            # 群组中：使用 unpin_all
                            try:
                                await self.app.bot.unpin_all_chat_messages(chat_id=cid)
                                logger.info(f"📌 已取消 cid={cid} 全部置顶（unpin_all）")
                            except Exception as _upa:
                                logger.warning(f"📌 所有取消置顶方式均失败 cid={cid}: {_upa}")
            else:
                # 仍有持仓：立即刷新置顶内容
                current_text = await self.conversation_handler._build_pinned_summary()
                if current_text:
                    for cid in self.broadcast_ids:
                        mid = self._pinned_msg_ids.get(cid)
                        if mid:
                            try:
                                await self.app.bot.edit_message_text(
                                    chat_id=cid,
                                    message_id=mid,
                                    text=current_text
                                )
                                logger.info(f"📌 交易后立即刷新置顶 cid={cid} mid={mid}")
                            except Exception as _ee:
                                logger.warning(f"刷新置顶失败 cid={cid}: {_ee}")
            
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            import traceback
            traceback.print_exc()
            await update.message.reply_text(
                f"❌ 处理消息时出错：{str(e)[:300]}"
            )
    
    # ==========================================
    # 运行
    # ==========================================
    
    async def run(self):
        logger.info("🚀 启动 Telegram Bot...")
        
        # 自动读取环境变量中的代理配置（适配 WSL2/防火墙环境）
        _proxy_url = os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY') or None
        if _proxy_url:
            logger.info(f"🔗 使用代理连接 Telegram: {_proxy_url}")
            _request = HTTPXRequest(proxy=_proxy_url)
            self.app = Application.builder().token(self.token).request(_request).build()
        else:
            self.app = Application.builder().token(self.token).build()
        
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("portfolio", self.cmd_portfolio))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("performance", self.cmd_performance))
        self.app.add_handler(CommandHandler("analyze", self.cmd_analyze))
        self.app.add_handler(CommandHandler("advice", self.cmd_advice))
        
        # 添加消息处理器（处理所有非命令的文本消息）
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        logger.info("✅ Telegram Bot 运行中")

        # ★ 已删除市场价格定时刷新任务 - 统一使用实时查询，无需缓存刷新 ★

        # 启动 Alpaca WebSocket 实时美股推送（若已配置 ALPACA_API_KEY）
        if self.us_hk_fetcher and getattr(self.us_hk_fetcher, 'alpaca_ws', None):
            asyncio.create_task(self.us_hk_fetcher.start_alpaca_ws())
            logger.info("📡 Alpaca WebSocket 实时美股推送任务已挂载")

        # 启动 FUTU 港股实时推送（若 FutuOpenD 已在本机运行）
        if self.us_hk_fetcher and getattr(self.us_hk_fetcher, 'futu_client', None):
            self.us_hk_fetcher.start_futu_ws()
            logger.info("📡 FUTU 港股实时推送任务已挂载")

        # 盈亏广播函数（供高频告警循环使用）
        async def _broadcast_pnl(text: str):
            try:
                await self._broadcast(text)
            except Exception as _e:
                logger.warning(f"盈亏推送失败: {_e}")

        # 启动 +3%/-2% 高频盈亏告警循环（每30秒扫描，穿越阈值立即推送）
        asyncio.create_task(
            self.conversation_handler.start_pnl_alert_loop(_broadcast_pnl, interval=5)
        )
        logger.info("🔔 盈亏高频告警任务已挂载（每5秒扫描，+3%/-2%触发推送）")

        # 启动置顶持仓动态循环（每30秒刷新，对所有广播用户发送/编辑置顶消息）
        async def _pinned_position_loop():
            logger.info("📌 置顶持仓动态循环已启动（每30秒刷新，广播全部用户）")
            while True:
                await asyncio.sleep(30)
                try:
                    has_pos = bool(
                        self.conversation_handler.tracker
                        and self.conversation_handler.tracker.positions
                    )
                    text = await self.conversation_handler._build_pinned_summary() if has_pos else None

                    for cid in self.broadcast_ids:
                        try:
                            if has_pos and text:
                                mid = self._pinned_msg_ids.get(cid)
                                if mid is None:
                                    # 首次：发送新消息并置顶
                                    msg = await self.app.bot.send_message(chat_id=cid, text=text)
                                    self._pinned_msg_ids[cid] = msg.message_id
                                    try:
                                        await self.app.bot.pin_chat_message(
                                            chat_id=cid,
                                            message_id=msg.message_id,
                                            disable_notification=True,
                                        )
                                    except Exception as _pe:
                                        logger.warning(f"置顶失败 cid={cid}: {_pe}")
                                    logger.info(f"📌 置顶消息已创建 cid={cid} msg_id={msg.message_id}")
                                else:
                                    # 后续：编辑已有消息
                                    try:
                                        await self.app.bot.edit_message_text(
                                            chat_id=cid,
                                            message_id=mid,
                                            text=text,
                                        )
                                    except Exception as _ee:
                                        logger.warning(f"编辑置顶失败 cid={cid}: {_ee}，将重新创建")
                                        self._pinned_msg_ids.pop(cid, None)
                            else:
                                # 无仓位：取消置顶并清除
                                mid = self._pinned_msg_ids.pop(cid, None)
                                if mid is not None:
                                    try:
                                        await self.app.bot.unpin_chat_message(chat_id=cid, message_id=mid)
                                    except Exception:
                                        pass
                                    logger.info(f"📌 持仓清空，cid={cid} 置顶已取消")
                                else:
                                    # 无记录时兜底：强制取消所有置顶
                                    try:
                                        await self.app.bot.unpin_all_chat_messages(chat_id=cid)
                                        logger.info(f"📌 持仓清空，cid={cid} unpin_all 兜底取消置顶")
                                    except Exception as _upa:
                                        logger.debug(f"unpin_all 兜底失败 cid={cid}: {_upa}")
                        except Exception as _ce:
                            logger.error(f"置顶循环 cid={cid} 异常: {_ce}")
                except Exception as _le:
                    logger.error(f"置顶持仓循环异常: {_le}")

        asyncio.create_task(_pinned_position_loop())
        logger.info("📌 置顶持仓动态任务已挂载（每30秒刷新）")
        
        try:
            await self._broadcast("🤖 安诚科技 Ancent AI 已启动\n\n发送 /start 查看命令")
        except:
            pass
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()


if __name__ == '__main__':
    from dotenv import load_dotenv
    
    load_dotenv()
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("❌ 请配置 .env 文件")
        print("   需要设置：")
        print("   TELEGRAM_BOT_TOKEN=你的bot_token")
        print("   TELEGRAM_CHAT_ID=你的chat_id")
        print("   TELEGRAM_AUTHORIZED_USERS=你的用户ID （可选，推荐设置）")
        sys.exit(1)
    
    # 读取授权用户列表
    authorized_users_str = os.getenv('TELEGRAM_AUTHORIZED_USERS', '')
    authorized_users = None
    if authorized_users_str:
        try:
            authorized_users = [int(uid.strip()) for uid in authorized_users_str.split(',') if uid.strip()]
            print(f"✅ 已启用用户验证，授权用户数: {len(authorized_users)}")
            print(f"   授权用户ID: {authorized_users}")
        except ValueError:
            print("❌ TELEGRAM_AUTHORIZED_USERS 格式错误，应为逗号分隔的数字")
            print("   示例: TELEGRAM_AUTHORIZED_USERS=123456789,987654321")
            sys.exit(1)
    else:
        print("⚠️  警告：未设置 TELEGRAM_AUTHORIZED_USERS")
        print("   任何人都可以使用你的bot！")
        print("   建议在 .env 中添加：TELEGRAM_AUTHORIZED_USERS=你的用户ID")
        print("")
        print("如何获取你的用户ID：")
        print("   1. 在Telegram中搜索 @userinfobot")
        print("   2. 与它对话即可获得你的用户ID")
        print("")
    
    # 初始资金 0（通过"调整总资产"命令设置）
    tracker = PositionTracker(initial_capital=0)

    # 自动加载上次保存的账户状态（如存在）
    import os as _os
    _state_file = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'data', 'tracker_state.json')
    _loaded = tracker.load_state(_state_file)
    if _loaded:
        print(f"📂 已恢复账户状态：现金 ₩{tracker.cash:,.0f}，持仓 {len(tracker.positions)} 个")
    else:
        print(f"🆕 首次启动：初始资金 ₩{tracker.initial_capital:,.0f}")
    
    # 创建bot（带用户验证）
    bot = OpenClawTelegramBot(
        token=token,
        chat_id=chat_id,
        tracker=tracker,
        authorized_users=authorized_users,
        state_file=_state_file,
    )
    
    asyncio.run(bot.run())
