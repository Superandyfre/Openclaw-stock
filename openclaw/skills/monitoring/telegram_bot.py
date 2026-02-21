#!/usr/bin/env python3
"""
OpenClaw Telegram Bot
提供实时交互和通知功能
"""
import os
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
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
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.error("python-telegram-bot 未安装")

from openclaw.skills.execution.position_tracker import PositionTracker
from openclaw.core.portfolio_manager import PortfolioManager


class OpenClawTelegramBot:
    """OpenClaw Telegram Bot"""
    
    def __init__(
        self,
        token: str,
        chat_id: str,
        tracker: Optional[PositionTracker] = None,
        pm: Optional[PortfolioManager] = None
    ):
        if not TELEGRAM_AVAILABLE:
            raise ImportError("请安装: pip install python-telegram-bot")
        
        self.token = token
        self.chat_id = chat_id
        self.tracker = tracker
        self.pm = pm
        
        self.bot = Bot(token=token)
        self.app = None
        
        logger.info("✅ Telegram Bot 初始化成功")
    
    # ==========================================
    # 命令处理器
    # ==========================================
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        welcome_message = """
🦞 欢迎使用 OpenClaw 韩股交易系统！

📊 可用命令:
  /status - 查看系统状态
  /portfolio - 查看投资组合
  /positions - 查看当前持仓
  /performance - 查看绩效指标
  /help - 显示帮助信息

🔔 功能:
  • 实时异常波动告警
  • 每日组合报告
  • 交互式查询

💡 提示: 发送 /help 查看详细使用说明
        """
        await update.message.reply_text(welcome_message)
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /help 命令"""
        help_message = """
📖 OpenClaw 使用指南

🔍 查询命令:
  /status - 系统运行状态
  /portfolio - 投资组合总览
  /positions - 详细持仓列表
  /performance - 绩效分析
  /stocks - 韩股持仓
  /crypto - 加密货币持仓

⚙️ 设置命令:
  /alert on|off - 开启/关闭告警
  /threshold <数值> - 设置告警阈值(%)

📊 报告命令:
  /report - 生成当前报告
  /daily - 每日摘要

💡 使用技巧:
  • 直接发送股票代码（如: 005930）查询实时价格
  • 告警默认阈值为 ±2%
  • 每日报告时间: 09:00 (可配置)
        """
        await update.message.reply_text(help_message)
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /status 命令"""
        status_message = f"""
📊 OpenClaw 系统状态

⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔧 系统:
  • 数据源: pykrx (100%)
  • 缓存: Redis
  • AI 模型: GenAI, FinBERT

✅ 服务状态:
  • Telegram Bot: 运行中
  • 韩股监控: {'运行中' if self.tracker else '未启动'}
  • 持仓追踪: {'运行中' if self.pm else '未启动'}

📈 市场:
  • KOSPI: 查询中...
  • 交易时段: {'是' if self._is_trading_time() else '否'}
        """
        await update.message.reply_text(status_message)
    
    async def cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /portfolio 命令"""
        if not self.tracker or not self.pm:
            await update.message.reply_text("❌ 投资组合未初始化")
            return
        
        try:
            # 获取当前价格（实际应该从 pykrx 获取）
            current_prices = self._get_current_prices()
            
            # 获取组合数据
            portfolio = self.pm.get_portfolio_by_type(current_prices)
            
            total = portfolio['total']
            
            message = f"""
💼 投资组合总览

💰 资金状况:
  现金余额: ₩{total['cash']:,.0f}
  持仓市值: ₩{total['position_value']:,.0f}
  组合总值: ₩{total['portfolio_value']:,.0f}

📈 收益情况:
  总盈亏: ₩{total['total_pnl']:,.0f}
  收益率: {total['total_pnl_pct']:+.2f}%

📊 持仓分布:
  韩国股票: {portfolio['stocks']['count']} 只
  加密货币: {portfolio['crypto']['count']} 个

