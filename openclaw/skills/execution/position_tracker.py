"""
Position tracker for portfolio management
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import numpy as np
from loguru import logger


class PositionTracker:
    """Tracks positions and portfolio performance"""
    
    def __init__(self, initial_capital: float = 100000.0):
        """
        Initialize position tracker
        
        Args:
            initial_capital: Starting capital
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.closed_positions: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
    
    def open_position(
        self,
        symbol: str,
        quantity: int,
        entry_price: float,
        order_id: str = ""
    ) -> Dict[str, Any]:
        """
        Open a new position or add to existing
        
        Args:
            symbol: Asset symbol
            quantity: Number of shares
            entry_price: Entry price
            order_id: Associated order ID
        
        Returns:
            Position details
        """
        cost = quantity * entry_price
        
        if cost > self.cash:
            logger.warning(f"Insufficient funds to open position: {symbol}")
            return {"success": False, "reason": "insufficient_funds"}
        
        if symbol in self.positions:
            # Add to existing position (average price)
            position = self.positions[symbol]
            total_quantity = position['quantity'] + quantity
            total_cost = (position['quantity'] * position['avg_entry_price']) + cost
            avg_price = total_cost / total_quantity
            
            position['quantity'] = total_quantity
            position['avg_entry_price'] = avg_price
            position['total_cost'] = total_cost
            position['updated_at'] = datetime.now().isoformat()
        else:
            # Create new position
            self.positions[symbol] = {
                "symbol": symbol,
                "quantity": quantity,
                "avg_entry_price": entry_price,
                "total_cost": cost,
                "opened_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "highest_price": entry_price,
                "order_id": order_id
            }
        
        self.cash -= cost
        
        self.trade_history.append({
            "symbol": symbol,
            "action": "OPEN",
            "quantity": quantity,
            "price": entry_price,
            "cost": cost,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Opened position: {quantity} {symbol} @ {entry_price}")
        return {"success": True, "position": self.positions[symbol]}
    
    def close_position(
        self,
        symbol: str,
        quantity: Optional[int] = None,
        exit_price: float = 0.0,
        order_id: str = ""
    ) -> Dict[str, Any]:
        """
        Close a position (fully or partially)
        
        Args:
            symbol: Asset symbol
            quantity: Number of shares to close (None = close all)
            exit_price: Exit price
            order_id: Associated order ID
        
        Returns:
            Closure details
        """
        if symbol not in self.positions:
            logger.warning(f"No position found for {symbol}")
            return {"success": False, "reason": "no_position"}
        
        position = self.positions[symbol]
        
        if quantity is None:
            quantity = position['quantity']
        
        if quantity > position['quantity']:
            logger.warning(f"Quantity exceeds position size for {symbol}")
            return {"success": False, "reason": "insufficient_quantity"}
        
        # Calculate P&L
        revenue = quantity * exit_price
        cost_basis = quantity * position['avg_entry_price']
        pnl = revenue - cost_basis
        pnl_pct = (pnl / cost_basis) * 100
        
        # Update cash
        self.cash += revenue
        
        # Create closed position record
        closed_position = {
            "symbol": symbol,
            "quantity": quantity,
            "entry_price": position['avg_entry_price'],
            "exit_price": exit_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "opened_at": position['opened_at'],
            "closed_at": datetime.now().isoformat(),
            "order_id": order_id
        }
        
        self.closed_positions.append(closed_position)
        
        self.trade_history.append({
            "symbol": symbol,
            "action": "CLOSE",
            "quantity": quantity,
            "price": exit_price,
            "revenue": revenue,
            "pnl": pnl,
            "timestamp": datetime.now().isoformat()
        })
        
        # Update or remove position
        if quantity == position['quantity']:
            del self.positions[symbol]
            logger.info(f"Closed full position: {quantity} {symbol} @ {exit_price}, P&L: {pnl:.2f} ({pnl_pct:.2f}%)")
        else:
            position['quantity'] -= quantity
            position['total_cost'] -= cost_basis
            position['updated_at'] = datetime.now().isoformat()
            logger.info(f"Partially closed position: {quantity} {symbol} @ {exit_price}, P&L: {pnl:.2f} ({pnl_pct:.2f}%)")
        
        return {"success": True, "closed_position": closed_position}
    
    def update_position_prices(self, prices: Dict[str, float]):
        """
        Update current prices for positions
        
        Args:
            prices: Dictionary mapping symbols to current prices
        """
        for symbol, position in self.positions.items():
            if symbol in prices:
                current_price = prices[symbol]
                
                # Update highest price for trailing stop
                if current_price > position.get('highest_price', 0):
                    position['highest_price'] = current_price
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position details"""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        return list(self.positions.values())
    
    def calculate_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """
        Calculate total portfolio value
        
        Args:
            current_prices: Current prices for all positions
        
        Returns:
            Total portfolio value
        """
        position_value = sum(
            pos['quantity'] * current_prices.get(pos['symbol'], pos['avg_entry_price'])
            for pos in self.positions.values()
        )
        
        return self.cash + position_value
    
    def calculate_unrealized_pnl(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """
        Calculate unrealized P&L
        
        Args:
            current_prices: Current prices for positions
        
        Returns:
            Unrealized P&L details
        """
        total_pnl = 0.0
        position_pnls = {}
        
        for symbol, position in self.positions.items():
            current_price = current_prices.get(symbol, position['avg_entry_price'])
            current_value = position['quantity'] * current_price
            cost_basis = position['total_cost']
            pnl = current_value - cost_basis
            pnl_pct = (pnl / cost_basis) * 100 if cost_basis > 0 else 0
            
            position_pnls[symbol] = {
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "current_value": current_value
            }
            
            total_pnl += pnl
        
        return {
            "total_unrealized_pnl": total_pnl,
            "positions": position_pnls
        }
    
    def calculate_realized_pnl(self) -> float:
        """Calculate total realized P&L"""
        return sum(pos['pnl'] for pos in self.closed_positions)
    
    def calculate_performance_metrics(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """
        Calculate portfolio performance metrics
        
        Args:
            current_prices: Current prices
        
        Returns:
            Performance metrics
        """
        portfolio_value = self.calculate_portfolio_value(current_prices)
        total_return = portfolio_value - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100
        
        realized_pnl = self.calculate_realized_pnl()
        unrealized = self.calculate_unrealized_pnl(current_prices)
        
        # Calculate win rate
        winning_trades = [p for p in self.closed_positions if p['pnl'] > 0]
        win_rate = len(winning_trades) / len(self.closed_positions) * 100 if self.closed_positions else 0
        
        # Calculate Sharpe ratio (simplified)
        if self.closed_positions:
            returns = [p['pnl_pct'] for p in self.closed_positions]
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = (avg_return / std_return) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Calculate max drawdown
        equity_curve = [self.initial_capital]
        running_capital = self.initial_capital
        
        for trade in self.trade_history:
            if trade['action'] == 'CLOSE':
                running_capital += trade['pnl']
                equity_curve.append(running_capital)
        
        peak = equity_curve[0]
        max_drawdown = 0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return {
            "portfolio_value": portfolio_value,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized['total_unrealized_pnl'],
            "cash": self.cash,
            "num_positions": len(self.positions),
            "num_closed_trades": len(self.closed_positions),
            "win_rate": win_rate,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown
        }
