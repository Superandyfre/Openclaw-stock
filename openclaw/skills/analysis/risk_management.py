"""
Risk management for trading
Supports both long-term and short-term trading with enhanced controls
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
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
        self.min_risk_reward_ratio = config.get('min_risk_reward_ratio', 2.0)
        
        # Stop loss configuration
        self.stop_loss_enabled = config.get('stop_loss', {}).get('enabled', True)
        self.stop_loss_type = config.get('stop_loss', {}).get('type', 'trailing')
        self.stop_loss_pct = config.get('stop_loss', {}).get('percentage', 0.05)
        self.initial_stop_loss_pct = config.get('stop_loss', {}).get('initial_percentage', 0.01)
        self.trailing_step = config.get('stop_loss', {}).get('trailing_step', 0.005)
        self.min_profit_for_trailing = config.get('stop_loss', {}).get('min_profit_for_trailing', 0.005)
        
        # Take profit configuration (tiered for short-term)
        self.take_profit_enabled = config.get('take_profit', {}).get('enabled', True)
        self.take_profit_type = config.get('take_profit', {}).get('type', 'fixed')
        self.take_profit_pct = config.get('take_profit', {}).get('percentage', 0.10)
        self.quick_profit_pct = config.get('take_profit', {}).get('quick_profit', 0.015)
        self.main_profit_pct = config.get('take_profit', {}).get('main_profit', 0.025)
        self.max_profit_pct = config.get('take_profit', {}).get('max_profit', 0.05)
        
        # Intraday limits
        intraday_limits = config.get('intraday_limits', {})
        self.max_trades_per_day = intraday_limits.get('max_trades_per_day', 5)
        self.max_consecutive_losses = intraday_limits.get('max_consecutive_losses', 3)
        self.force_close_before_market_close = intraday_limits.get('force_close_before_market_close', True)
        self.min_time_between_trades_minutes = intraday_limits.get('min_time_between_trades_minutes', 30)
        
        # Position time limits
        position_limits = config.get('position_time_limits', {})
        self.max_hold_time_hours = position_limits.get('max_hold_time_hours', 24)
        self.default_hold_time_hours = position_limits.get('default_hold_time_hours', 6)
        self.auto_close_on_time_limit = position_limits.get('auto_close_on_time_limit', True)
        
        # Portfolio heat management
        portfolio_heat = config.get('portfolio_heat', {})
        self.max_total_risk = portfolio_heat.get('max_total_risk', 0.06)
        self.max_concurrent_positions = portfolio_heat.get('max_concurrent_positions', 3)
        
        # State tracking
        self.daily_pnl = 0.0
        self.peak_portfolio_value = 0.0
        self.daily_trade_count = 0
        self.consecutive_losses = 0
        self.last_trade_time: Optional[datetime] = None
        self.trade_history: List[Dict[str, Any]] = []
    
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
    
    def calculate_tiered_take_profits(self, entry_price: float) -> Dict[str, float]:
        """
        Calculate tiered take profit levels for short-term trading
        
        Args:
            entry_price: Entry price
        
        Returns:
            Dictionary of take profit levels
        """
        return {
            "quick_profit": entry_price * (1 + self.quick_profit_pct),     # 1.5% - Take 33%
            "main_profit": entry_price * (1 + self.main_profit_pct),       # 2.5% - Take 33%
            "max_profit": entry_price * (1 + self.max_profit_pct)          # 5% - Take remaining
        }
    
    def calculate_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        highest_price: float
    ) -> float:
        """
        Calculate trailing stop loss for short-term trading
        
        Args:
            entry_price: Entry price
            current_price: Current price
            highest_price: Highest price since entry
        
        Returns:
            Trailing stop loss price
        """
        # Calculate profit percentage
        profit_pct = (highest_price - entry_price) / entry_price
        
        # Only start trailing if minimum profit is reached
        if profit_pct < self.min_profit_for_trailing:
            # Use initial stop loss
            return entry_price * (1 - self.initial_stop_loss_pct)
        
        # Calculate how many trailing steps we've achieved
        steps = int(profit_pct / self.trailing_step)
        
        # Move stop loss up by number of steps
        trailing_stop = entry_price * (1 - self.initial_stop_loss_pct + steps * self.trailing_step)
        
        return trailing_stop
    
    def check_intraday_limits(self) -> Dict[str, Any]:
        """
        Check if intraday trading limits are exceeded
        
        Returns:
            Dictionary with limit check results
        """
        violations = []
        can_trade = True
        
        # Check daily trade limit
        if self.daily_trade_count >= self.max_trades_per_day:
            violations.append({
                "type": "max_daily_trades",
                "current": self.daily_trade_count,
                "limit": self.max_trades_per_day
            })
            can_trade = False
        
        # Check consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            violations.append({
                "type": "max_consecutive_losses",
                "current": self.consecutive_losses,
                "limit": self.max_consecutive_losses
            })
            can_trade = False
        
        # Check minimum time between trades
        if self.last_trade_time:
            time_since_last_trade = (datetime.now() - self.last_trade_time).total_seconds() / 60
            if time_since_last_trade < self.min_time_between_trades_minutes:
                violations.append({
                    "type": "min_time_between_trades",
                    "time_elapsed_minutes": time_since_last_trade,
                    "required_minutes": self.min_time_between_trades_minutes
                })
                can_trade = False
        
        return {
            "can_trade": can_trade,
            "violations": violations,
            "daily_trade_count": self.daily_trade_count,
            "consecutive_losses": self.consecutive_losses
        }
    
    def check_position_time_limit(
        self,
        entry_time: datetime,
        max_hold_hours: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Check if position has exceeded time limit
        
        Args:
            entry_time: When position was entered
            max_hold_hours: Maximum hold time (uses default if None)
        
        Returns:
            Time limit check results
        """
        if max_hold_hours is None:
            max_hold_hours = self.max_hold_time_hours
        
        hours_held = (datetime.now() - entry_time).total_seconds() / 3600
        time_limit_exceeded = hours_held >= max_hold_hours
        
        should_close = self.auto_close_on_time_limit and time_limit_exceeded
        
        return {
            "hours_held": hours_held,
            "max_hold_hours": max_hold_hours,
            "time_limit_exceeded": time_limit_exceeded,
            "should_auto_close": should_close,
            "time_remaining_hours": max(0, max_hold_hours - hours_held)
        }
    
    def record_trade(self, trade_result: Dict[str, Any]):
        """
        Record a completed trade and update tracking
        
        Args:
            trade_result: Trade result dictionary with 'pnl' and 'success' keys
        """
        self.trade_history.append({
            **trade_result,
            "timestamp": datetime.now().isoformat()
        })
        
        self.daily_trade_count += 1
        self.last_trade_time = datetime.now()
        
        # Update consecutive losses
        if trade_result.get('pnl', 0) < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        # Update daily PnL
        self.update_daily_pnl(trade_result.get('pnl', 0))
        
        logger.info(f"Trade recorded: PnL=${trade_result.get('pnl', 0):.2f}, "
                   f"Daily trades: {self.daily_trade_count}, "
                   f"Consecutive losses: {self.consecutive_losses}")
    
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
        """Reset daily P&L and counters (call at market close)"""
        logger.info(f"Resetting daily counters - Trades: {self.daily_trade_count}, PnL: ${self.daily_pnl:.2f}")
        self.daily_pnl = 0.0
        self.daily_trade_count = 0
        self.consecutive_losses = 0
    
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