⏰ 更新时间: {datetime.now().strftime('%H:%M:%S')}
            """
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Portfolio 查询失败: {e}")
            await update.message.reply_text(f"❌ 查询失败: {e}")
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /positions 命令"""
        if not self.tracker:
            await update.message.reply_text("❌ 持仓追踪未初始化")
            return
        
        try:
            current_prices = self._get_current_prices()
            
            # 获取所有持仓
            positions = self.tracker.positions
            
            if not positions:
                await update.message.reply_text("📭 当前无持仓")
                return
            
            message = "📊 当前持仓明细\n\n"
            
            # 股票
            stock_positions = self.pm.get_stock_positions()
            if stock_positions:
                message += "📈 韩国股票:\n"
                for symbol, pos in stock_positions.items():
                    current_price = current_prices.get(symbol, pos['avg_entry_price'])
                    current_value = pos['quantity'] * current_price
                    pnl = current_value - pos['total_cost']
                    pnl_pct = (pnl / pos['total_cost']) * 100
                    
                    emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                    message += f"\n{emoji} {symbol}\n"
                    message += f"  数量: {pos['quantity']:.0f}주\n"
                    message += f"  成本: ₩{pos['total_cost']:,.0f}\n"
                    message += f"  市值: ₩{current_value:,.0f}\n"
                    message += f"  盈亏: ₩{pnl:,.0f} ({pnl_pct:+.2f}%)\n"
            
            # 加密货币
            crypto_positions = self.pm.get_crypto_positions()
            if crypto_positions:
                message += "\n🪙 加密货币:\n"
                for symbol, pos in crypto_positions.items():
                    current_price = current_prices.get(symbol, pos['avg_entry_price'])
                    current_value = pos['quantity'] * current_price
                    pnl = current_value - pos['total_cost']
                    pnl_pct = (pnl / pos['total_cost']) * 100
                    
                    emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                    message += f"\n{emoji} {symbol}\n"
                    message += f"  数量: {pos['quantity']:.4f}\n"
                    message += f"  成本: ₩{pos['total_cost']:,.0f}\n"
                    message += f"  市值: ₩{current_value:,.0f}\n"
                    message += f"  盈亏: ₩{pnl:,.0f} ({pnl_pct:+.2f}%)\n"
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Positions 查询失败: {e}")
            await update.message.reply_text(f"❌ 查询失败: {e}")
    
    async def cmd_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /performance 命令"""
        if not self.tracker:
            await update.message.reply_text("❌ 持仓追踪未初始化")
            return
        
        try:
            current_prices = self._get_current_prices()
            metrics = self.tracker.calculate_performance_metrics(current_prices)
            
            message = f"""
📈 绩效分析

💰 收益表现:
  组合市值: ₩{metrics['portfolio_value']:,.0f}
  总收益: ₩{metrics['total_return']:,.0f}
  收益率: {metrics['total_return_pct']:.2f}%

📊 交易统计:
  持仓数量: {int(metrics['num_positions'])}
  已平仓数: {int(metrics['num_closed_trades'])}
  胜率: {metrics['win_rate']:.1f}%

📉 风险指标:
  夏普比率: {metrics['sharpe_ratio']:.2f}
  最大回撤: {metrics['max_drawdown']:.2f}%

⏰ 更新: {datetime.now().strftime('%H:%M:%S')}
            """
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Performance 查询失败: {e}")
            await update.message.reply_text(f"❌ 查询失败: {e}")
    
    # ==========================================
    # 通知功能
    # ==========================================
    
    async def send_alert(self, alert_data: Dict[str, Any]):
        """发送告警通知"""
        try:
            symbol = alert_data.get('symbol', 'N/A')
            name = alert_data.get('name', '')
            price_data = alert_data.get('price_data', {})
            
            price = price_data.get('price', 0)
            change = price_data.get('change', 0)
            
            emoji = "🟢" if change > 0 else "🔴"
            
            message = f"""
🚨 异常波动告警

{emoji} {symbol} ({name})

💹 当前价格: ₩{price:,}
📊 涨跌幅: {change:+.2f}%
⏰ 时间: {datetime.now().strftime('%H:%M:%S')}

