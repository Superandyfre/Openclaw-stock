"""
Position tracker for portfolio management
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import numpy as np
from loguru import logger


class PositionTracker:
    """Tracks positions and portfolio performance"""
    
    def __init__(self, initial_capital: float = 100000.0, alert_callback=None):
        """
        Initialize position tracker
        
        Args:
            initial_capital: Starting capital
            alert_callback: Callback function for sending alerts（接收symbol, alert_type, message）
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.closed_positions: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.alert_callback = alert_callback
        
        # 严格风控参数（强制执行）
        self.STOP_LOSS_PCT = -10.0  # 止损红线：-10%
        self.STOP_LOSS_WARNING_PCT = -8.0  # 止损警告：-8%
        self.PROFIT_TARGET_PCT = 20.0  # 收益目标：+20%
        self.MAJOR_GAIN_PCT = 15.0  # 重大利好：+15%
    
    def open_position(
        self,
        symbol: str,
        quantity: int,
        entry_price: float,
        order_id: str = "",
        custom_profit_target_price: Optional[float] = None  # 新增：支持自定义目标价
    ) -> Dict[str, Any]:
        """
        Open a new position or add to existing
        
        Args:
            symbol: Asset symbol
            quantity: Number of shares
            entry_price: Entry price
            order_id: Associated order ID
            custom_profit_target_price: Optional custom target price
        
        Returns:
            Position details
        """
        cost = quantity * entry_price
        
        if cost > self.cash:
            logger.warning(f"Insufficient funds to open position: {symbol}")
            return {
                "success": False,
                "reason": "insufficient_funds",
                "required": cost,
                "available": self.cash,
            }
        
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
            
            # 重新计算止损位
            position['stop_loss_price'] = avg_price * (1 + self.STOP_LOSS_PCT / 100)
            
            # 目标价处理：若有自定义则更新，否则按均价重算默认目标
            if custom_profit_target_price is not None and custom_profit_target_price > 0:
                position['profit_target_price'] = custom_profit_target_price
            else:
                # 保持原有比例逻辑（或者加权平均？简化起见按新均价+20%重置，除非原来有特殊设定）
                # 这里我们选择：若无新指定，则按新均价 + 20% 重置，符合加仓逻辑
                position['profit_target_price'] = avg_price * (1 + self.PROFIT_TARGET_PCT / 100)
            
            logger.warning(f"⚠️ 更新仓位: {symbol} 止损价={position['stop_loss_price']:,.0f}, 目标价={position['profit_target_price']:,.0f}")
        else:
            # Create new position with MANDATORY stop loss
            stop_loss_price = entry_price * (1 + self.STOP_LOSS_PCT / 100)
            
            if custom_profit_target_price is not None and custom_profit_target_price > 0:
                profit_target_price = custom_profit_target_price
                pct = ((profit_target_price - entry_price) / entry_price * 100)
                desc = f"自定义目标 (+{pct:.1f}%)"
            else:
                profit_target_price = entry_price * (1 + self.PROFIT_TARGET_PCT / 100)
                desc = "+20% 默认目标"
            
            self.positions[symbol] = {
                "symbol": symbol,
                "quantity": quantity,
                "avg_entry_price": entry_price,
                "total_cost": cost,
                "opened_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "highest_price": entry_price,
                "order_id": order_id,
                # 强制风控参数
                "stop_loss_price": stop_loss_price,  # 止损价（-10%）
                "profit_target_price": profit_target_price,  # 目标价
                "stop_loss_triggered": False,  # 是否已触发止损
                "alert_sent": []  # 已发送的告警类型
            }
            
            logger.warning(f"⚠️ 开仓风控: {symbol} 止损={stop_loss_price:,.0f} (−10%), 目标={profit_target_price:,.0f} ({desc})")
        
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
            
            # 更新最高价格
            if 'highest_price' not in position or current_price > position['highest_price']:
                position['highest_price'] = current_price
            
            position_pnls[symbol] = {
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "current_value": current_value,
                "highest_price": position.get('highest_price', current_price)
            }
            
            total_pnl += pnl
        
        return {
            "total_unrealized_pnl": total_pnl,
            "positions": position_pnls
        }
    
    def check_stop_loss_and_alert(self, symbol: str, current_price: float) -> Optional[Dict[str, Any]]:
        """
        检查单个持仓的止损情况并立即发送告警（强制执行）
        
        Args:
            symbol: 股票代码
            current_price: 当前价格
            
        Returns:
            告警信息（如果有）
        """
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        # 使用精确的entry_price（从total_cost计算，避免四舍五入误差）
        entry_price = position['total_cost'] / position['quantity'] if position['quantity'] > 0 else position['avg_entry_price']
        stop_loss_price = position['stop_loss_price']
        profit_target_price = position['profit_target_price']
        
        # 计算盈亏百分比
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        
        alert = None
        alert_type = None
        
        # 🔴 强制止损：触发-10%红线
        if current_price <= stop_loss_price:
            alert_type = "STOP_LOSS_TRIGGER"
            if alert_type not in position['alert_sent']:
                alert = {
                    "symbol": symbol,
                    "type": alert_type,
                    "severity": "CRITICAL",
                    "message": f"!! 强制止损触发 !! {symbol}\n当前价格: {current_price:,.2f}\n止损价: {stop_loss_price:,.2f}\n亏损: {pnl_pct:.2f}%\n立即平仓！",
                    "pnl_pct": pnl_pct,
                    "current_price": current_price,
                    "stop_loss_price": stop_loss_price,
                    "action_required": "SELL_NOW"
                }
                position['stop_loss_triggered'] = True
                position['alert_sent'].append(alert_type)
                logger.critical(f"🔴 STOP LOSS TRIGGERED: {symbol} @ {current_price:,.2f} ({pnl_pct:.2f}%)")
        
        # ⚠️ 止损警告：接近-10%（-8%以上）
        elif pnl_pct <= self.STOP_LOSS_WARNING_PCT:
            alert_type = "STOP_LOSS_WARNING"
            if alert_type not in position['alert_sent']:
                distance_to_stop = abs(current_price - stop_loss_price)
                alert = {
                    "symbol": symbol,
                    "type": alert_type,
                    "severity": "HIGH",
                    "message": f"! 风险告警 ! {symbol}\n当前价格: {current_price:,.2f}\n亏损: {pnl_pct:.2f}%\n距离止损线: {distance_to_stop:,.2f}韩元\n请密切关注！",
                    "pnl_pct": pnl_pct,
                    "current_price": current_price,
                    "stop_loss_price": stop_loss_price,
                    "action_required": "MONITOR_CLOSELY"
                }
                position['alert_sent'].append(alert_type)
                logger.warning(f"⚠️ STOP LOSS WARNING: {symbol} @ {current_price:,.2f} ({pnl_pct:.2f}%)")
        
        # ✅ 收益达标：+20%以上
        elif current_price >= profit_target_price:
            alert_type = "PROFIT_TARGET_REACHED"
            if alert_type not in position['alert_sent']:
                alert = {
                    "symbol": symbol,
                    "type": alert_type,
                    "severity": "SUCCESS",
                    "message": f"+ 收益达标 + {symbol}\n当前价格: {current_price:,.2f}\n盈利: {pnl_pct:.2f}%\n已达目标！考虑获利了结！",
                    "pnl_pct": pnl_pct,
                    "current_price": current_price,
                    "profit_target_price": profit_target_price,
                    "action_required": "CONSIDER_SELL"
                }
                position['alert_sent'].append(alert_type)
                logger.info(f"✅ PROFIT TARGET: {symbol} @ {current_price:,.2f} ({pnl_pct:.2f}%) [target_price={profit_target_price:,.2f}]")
        
        # 📈 重大利好：+15%以上
        elif pnl_pct >= self.MAJOR_GAIN_PCT:
            alert_type = "MAJOR_GAIN"
            if alert_type not in position['alert_sent']:
                alert = {
                    "symbol": symbol,
                    "type": alert_type,
                    "severity": "GOOD_NEWS",
                    "message": f"++ 重大利好 ++ {symbol}\n当前价格: {current_price:,.2f}\n盈利: {pnl_pct:.2f}%\n距离20%目标: {self.PROFIT_TARGET_PCT - pnl_pct:.1f}%",
                    "pnl_pct": pnl_pct,
                    "current_price": current_price,
                    "action_required": "HOLD"
                }
                position['alert_sent'].append(alert_type)
                logger.info(f"📈 MAJOR GAIN: {symbol} @ {current_price:,.2f} ({pnl_pct:.2f}%)")
        
        # 如果有告警且设置了回调函数，立即发送
        if alert and self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception as e:
                logger.error(f"告警回调失败: {e}")
        
        return alert
    
    def check_position_alerts(self, current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        批量检查所有持仓的风险告警（强制执行止损红线）
        
        Args:
            current_prices: 当前价格字典
        
        Returns:
            告警列表
        """
        alerts = []
        
        for symbol in list(self.positions.keys()):
            current_price = current_prices.get(symbol)
            if current_price:
                alert = self.check_stop_loss_and_alert(symbol, current_price)
                if alert:
                    alerts.append(alert)
        
        return alerts
    
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
        total_return_pct = (total_return / self.initial_capital * 100) if self.initial_capital else 0.0
        
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

    # ──────────────────────────────────────────────────────────
    # 状态持久化：保存 / 加载
    # ──────────────────────────────────────────────────────────

    def save_state(self, filepath: str) -> bool:
        """将账户状态序列化为 JSON 文件，重启后可恢复。"""
        import json, os
        try:
            state = {
                'initial_capital': self.initial_capital,
                'cash': self.cash,
                'positions': self.positions,
                'closed_positions': self.closed_positions,
                'trade_history': self.trade_history[-200:],  # 最多保留最近200条
                'saved_at': datetime.now().isoformat(),
            }
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            tmp = filepath + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp, filepath)  # 原子替换，避免写一半崩溃
            logger.info(f'💾 账户状态已保存: {filepath}')
            return True
        except Exception as e:
            logger.error(f'账户状态保存失败: {e}')
            return False

    def load_state(self, filepath: str) -> bool:
        """从 JSON 文件恢复账户状态。返回 True 表示成功加载。"""
        import json, os
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                state = json.load(f)
            self.initial_capital = float(state.get('initial_capital', self.initial_capital))
            self.cash = float(state.get('cash', self.initial_capital))
            self.positions = state.get('positions', {})
            self.closed_positions = state.get('closed_positions', [])
            self.trade_history = state.get('trade_history', [])
            saved_at = state.get('saved_at', '?')
            logger.info(f'📂 账户状态已恢复（保存于 {saved_at}）: '
                        f'现金₩{self.cash:,.0f}, 持仓{len(self.positions)}个')
            return True
        except Exception as e:
            logger.error(f'账户状态加载失败: {e}')
            return False
