"""
Alert manager for notifications
"""
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from enum import Enum
from loguru import logger


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertManager:
    """Manages alerts and notifications"""
    
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
        Generate formatted report
        
        Args:
            portfolio_metrics: Portfolio performance metrics
            market_summary: Market summary data
        
        Returns:
            Formatted report text
        """
        report = "📊 **OpenClaw Trading Report**\n\n"
        
        # Portfolio section
        report += "**Portfolio Performance:**\n"
        report += f"- Portfolio Value: ${portfolio_metrics.get('portfolio_value', 0):,.2f}\n"
        report += f"- Total Return: ${portfolio_metrics.get('total_return', 0):,.2f} ({portfolio_metrics.get('total_return_pct', 0):.2f}%)\n"
        report += f"- Realized P&L: ${portfolio_metrics.get('realized_pnl', 0):,.2f}\n"
        report += f"- Unrealized P&L: ${portfolio_metrics.get('unrealized_pnl', 0):,.2f}\n"
        report += f"- Cash: ${portfolio_metrics.get('cash', 0):,.2f}\n"
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