🔍 数据源: {price_data.get('source', 'pykrx')}
            """
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message
            )
            
            logger.info(f"✅ 告警已发送: {symbol} {change:+.2f}%")
            
        except Exception as e:
            logger.error(f"发送告警失败: {e}")
    
    async def send_daily_report(self):
        """发送每日报告"""
        if not self.tracker or not self.pm:
            return
        
        try:
            current_prices = self._get_current_prices()
            portfolio = self.pm.get_portfolio_by_type(current_prices)
            
            total = portfolio['total']
            stocks = portfolio['stocks']
            crypto = portfolio['crypto']
            
            message = f"""
📅 OpenClaw 每日报告
{datetime.now().strftime('%Y-%m-%d')}

💼 组合总览:
  组合总值: ₩{total['portfolio_value']:,.0f}
  总盈亏: ₩{total['total_pnl']:,.0f} ({total['total_pnl_pct']:+.2f}%)

📈 韩国股票:
  持仓: {stocks['count']} 只
  市值: ₩{stocks['total_value']:,.0f}
  盈亏: ₩{stocks['unrealized_pnl']:,.0f} ({stocks['unrealized_pnl_pct']:+.2f}%)

🪙 加密货币:
  持仓: {crypto['count']} 个
  市值: ₩{crypto['total_value']:,.0f}
  盈亏: ₩{crypto['unrealized_pnl']:,.0f} ({crypto['unrealized_pnl_pct']:+.2f}%)

💰 现金余额: ₩{total['cash']:,.0f}

✅ 系统运行正常
            """
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message
            )
            
            logger.info("✅ 每日报告已发送")
            
        except Exception as e:
            logger.error(f"发送每日报告失败: {e}")
    
    # ==========================================
    # 辅助方法
    # ==========================================
    
    def _is_trading_time(self) -> bool:
        """检查是否在交易时间"""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        
        # 韩国交易时间: 09:00-15:30 KST
        # 北京时间: 08:00-14:30 CST
        if hour < 8 or hour > 14:
            return False
        if hour == 14 and minute > 30:
            return False
        return True
    
    def _get_current_prices(self) -> Dict[str, float]:
        """获取当前价格（示例，实际应该从 pykrx 获取）"""
        # TODO: 集成 pykrx 实时价格
        prices = {}
        
        if self.tracker:
            for symbol, pos in self.tracker.positions.items():
                # 临时使用入场价格
                prices[symbol] = pos['avg_entry_price']
        
        return prices
    
    # ==========================================
    # 运行
    # ==========================================
    
    async def run(self):
        """运行 Bot"""
        logger.info("🚀 启动 Telegram Bot...")
        
        # 创建应用
        self.app = Application.builder().token(self.token).build()
        
        # 注册命令处理器
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("portfolio", self.cmd_portfolio))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("performance", self.cmd_performance))
        
        # 启动
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        logger.info("✅ Telegram Bot 运行中...")
        logger.info(f"   Chat ID: {self.chat_id}")
        
        # 发送启动通知
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text="🦞 OpenClaw 系统已启动\n\n发送 /help 查看可用命令"
            )
        except:
            pass
        
        # 保持运行
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 停止 Telegram Bot...")
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()


# 测试
if __name__ == '__main__':
    import sys
    from dotenv import load_dotenv
    
    load_dotenv()
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("❌ 请先配置 .env 文件:")
        print("   TELEGRAM_BOT_TOKEN=你的token")
        print("   TELEGRAM_CHAT_ID=你的chat_id")
        sys.exit(1)
    
    # 创建测试持仓
    tracker = PositionTracker(initial_capital=10000000)
    pm = PortfolioManager(tracker)
    
    # 添加测试持仓
    tracker.open_position('005930', 10, 181200)
    tracker.open_position('KRW-BTC', 0.05, 60000000)
    
    # 启动 Bot
    bot = OpenClawTelegramBot(token, chat_id, tracker, pm)
    
    asyncio.run(bot.run())
