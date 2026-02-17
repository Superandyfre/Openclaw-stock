"""
Alert manager for notifications
2026 Edition with KRW currency support
"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from loguru import logger

try:
    from ..utils.currency_converter import get_converter
    CURRENCY_CONVERTER_AVAILABLE = True
except ImportError:
    CURRENCY_CONVERTER_AVAILABLE = False
    logger.warning("Currency converter not available")


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertManager:
    """Manages alerts and notifications with KRW currency support"""
    
    def __init__(
        self,
        telegram_bot_token: str = "",
        telegram_chat_id: str = "",
        email_enabled: bool = False
    ):
        """
        Initialize alert manager
        
        Args:
            telegram_bot_token: Telegram bot token
            telegram_chat_id: Telegram chat ID
            email_enabled: Enable email notifications
        """
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.email_enabled = email_enabled
        self.alerts: List[Dict[str, Any]] = []
        
        # Currency converter for KRW formatting
        self.currency_converter = None
        if CURRENCY_CONVERTER_AVAILABLE:
            try:
                self.currency_converter = get_converter()
            except Exception as e:
                logger.warning(f"Failed to initialize currency converter: {e}")
    
    async def send_alert(
        self,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        data: Dict[str, Any] = None
    ):
        """
        Send an alert
        
        Args:
            message: Alert message
            level: Alert severity level
            data: Additional data
        """
        alert = {
            "message": message,
            "level": level.value,
            "data": data or {},
            "timestamp": datetime.now().isoformat()
        }
        
        self.alerts.append(alert)
        
        # Log alert
        if level == AlertLevel.CRITICAL:
            logger.critical(f"🚨 {message}")
        elif level == AlertLevel.WARNING:
            logger.warning(f"⚠️  {message}")
        else:
            logger.info(f"ℹ️  {message}")
        
        # Send to configured channels
        if level in [AlertLevel.WARNING, AlertLevel.CRITICAL]:
            await self._send_to_telegram(alert)
            
            if self.email_enabled:
                await self._send_to_email(alert)
        
        # Keep only last 1000 alerts
        if len(self.alerts) > 1000:
            self.alerts = self.alerts[-1000:]
    
    async def _send_to_telegram(self, alert: Dict[str, Any]):
        """Send alert to Telegram"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.debug("Telegram not configured, skipping notification")
            return
        
        try:
            # Format message
            emoji_map = {
                "info": "ℹ️",
                "warning": "⚠️",
                "critical": "🚨"
            }
            
            emoji = emoji_map.get(alert['level'], "📢")
            formatted_message = f"{emoji} *{alert['level'].upper()}*\n\n{alert['message']}"
            
            if alert['data']:
                formatted_message += f"\n\n```json\n{alert['data']}\n```"
            
            # Send via Telegram Bot API
            # In production, would use python-telegram-bot library
            logger.info(f"[TELEGRAM] Would send: {formatted_message}")
        
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
    
    async def _send_to_email(self, alert: Dict[str, Any]):
        """Send alert via email"""
        try:
            # In production, would use SMTP
            logger.info(f"[EMAIL] Would send: {alert['message']}")
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    def generate_report(
        self,
        portfolio_metrics: Dict[str, Any],
        market_summary: Dict[str, Any]
    ) -> str:
        """
        Generate formatted report with KRW currency
        
        Args:
            portfolio_metrics: Portfolio performance metrics
            market_summary: Market summary data
        
        Returns:
            Formatted report text
        """
        # Helper functions for formatting
        fmt_krw = self._format_krw
        fmt_pct = self._format_percentage
        
        report = "📊 **OpenClaw Trading Report**\n\n"
        
        # Portfolio section
        report += "**Portfolio Performance (₩ Korean Won):**\n"
        report += f"- Portfolio Value: {fmt_krw(portfolio_metrics.get('portfolio_value', 0))}\n"
        
        total_return = portfolio_metrics.get('total_return', 0)
        total_return_pct = portfolio_metrics.get('total_return_pct', 0)
        report += f"- Total Return: {fmt_krw(total_return)} ({fmt_pct(total_return_pct)})\n"
        
        report += f"- Realized P&L: {fmt_krw(portfolio_metrics.get('realized_pnl', 0))}\n"
        report += f"- Unrealized P&L: {fmt_krw(portfolio_metrics.get('unrealized_pnl', 0))}\n"
        report += f"- Cash: {fmt_krw(portfolio_metrics.get('cash', 0))}\n"
        report += f"- Open Positions: {portfolio_metrics.get('num_positions', 0)}\n"
        report += f"- Win Rate: {portfolio_metrics.get('win_rate', 0):.1f}%\n"
        report += f"- Sharpe Ratio: {portfolio_metrics.get('sharpe_ratio', 0):.2f}\n"
        report += f"- Max Drawdown: {portfolio_metrics.get('max_drawdown', 0):.2f}%\n\n"
        
        # Market section
        report += "**Market Summary:**\n"
        report += f"- Active Stocks: {market_summary.get('stock_count', 0)}\n"
        report += f"- Active Cryptos: {market_summary.get('crypto_count', 0)}\n"
        report += f"- Anomalies Detected: {market_summary.get('anomaly_count', 0)}\n"
        report += f"- Signals Generated: {market_summary.get('signal_count', 0)}\n\n"
        
        report += f"_Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
        
        return report
    
    def get_recent_alerts(self, count: int = 10, level: AlertLevel = None) -> List[Dict[str, Any]]:
        """
        Get recent alerts
        
        Args:
            count: Number of alerts to return
            level: Filter by alert level
        
        Returns:
            List of recent alerts
        """
        alerts = self.alerts
        
        if level:
            alerts = [a for a in alerts if a['level'] == level.value]
        
        return alerts[-count:]
    
    async def generate_short_term_signal_alert(
        self,
        symbol: str,
        signal: Dict[str, Any]
    ) -> str:
        """
        Generate short-term trading signal alert with KRW prices
        
        Args:
            symbol: Asset symbol
            signal: Trading signal details
        
        Returns:
            Formatted alert message
        """
        action = signal.get('action', 'HOLD')
        strategy = signal.get('strategy', 'Unknown')
        
        # Ensure confidence is in 0-1 range, then scale to 1-10
        confidence = signal.get('confidence', 0)
        if confidence > 1:
            # Already on 1-10 scale
            confidence_score = min(10, max(0, confidence))
        else:
            # On 0-1 scale, convert to 1-10
            confidence_score = confidence * 10
        
        emoji_map = {
            'BUY': '🔥',
            'SELL': '❌',
            'HOLD': '⏸️'
        }
        
        emoji = emoji_map.get(action, '📊')
        
        # Convert prices to KRW
        price = await self._convert_price(symbol, signal.get('price', 0))
        stop_loss = await self._convert_price(symbol, signal.get('stop_loss', 0))
        take_profit = await self._convert_price(symbol, signal.get('take_profit', 0))
        
        # Format prices
        fmt_krw = self._format_krw
        fmt_pct = self._format_percentage
        
        alert = f"{emoji} **SHORT-TERM OPPORTUNITY: {symbol}**\n\n"
        alert += f"**Strategy**: {strategy}\n"
        alert += f"**Action**: {action}\n"
        alert += f"**Entry Price**: {fmt_krw(price)}\n"
        
        if action == 'BUY':
            # Calculate percentages safely
            if price > 0:
                stop_loss_pct = ((price - stop_loss) / price) if stop_loss > 0 else 0
                take_profit_pct = ((take_profit - price) / price) if take_profit > 0 else 0
                
                alert += f"**Stop Loss**: {fmt_krw(stop_loss)} ({fmt_pct(-stop_loss_pct)})\n"
                alert += f"**Take Profit**: {fmt_krw(take_profit)} ({fmt_pct(take_profit_pct)})\n"
            
            alert += f"**Expected Hold**: {signal.get('max_hold_hours', 6)} hours\n"
        
        alert += f"**Confidence**: {confidence_score:.0f}/10\n\n"
        alert += f"**Reason**: {signal.get('reason', 'N/A')}\n\n"
        alert += f"⚡ _Quick decision required - short-term opportunity!_"
        
        return alert
    
    async def generate_position_alert(
        self,
        symbol: str,
        position_type: str,
        details: Dict[str, Any]
    ) -> str:
        """
        Generate position management alert with KRW prices
        
        Args:
            symbol: Asset symbol
            position_type: Type of alert (stop_loss, take_profit, time_limit)
            details: Position details
        
        Returns:
            Formatted alert message
        """
        emoji_map = {
            'stop_loss': '🛑',
            'take_profit': '✅',
            'time_limit': '⏰',
            'trailing_stop': '📈'
        }
        
        emoji = emoji_map.get(position_type, '📊')
        
        # Convert prices to KRW
        entry_price = await self._convert_price(symbol, details.get('entry_price', 0))
        exit_price = await self._convert_price(symbol, details.get('exit_price', 0))
        pnl = await self._convert_price(symbol, details.get('pnl', 0))
        
        # Format prices
        fmt_krw = self._format_krw
        fmt_pct = self._format_percentage
        
        alert = f"{emoji} **POSITION UPDATE: {symbol}**\n\n"
        
        pnl_pct = details.get('pnl_pct', 0) / 100  # Convert to decimal
        
        if position_type == 'stop_loss':
            alert += "**Stop Loss Hit**\n"
            alert += f"Entry: {fmt_krw(entry_price)}\n"
            alert += f"Exit: {fmt_krw(exit_price)}\n"
            alert += f"Loss: {fmt_krw(pnl)} ({fmt_pct(pnl_pct)})\n"
        
        elif position_type == 'take_profit':
            alert += "**Take Profit Target Hit!**\n"
            alert += f"Entry: {fmt_krw(entry_price)}\n"
            alert += f"Exit: {fmt_krw(exit_price)}\n"
            alert += f"Profit: {fmt_krw(pnl)} ({fmt_pct(pnl_pct)})\n"
        
        elif position_type == 'time_limit':
            alert += "**Time Limit Reached**\n"
            alert += f"Held for: {details.get('hours_held', 0):.1f} hours\n"
            alert += f"Current P&L: {fmt_krw(pnl)} ({fmt_pct(pnl_pct)})\n"
            alert += "Position closed automatically.\n"
        
        alert += f"\n_Position closed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
        
        return alert
    
    # Helper methods for KRW formatting
    
    async def _convert_price(self, symbol: str, price: float) -> float:
        """Convert price to KRW"""
        if self.currency_converter:
            try:
                return await self.currency_converter.convert_price(symbol, price)
            except Exception as e:
                logger.warning(f"Price conversion failed: {e}")
        return price
    
    def _format_krw(self, amount: float) -> str:
        """Format amount as KRW"""
        if self.currency_converter:
            return self.currency_converter.format_krw(amount)
        return f"₩{amount:,.0f}"
    
    def _format_percentage(self, pct: float) -> str:
        """Format percentage with sign"""
        if self.currency_converter:
            return self.currency_converter.format_change(pct)
        
        # Fallback formatting
        pct_value = pct * 100
        if pct >= 0:
            return f"+{pct_value:.2f}%"
        else:
            return f"{pct_value:.2f}%"
