"""
Risk management for trading
"""
from typing import Dict, Any, List
from datetime import datetime
from loguru import logger


class RiskManagement:
    """Manages trading risk and position sizing"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize risk manager
        
        Args:
            config: Risk configuration
        """
        self.max_position_size = config.get('max_position_size', 0.1)
        self.max_loss_per_trade = config.get('max_loss_per_trade', 0.02)
        self.max_daily_loss = config.get('max_daily_loss', 0.05)
        self.max_drawdown = config.get('max_drawdown', 0.15)
        
        self.stop_loss_enabled = config.get('stop_loss', {}).get('enabled', True)
        self.stop_loss_type = config.get('stop_loss', {}).get('type', 'trailing')
        self.stop_loss_pct = config.get('stop_loss', {}).get('percentage', 0.05)
        
        self.take_profit_enabled = config.get('take_profit', {}).get('enabled', True)
        self.take_profit_pct = config.get('take_profit', {}).get('percentage', 0.10)
        
        self.daily_pnl = 0.0
        self.peak_portfolio_value = 0.0
    
    def calculate_position_size(
        self,
        portfolio_value: float,
        entry_price: float,
        risk_per_trade: float = None
    ) -> int:
        """
        Calculate optimal position size
        
        Args:
            portfolio_value: Total portfolio value
            entry_price: Entry price per share
            risk_per_trade: Risk per trade (override default)
        
        Returns:
            Number of shares to trade
        """
        if risk_per_trade is None:
            risk_per_trade = self.max_loss_per_trade
        
        # Maximum position value
        max_position_value = portfolio_value * self.max_position_size
        
        # Risk-based position sizing
        risk_amount = portfolio_value * risk_per_trade
        stop_loss_distance = entry_price * self.stop_loss_pct
        
        if stop_loss_distance > 0:
            shares_by_risk = int(risk_amount / stop_loss_distance)
        else:
            shares_by_risk = 0
        
        # Shares based on max position size
        shares_by_position = int(max_position_value / entry_price)
        
        # Use the smaller of the two
        position_size = min(shares_by_risk, shares_by_position)
        
        logger.info(f"Calculated position size: {position_size} shares")
        return max(0, position_size)
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        current_price: float = None,
        highest_price: float = None
    ) -> float:
        """
        Calculate stop loss price
        
        Args:
            entry_price: Entry price
            current_price: Current price (for trailing stop)
            highest_price: Highest price since entry (for trailing stop)
        
        Returns:
            Stop loss price
        """
        if self.stop_loss_type == 'trailing' and highest_price:
            stop_loss = highest_price * (1 - self.stop_loss_pct)
        else:
            stop_loss = entry_price * (1 - self.stop_loss_pct)
        
        return stop_loss
    
    def calculate_take_profit(self, entry_price: float) -> float:
        """
        Calculate take profit price
        
        Args:
            entry_price: Entry price
        
        Returns:
            Take profit price
        """
        return entry_price * (1 + self.take_profit_pct)
    
    def check_risk_limits(
        self,
        portfolio_value: float,
        current_drawdown: float
    ) -> Dict[str, Any]:
        """
        Check if risk limits are exceeded
        
        Args:
            portfolio_value: Current portfolio value
            current_drawdown: Current drawdown percentage
        
        Returns:
            Risk check results
        """
        violations = []
        
        # Update peak value
        if portfolio_value > self.peak_portfolio_value:
            self.peak_portfolio_value = portfolio_value
        
        # Check daily loss limit
        daily_loss_pct = abs(self.daily_pnl / portfolio_value) if portfolio_value > 0 else 0
        if daily_loss_pct > self.max_daily_loss:
            violations.append({
                "type": "daily_loss_exceeded",
                "current": daily_loss_pct,
                "limit": self.max_daily_loss
            })
        
        # Check drawdown limit
        if current_drawdown > self.max_drawdown:
            violations.append({
                "type": "max_drawdown_exceeded",
                "current": current_drawdown,
                "limit": self.max_drawdown
            })
        
        return {
            "within_limits": len(violations) == 0,
            "violations": violations,
            "daily_pnl": self.daily_pnl,
            "daily_loss_pct": daily_loss_pct,
            "current_drawdown": current_drawdown
        }
    
    def update_daily_pnl(self, pnl: float):
        """Update daily P&L"""
        self.daily_pnl += pnl
    
    def reset_daily_pnl(self):
        """Reset daily P&L (call at market close)"""
        self.daily_pnl = 0.0
    
    def calculate_risk_reward_ratio(
        self,
        entry_price: float,
        target_price: float,
        stop_loss_price: float
    ) -> float:
        """
        Calculate risk-reward ratio
        
        Args:
            entry_price: Entry price
            target_price: Target price
            stop_loss_price: Stop loss price
        
        Returns:
            Risk-reward ratio
        """
        potential_profit = target_price - entry_price
        potential_loss = entry_price - stop_loss_price
        
        if potential_loss == 0:
            return 0.0
        
        return potential_profit / potential_loss
    
    def should_take_trade(
        self,
        entry_price: float,
        target_price: float,
        stop_loss_price: float,
        min_risk_reward: float = 2.0
    ) -> Dict[str, Any]:
        """
        Determine if trade meets risk criteria
        
        Args:
            entry_price: Entry price
            target_price: Target price
            stop_loss_price: Stop loss price
            min_risk_reward: Minimum acceptable risk-reward ratio
        
        Returns:
            Trade decision
        """
        rr_ratio = self.calculate_risk_reward_ratio(
            entry_price,
            target_price,
            stop_loss_price
        )
        
        should_trade = rr_ratio >= min_risk_reward
        
        return {
            "should_trade": should_trade,
            "risk_reward_ratio": rr_ratio,
            "required_ratio": min_risk_reward,
            "reason": f"R:R ratio {rr_ratio:.2f}" if should_trade else f"R:R ratio {rr_ratio:.2f} below minimum {min_risk_reward}"
        }
