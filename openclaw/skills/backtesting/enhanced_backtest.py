"""
增强型回测引擎

特点：
- 集成强制止损红线（-10%）和收益目标（+20%）
- 支持10小时短线交易策略
- 实时风险告警模拟
- 详细的交易记录
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
import numpy as np


class EnhancedBacktest:
    """
    增强型回测引擎，集成强制风控规则
    
    特点：
    - 强制-10%止损红线（STOP_LOSS_PCT）
    - +20%收益目标（PROFIT_TARGET_PCT）
    - -8%警告（STOP_LOSS_WARNING_PCT）
    - +15%利好通知（MAJOR_GAIN_PCT）
    - 10小时最大持仓时间（短线策略）
    - 实时风险告警模拟
    """
    
    # 强制风控参数（与PositionTracker保持一致）
    STOP_LOSS_PCT = -10.0  # 强制止损红线
    STOP_LOSS_WARNING_PCT = -8.0  # 止损警告阈值
    PROFIT_TARGET_PCT = 20.0  # 收益目标
    MAJOR_GAIN_PCT = 15.0  # 重大利好阈值
    MAX_HOLD_HOURS = 10  # 最大持仓时间（小时）
    
    def __init__(
        self,
        initial_capital: float = 10000000,  # 1000万韩元
        slippage_pct: float = 0.002,  # 0.2% 滑点（韩股实际情况）
        commission_pct: float = 0.0015  # 0.15% 手续费
    ):
        """
        初始化回测引擎
        
        Args:
            initial_capital: 初始资金
            slippage_pct: 滑点百分比
            commission_pct: 手续费百分比
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.slippage_pct = slippage_pct
        self.commission_pct = commission_pct
        
        # 状态追踪
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.closed_trades: List[Dict[str, Any]] = []
        self.equity_curve: List[tuple] = [(datetime.now(), initial_capital)]
        self.alerts_triggered: List[Dict[str, Any]] = []  # 告警记录
        
        logger.info(f"✅ 回测引擎初始化: 初始资金 ₩{initial_capital:,.0f}")
        logger.info(f"   止损红线: {self.STOP_LOSS_PCT}% | 收益目标: {self.PROFIT_TARGET_PCT}%")
        logger.info(f"   最大持仓: {self.MAX_HOLD_HOURS}小时 | 滑点: {slippage_pct*100}%")
    
    def run_backtest(
        self,
        historical_data: Dict[str, List[Dict[str, Any]]],
        signals: List[Dict[str, Any]],
        max_position_size: float = 0.2  # 单笔最大仓位20%
    ) -> Dict[str, Any]:
        """
        运行回测
        
        Args:
            historical_data: 历史数据 {symbol: [{timestamp, open, high, low, close, volume}, ...]}
            signals: 交易信号列表 [{timestamp, symbol, action, price, strategy}, ...]
            max_position_size: 单笔最大仓位比例
        
        Returns:
            回测结果和性能指标
        """
        logger.info(f"🚀 开始回测: {len(signals)}个信号, {len(historical_data)}个标的")
        
        # 按时间排序信号
        sorted_signals = sorted(signals, key=lambda x: x.get('timestamp', ''))
        
        # 处理每个信号
        for signal in sorted_signals:
            self._process_signal(signal, historical_data, max_position_size)
        
        # 平仓所有剩余持仓
        self._close_all_positions(historical_data, 'END_OF_BACKTEST')
        
        # 计算性能指标
        metrics = self._calculate_metrics()
        
        logger.info(f"✅ 回测完成: 最终资金 ₩{self.capital:,.0f}")
        logger.info(f"   总收益: {metrics['total_return']:.2f}% | 胜率: {metrics['win_rate']:.2f}%")
        
        return metrics
    
    def _process_signal(
        self,
        signal: Dict[str, Any],
        historical_data: Dict[str, List[Dict[str, Any]]],
        max_position_size: float
    ):
        """处理交易信号"""
        symbol = signal.get('symbol')
        action = signal.get('action', '').upper()
        timestamp = signal.get('timestamp')
        
        # 买入信号
        if action == 'BUY' and symbol not in self.positions:
            self._open_position(signal, max_position_size)
        
        # 卖出信号
        elif action == 'SELL' and symbol in self.positions:
            current_price = signal.get('price', 0)
            self._close_position(symbol, current_price, timestamp, 'SIGNAL')
        
        # 检查现有持仓的风险状态（每个信号时间点检查一次）
        self._check_position_risk(historical_data, timestamp)
    
    def _open_position(
        self,
        signal: Dict[str, Any],
        max_position_size: float
    ):
        """开仓"""
        symbol = signal.get('symbol')
        entry_price = signal.get('price', 0)
        timestamp = signal.get('timestamp', datetime.now().isoformat())
        
        if entry_price <= 0:
            logger.warning(f"⚠️ 无效价格: {symbol} @ {entry_price}")
            return
        
        # 应用滑点（买入时价格上涨）
        actual_entry = entry_price * (1 + self.slippage_pct)
        
        # 计算仓位大小
        position_value = self.capital * max_position_size
        shares = int(position_value / actual_entry)
        
        if shares == 0:
            logger.warning(f"⚠️ 资金不足: {symbol} (需要 ₩{actual_entry:,.0f})")
            return
        
        # 计算成本
        position_cost = shares * actual_entry
        commission = position_cost * self.commission_pct
        total_cost = position_cost + commission
        
        if total_cost > self.capital:
            # 调整股数以适应可用资金
            available = self.capital * 0.95  # 留5%缓冲
            shares = int(available / (actual_entry * (1 + self.commission_pct)))
            if shares == 0:
                logger.warning(f"⚠️ 资金不足: {symbol}")
                return
            position_cost = shares * actual_entry
            commission = position_cost * self.commission_pct
            total_cost = position_cost + commission
        
        # 更新资金
        self.capital -= total_cost
        
        # 计算强制止损价和目标价
        stop_loss_price = actual_entry * (1 + self.STOP_LOSS_PCT / 100)  # -10%
        profit_target_price = actual_entry * (1 + self.PROFIT_TARGET_PCT / 100)  # +20%
        
        # 记录持仓
        self.positions[symbol] = {
            'symbol': symbol,
            'shares': shares,
            'entry_price': actual_entry,
            'entry_time': timestamp,
            'stop_loss_price': stop_loss_price,
            'profit_target_price': profit_target_price,
            'highest_price': actual_entry,
            'commission_paid': commission,
            'strategy': signal.get('strategy', 'Unknown'),
            'stop_loss_triggered': False,
            'alert_sent': []
        }
        
        logger.debug(f"📈 开仓: {symbol} x{shares} @ ₩{actual_entry:,.0f} "
                    f"(止损: ₩{stop_loss_price:,.0f}, 目标: ₩{profit_target_price:,.0f})")
    
    def _close_position(
        self,
        symbol: str,
        exit_price: float,
        timestamp: str,
        reason: str
    ):
        """平仓"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        
        # 应用滑点（卖出时价格下跌）
        actual_exit = exit_price * (1 - self.slippage_pct)
        
        # 计算收益
        shares = position['shares']
        proceeds = shares * actual_exit
        commission = proceeds * self.commission_pct
        net_proceeds = proceeds - commission
        
        # 更新资金
        self.capital += net_proceeds
        
        # 计算盈亏
        entry_cost = shares * position['entry_price']
        total_commission = position['commission_paid'] + commission
        pnl = net_proceeds - entry_cost - position['commission_paid']
        pnl_pct = (pnl / entry_cost) * 100
        
        # 计算持仓时间
        try:
            entry_time = datetime.fromisoformat(position['entry_time'])
            exit_time = datetime.fromisoformat(timestamp) if timestamp else datetime.now()
            hold_hours = (exit_time - entry_time).total_seconds() / 3600
        except:
            hold_hours = 0
        
        # 记录交易
        trade_record = {
            **position,
            'exit_price': actual_exit,
            'exit_time': timestamp,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_reason': reason,
            'total_commission': total_commission,
            'hold_hours': hold_hours
        }
        
        self.closed_trades.append(trade_record)
        
        # 移除持仓
        del self.positions[symbol]
        
        # 更新权益曲线
        current_equity = self.capital + self._calculate_open_position_value()
        self.equity_curve.append((exit_time if timestamp else datetime.now(), current_equity))
        
        # 日志
        reason_emoji = {
            'STOP_LOSS': '🔴',
            'TAKE_PROFIT': '✅',
            'TIME_LIMIT': '⏰',
            'SIGNAL': '📊',
            'END_OF_BACKTEST': '🏁'
        }.get(reason, '❓')
        
        logger.debug(f"{reason_emoji} 平仓: {symbol} @ ₩{actual_exit:,.0f} | "
                    f"盈亏: {pnl_pct:+.2f}% (₩{pnl:+,.0f}) | {reason}")
    
    def _check_position_risk(
        self,
        historical_data: Dict[str, List[Dict[str, Any]]],
        current_timestamp: str
    ):
        """检查所有持仓的风险状态"""
        for symbol in list(self.positions.keys()):
            position = self.positions[symbol]
            
            # 获取当前价格
            current_price = self._get_price_at_timestamp(
                symbol, historical_data, current_timestamp
            )
            
            if current_price <= 0:
                continue
            
            # 更新最高价
            if current_price > position['highest_price']:
                position['highest_price'] = current_price
            
            # 计算盈亏百分比
            entry_price = position['entry_price']
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            
            # 🔴 强制止损：触发-10%红线
            if current_price <= position['stop_loss_price']:
                if not position['stop_loss_triggered']:
                    position['stop_loss_triggered'] = True
                    self._trigger_alert(symbol, 'STOP_LOSS_TRIGGER', pnl_pct, current_timestamp)
                    logger.warning(f"🔴 强制止损触发: {symbol} @ ₩{current_price:,.0f} ({pnl_pct:.2f}%)")
                
                # 立即平仓
                self._close_position(symbol, current_price, current_timestamp, 'STOP_LOSS')
                continue
            
            # ⚠️ 止损警告：接近-8%
            if pnl_pct <= self.STOP_LOSS_WARNING_PCT:
                if 'STOP_LOSS_WARNING' not in position['alert_sent']:
                    position['alert_sent'].append('STOP_LOSS_WARNING')
                    self._trigger_alert(symbol, 'STOP_LOSS_WARNING', pnl_pct, current_timestamp)
                    logger.warning(f"⚠️ 止损警告: {symbol} @ ₩{current_price:,.0f} ({pnl_pct:.2f}%)")
            
            # ✅ 收益目标：达到+20%
            if current_price >= position['profit_target_price']:
                if 'PROFIT_TARGET_REACHED' not in position['alert_sent']:
                    position['alert_sent'].append('PROFIT_TARGET_REACHED')
                    self._trigger_alert(symbol, 'PROFIT_TARGET_REACHED', pnl_pct, current_timestamp)
                    logger.info(f"✅ 收益达标: {symbol} @ ₩{current_price:,.0f} ({pnl_pct:.2f}%)")
                
                # 可选：自动止盈（取决于策略，这里不强制平仓）
                # self._close_position(symbol, current_price, current_timestamp, 'TAKE_PROFIT')
            
            # 📈 重大利好：+15%
            elif pnl_pct >= self.MAJOR_GAIN_PCT:
                if 'MAJOR_GAIN' not in position['alert_sent']:
                    position['alert_sent'].append('MAJOR_GAIN')
                    self._trigger_alert(symbol, 'MAJOR_GAIN', pnl_pct, current_timestamp)
                    logger.info(f"📈 重大利好: {symbol} @ ₩{current_price:,.0f} ({pnl_pct:.2f}%)")
            
            # ⏰ 时间检查：超过最大持仓时间
            try:
                entry_time = datetime.fromisoformat(position['entry_time'])
                current_time = datetime.fromisoformat(current_timestamp)
                hold_hours = (current_time - entry_time).total_seconds() / 3600
                
                if hold_hours >= self.MAX_HOLD_HOURS:
                    logger.info(f"⏰ 超时平仓: {symbol} (持仓 {hold_hours:.1f}h)")
                    self._close_position(symbol, current_price, current_timestamp, 'TIME_LIMIT')
            except:
                pass
    
    def _trigger_alert(self, symbol: str, alert_type: str, pnl_pct: float, timestamp: str):
        """触发告警（记录）"""
        alert = {
            'timestamp': timestamp,
            'symbol': symbol,
            'type': alert_type,
            'pnl_pct': pnl_pct
        }
        self.alerts_triggered.append(alert)
    
    def _close_all_positions(self, historical_data: Dict[str, List[Dict[str, Any]]], reason: str):
        """平仓所有剩余持仓"""
        for symbol in list(self.positions.keys()):
            # 获取最后价格
            if symbol in historical_data and historical_data[symbol]:
                last_data = historical_data[symbol][-1]
                exit_price = last_data.get('close', 0)
                timestamp = last_data.get('timestamp', datetime.now().isoformat())
                
                if exit_price > 0:
                    self._close_position(symbol, exit_price, timestamp, reason)
    
    def _get_price_at_timestamp(
        self,
        symbol: str,
        historical_data: Dict[str, List[Dict[str, Any]]],
        timestamp: str
    ) -> float:
        """获取指定时间戳的价格"""
        if symbol not in historical_data:
            return 0.0
        
        data = historical_data[symbol]
        
        # 简化：找到最接近的时间戳
        for candle in data:
            if candle.get('timestamp', '') >= timestamp:
                return candle.get('close', 0.0)
        
        # 如果没找到，返回最后一个价格
        return data[-1].get('close', 0.0) if data else 0.0
    
    def _calculate_open_position_value(self) -> float:
        """计算当前持仓市值（简化，使用入场价）"""
        return sum(
            pos['shares'] * pos['entry_price']
            for pos in self.positions.values()
        )
    
    def _calculate_metrics(self) -> Dict[str, Any]:
        """计算回测性能指标"""
        if not self.closed_trades:
            return {
                "error": "无交易记录",
                "final_capital": self.capital,
                "total_return": 0.0
            }
        
        # 基础指标
        winning_trades = [t for t in self.closed_trades if t['pnl'] > 0]
        losing_trades = [t for t in self.closed_trades if t['pnl'] <= 0]
        
        total_trades = len(self.closed_trades)
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl = sum(t['pnl'] for t in self.closed_trades)
        total_return = ((self.capital - self.initial_capital) / self.initial_capital) * 100
        
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0
        
        # 风险指标
        returns = [t['pnl_pct'] for t in self.closed_trades]
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        max_drawdown = self._calculate_max_drawdown()
        
        # 交易统计
        avg_hold_time = np.mean([t.get('hold_hours', 0) for t in self.closed_trades])
        
        # 止损统计
        stop_loss_count = len([t for t in self.closed_trades if t['exit_reason'] == 'STOP_LOSS'])
        take_profit_count = len([t for t in self.closed_trades if t['exit_reason'] == 'TAKE_PROFIT'])
        time_limit_count = len([t for t in self.closed_trades if t['exit_reason'] == 'TIME_LIMIT'])
        
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
            "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else float('inf'),
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "avg_hold_time_hours": avg_hold_time,
            "largest_win": max([t['pnl'] for t in self.closed_trades]) if self.closed_trades else 0,
            "largest_loss": min([t['pnl'] for t in self.closed_trades]) if self.closed_trades else 0,
            "total_commission": sum(t.get('total_commission', 0) for t in self.closed_trades),
            "stop_loss_count": stop_loss_count,
            "take_profit_count": take_profit_count,
            "time_limit_count": time_limit_count,
            "alerts_triggered": len(self.alerts_triggered),
            # 强制风控规则参数
            "risk_params": {
                "stop_loss_pct": self.STOP_LOSS_PCT,
                "profit_target_pct": self.PROFIT_TARGET_PCT,
                "max_hold_hours": self.MAX_HOLD_HOURS
            }
        }
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """计算夏普比率"""
        if not returns or len(returns) < 2:
            return 0.0
        
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # 年化（假设252个交易日）
        sharpe = (avg_return / std_return) * np.sqrt(252)
        
        return float(sharpe)
    
    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        if len(self.equity_curve) < 2:
            return 0.0
        
        peak = self.equity_curve[0][1]
        max_dd = 0.0
        
        for _, value in self.equity_curve:
            if value > peak:
                peak = value
            
            dd = ((peak - value) / peak) * 100
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def get_trade_history(self) -> List[Dict[str, Any]]:
        """获取交易历史"""
        return self.closed_trades
    
    def get_equity_curve(self) -> List[tuple]:
        """获取权益曲线"""
        return self.equity_curve
    
    def get_alerts(self) -> List[Dict[str, Any]]:
        """获取告警记录"""
        return self.alerts_triggered
