"""
Short-Term Backtesting Module

Backtest short-term trading strategies using minute-level data
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
import numpy as np


class ShortTermBacktest:
    """
    Backtest engine for short-term trading strategies
    
    Features:
    - Minute-level data simulation
    - Realistic slippage and fees
    - Intraday position management
    - Performance metrics calculation
    """
    
    def __init__(
        self,
        initial_capital: float = 100000,
        slippage_pct: float = 0.001,  # 0.1% slippage
        commission_pct: float = 0.001  # 0.1% commission
    ):
        """
        Initialize backtest engine
        
        Args:
            initial_capital: Starting capital
            slippage_pct: Slippage percentage
            commission_pct: Commission percentage
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.slippage_pct = slippage_pct
        self.commission_pct = commission_pct
        
        # State tracking
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.closed_trades: List[Dict[str, Any]] = []
        self.equity_curve: List[float] = [initial_capital]
        self.daily_returns: List[float] = []
        
        logger.info(f"Backtest initialized with ${initial_capital:,.0f}")
    
    def run_backtest(
        self,
        minute_data: Dict[str, List[Dict[str, Any]]],
        strategy_signals: List[Dict[str, Any]],
        risk_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run backtest simulation
        
        Args:
            minute_data: Minute-level price data by symbol
            strategy_signals: List of trading signals generated
            risk_params: Risk management parameters
        
        Returns:
            Backtest results and metrics
        """
        logger.info(f"Running backtest with {len(strategy_signals)} signals")
        
        # Process each signal chronologically
        sorted_signals = sorted(strategy_signals, key=lambda x: x.get('timestamp', ''))
        
        for signal in sorted_signals:
            self._process_signal(signal, minute_data, risk_params)
        
        # Close any remaining positions at end of backtest
        self._close_all_positions(minute_data)
        
        # Calculate performance metrics
        metrics = self._calculate_metrics()
        
        logger.info(f"Backtest complete: Final capital ${self.capital:,.2f}")
        
        return metrics
    
    def _process_signal(
        self,
        signal: Dict[str, Any],
        minute_data: Dict[str, List[Dict[str, Any]]],
        risk_params: Dict[str, Any]
    ):
        """Process a trading signal"""
        symbol = signal.get('symbol')
        action = signal.get('action')
        
        if action == 'BUY' and symbol not in self.positions:
            self._open_position(signal, risk_params)
        
        elif action == 'SELL' and symbol in self.positions:
            self._close_position(symbol, signal.get('price', 0), 'SIGNAL')
        
        # Check existing positions for stop loss / take profit
        self._check_position_exits(minute_data, risk_params)
    
    def _open_position(
        self,
        signal: Dict[str, Any],
        risk_params: Dict[str, Any]
    ):
        """Open a new position"""
        symbol = signal.get('symbol')
        entry_price = signal.get('price', 0)
        
        # Apply slippage (assume worse execution for buys)
        actual_entry = entry_price * (1 + self.slippage_pct)
        
        # Calculate position size (simplified - use fixed percentage)
        position_value = self.capital * risk_params.get('max_position_size', 0.2)
        shares = int(position_value / actual_entry)
        
        if shares == 0:
            logger.warning(f"Cannot open position in {symbol}: insufficient capital")
            return
        
        # Calculate costs
        position_cost = shares * actual_entry
        commission = position_cost * self.commission_pct
        total_cost = position_cost + commission
        
        if total_cost > self.capital:
            logger.warning(f"Cannot open position in {symbol}: insufficient capital")
            return
        
        # Update capital
        self.capital -= total_cost
        
        # Record position
        self.positions[symbol] = {
            'symbol': symbol,
            'shares': shares,
            'entry_price': actual_entry,
            'entry_time': signal.get('timestamp', datetime.now().isoformat()),
            'stop_loss': signal.get('stop_loss', actual_entry * 0.98),
            'take_profit': signal.get('take_profit', actual_entry * 1.02),
            'max_hold_hours': signal.get('max_hold_hours', 24),
            'highest_price': actual_entry,
            'commission_paid': commission,
            'strategy': signal.get('strategy', 'Unknown')
        }
        
        logger.debug(f"Opened {symbol}: {shares} shares @ ${actual_entry:.2f}")
    
    def _close_position(
        self,
        symbol: str,
        exit_price: float,
        reason: str
    ):
        """Close an existing position"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        
        # Apply slippage (assume worse execution for sells)
        actual_exit = exit_price * (1 - self.slippage_pct)
        
        # Calculate proceeds
        shares = position['shares']
        proceeds = shares * actual_exit
        commission = proceeds * self.commission_pct
        net_proceeds = proceeds - commission
        
        # Update capital
        self.capital += net_proceeds
        
        # Calculate P&L
        entry_cost = shares * position['entry_price'] + position['commission_paid']
        pnl = net_proceeds - entry_cost
        pnl_pct = (pnl / entry_cost) * 100
        
        # Record trade
        trade_record = {
            **position,
            'exit_price': actual_exit,
            'exit_time': datetime.now().isoformat(),
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_reason': reason,
            'total_commission': position['commission_paid'] + commission
        }
        
        self.closed_trades.append(trade_record)
        
        # Limit memory usage for very long backtests
        if len(self.closed_trades) > 10000:
            logger.warning("Closed trades list exceeds 10000, keeping last 10000")
            self.closed_trades = self.closed_trades[-10000:]
        
        # Remove position
        del self.positions[symbol]
        
        # Update equity curve
        self.equity_curve.append(self.capital + self._calculate_open_position_value())
        
        logger.debug(f"Closed {symbol}: P&L ${pnl:.2f} ({pnl_pct:.2f}%) - {reason}")
    
    def _check_position_exits(
        self,
        minute_data: Dict[str, List[Dict[str, Any]]],
        risk_params: Dict[str, Any]
    ):
        """Check all positions for stop loss, take profit, or time limit exits"""
        for symbol in list(self.positions.keys()):
            position = self.positions[symbol]
            
            # Get current price (simplified - use last available)
            current_price = self._get_current_price(symbol, minute_data)
            
            if current_price == 0:
                continue
            
            # Update highest price for trailing stop
            if current_price > position['highest_price']:
                position['highest_price'] = current_price
            
            # Check stop loss
            if current_price <= position['stop_loss']:
                self._close_position(symbol, current_price, 'STOP_LOSS')
                continue
            
            # Check take profit
            if current_price >= position['take_profit']:
                self._close_position(symbol, current_price, 'TAKE_PROFIT')
                continue
            
            # Check time limit
            entry_time = datetime.fromisoformat(position['entry_time'])
            hours_held = (datetime.now() - entry_time).total_seconds() / 3600
            
            if hours_held >= position['max_hold_hours']:
                self._close_position(symbol, current_price, 'TIME_LIMIT')
                continue
    
    def _close_all_positions(self, minute_data: Dict[str, List[Dict[str, Any]]]):
        """Close all remaining positions at end of backtest"""
        for symbol in list(self.positions.keys()):
            current_price = self._get_current_price(symbol, minute_data)
            if current_price > 0:
                self._close_position(symbol, current_price, 'END_OF_BACKTEST')
    
    def _get_current_price(
        self,
        symbol: str,
        minute_data: Dict[str, List[Dict[str, Any]]]
    ) -> float:
        """Get current price for a symbol"""
        if symbol not in minute_data or not minute_data[symbol]:
            return 0.0
        
        return minute_data[symbol][-1].get('close', 0.0)
    
    def _calculate_open_position_value(self) -> float:
        """Calculate total value of open positions"""
        # Simplified - would need current prices
        return sum(
            pos['shares'] * pos['entry_price']
            for pos in self.positions.values()
        )
    
    def _calculate_metrics(self) -> Dict[str, Any]:
        """Calculate backtest performance metrics"""
        if not self.closed_trades:
            return {
                "error": "No trades executed",
                "final_capital": self.capital,
                "total_return": 0.0
            }
        
        # Basic metrics
        winning_trades = [t for t in self.closed_trades if t['pnl'] > 0]
        losing_trades = [t for t in self.closed_trades if t['pnl'] <= 0]
        
        total_trades = len(self.closed_trades)
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl = sum(t['pnl'] for t in self.closed_trades)
        total_return = (self.capital - self.initial_capital) / self.initial_capital * 100
        
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0
        
        # Risk metrics
        returns = [t['pnl_pct'] for t in self.closed_trades]
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        max_drawdown = self._calculate_max_drawdown()
        
        # Trade statistics
        avg_hold_time = self._calculate_avg_hold_time()
        
        return {
            "final_capital": self.capital,
            "initial_capital": self.initial_capital,
            "total_return": total_return,
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else 0,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "avg_hold_time_hours": avg_hold_time,
            "largest_win": max([t['pnl'] for t in self.closed_trades]),
            "largest_loss": min([t['pnl'] for t in self.closed_trades]),
            "total_commission": sum(t.get('total_commission', 0) for t in self.closed_trades)
        }
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio"""
        if not returns or len(returns) < 2:
            return 0.0
        
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualized (assuming ~252 trading days, multiple trades per day)
        sharpe = (avg_return / std_return) * np.sqrt(252)
        
        return float(sharpe)
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        if len(self.equity_curve) < 2:
            return 0.0
        
        peak = self.equity_curve[0]
        max_dd = 0.0
        
        for value in self.equity_curve:
            if value > peak:
                peak = value
            
            dd = (peak - value) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def _calculate_avg_hold_time(self) -> float:
        """Calculate average holding time in hours"""
        if not self.closed_trades:
            return 0.0
        
        hold_times = []
        for trade in self.closed_trades:
            try:
                entry = datetime.fromisoformat(trade['entry_time'])
                exit_time = datetime.fromisoformat(trade['exit_time'])
                hours = (exit_time - entry).total_seconds() / 3600
                hold_times.append(hours)
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping trade with invalid timestamp: {e}")
                continue
        
        if not hold_times:
            return 0.0
        
        return float(np.mean(hold_times))
    
    def get_trade_history(self) -> List[Dict[str, Any]]:
        """Get complete trade history"""
        return self.closed_trades
    
    def get_equity_curve(self) -> List[float]:
        """Get equity curve"""
        return self.equity_curve
