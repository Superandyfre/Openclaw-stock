"""
Portfolio manager for stock and cryptocurrency positions
"""
from typing import Dict, Any
from openclaw.skills.execution.position_tracker import PositionTracker


class PortfolioManager:
    """
    Portfolio manager extending PositionTracker with crypto/stock segregation
    """
    
    def __init__(self, position_tracker: PositionTracker):
        """
        Initialize portfolio manager
        
        Args:
            position_tracker: Underlying position tracker
        """
        self.tracker = position_tracker
    
    def _is_crypto(self, symbol: str) -> bool:
        """
        Determine if symbol is a cryptocurrency
        
        Args:
            symbol: Asset symbol
        
        Returns:
            True if cryptocurrency, False if stock
        """
        symbol_upper = symbol.upper()
        
        # Upbit format: KRW-BTC, KRW-ETH
        if symbol_upper.startswith('KRW-'):
            return True
        
        # Korean stocks: ends with .KS or .KQ
        if symbol_upper.endswith('.KS') or symbol_upper.endswith('.KQ'):
            return False
        
        # Common crypto symbols (without exchange prefix)
        common_crypto = {'BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'DOGE', 'BNB', 'USDT', 'USDC'}
        if symbol_upper in common_crypto:
            return True
        
        # Default to stock for unknown symbols
        return False
    
    def get_crypto_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all cryptocurrency positions
        
        Returns:
            Dictionary of crypto positions {symbol: position_data}
        """
        all_positions = self.tracker.positions
        return {
            symbol: pos for symbol, pos in all_positions.items()
            if self._is_crypto(symbol)
        }
    
    def get_stock_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all stock positions
        
        Returns:
            Dictionary of stock positions {symbol: position_data}
        """
        all_positions = self.tracker.positions
        return {
            symbol: pos for symbol, pos in all_positions.items()
            if not self._is_crypto(symbol)
        }
    
    def get_portfolio_by_type(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """
        Calculate portfolio grouped by asset type
        
        Args:
            current_prices: Dictionary of current prices {symbol: price}
        
        Returns:
            Portfolio breakdown with structure:
            {
                'stocks': {
                    'positions': {...},
                    'total_value': float,
                    'total_cost': float,
                    'unrealized_pnl': float,
                    'unrealized_pnl_pct': float
                },
                'crypto': {
                    'positions': {...},
                    'total_value': float,
                    'total_cost': float,
                    'unrealized_pnl': float,
                    'unrealized_pnl_pct': float
                },
                'total': {
                    'portfolio_value': float,
                    'cash': float,
                    'total_invested': float,
                    'total_pnl': float,
                    'total_pnl_pct': float
                }
            }
        """
        stock_positions = self.get_stock_positions()
        crypto_positions = self.get_crypto_positions()
        
        def calculate_group_metrics(positions: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
            """Calculate metrics for a group of positions"""
            if not positions:
                return {
                    'positions': {},
                    'total_value': 0.0,
                    'total_cost': 0.0,
                    'unrealized_pnl': 0.0,
                    'unrealized_pnl_pct': 0.0,
                    'count': 0
                }
            
            total_value = 0.0
            total_cost = 0.0
            position_details = {}
            
            for symbol, pos in positions.items():
                current_price = current_prices.get(symbol, pos['avg_entry_price'])
                quantity = pos['quantity']
                cost = pos['total_cost']
                value = quantity * current_price
                pnl = value - cost
                pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0
                
                total_value += value
                total_cost += cost
                
                position_details[symbol] = {
                    'quantity': quantity,
                    'avg_entry_price': pos['avg_entry_price'],
                    'current_price': current_price,
                    'total_cost': cost,
                    'current_value': value,
                    'unrealized_pnl': pnl,
                    'unrealized_pnl_pct': pnl_pct,
                    'opened_at': pos.get('opened_at'),
                    'updated_at': pos.get('updated_at')
                }
            
            total_pnl = total_value - total_cost
            total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
            
            return {
                'positions': position_details,
                'total_value': total_value,
                'total_cost': total_cost,
                'unrealized_pnl': total_pnl,
                'unrealized_pnl_pct': total_pnl_pct,
                'count': len(positions)
            }
        
        # Calculate metrics for each group
        stocks_metrics = calculate_group_metrics(stock_positions)
        crypto_metrics = calculate_group_metrics(crypto_positions)
        
        # Calculate total portfolio metrics
        total_position_value = stocks_metrics['total_value'] + crypto_metrics['total_value']
        total_invested = stocks_metrics['total_cost'] + crypto_metrics['total_cost']
        portfolio_value = self.tracker.cash + total_position_value
        total_pnl = total_position_value - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
        
        return {
            'stocks': stocks_metrics,
            'crypto': crypto_metrics,
            'total': {
                'portfolio_value': portfolio_value,
                'cash': self.tracker.cash,
                'total_invested': total_invested,
                'position_value': total_position_value,
                'total_pnl': total_pnl,
                'total_pnl_pct': total_pnl_pct,
                'initial_capital': self.tracker.initial_capital
            }
        }
