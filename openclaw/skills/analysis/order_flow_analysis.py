"""
Order Flow Analysis Module

Analyzes order book data, large orders, and tape reading for short-term trading
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
import numpy as np


class OrderFlowAnalysis:
    """
    Analyzes order flow and market microstructure
    
    Features:
    - Large order detection
    - Buy/sell pressure analysis
    - Order book imbalance
    - Tape reading (time & sales)
    """
    
    def __init__(self, large_order_threshold: float = 100000):
        """
        Initialize order flow analyzer
        
        Args:
            large_order_threshold: Minimum size for large order detection
        """
        self.large_order_threshold = large_order_threshold
        self.order_history: List[Dict[str, Any]] = []
        self.large_orders: List[Dict[str, Any]] = []
    
    def analyze_order_book(
        self,
        bids: List[Dict[str, float]],
        asks: List[Dict[str, float]],
        depth_levels: int = 10
    ) -> Dict[str, Any]:
        """
        Analyze order book for imbalances
        
        Args:
            bids: List of bid orders [{"price": p, "size": s}, ...]
            asks: List of ask orders [{"price": p, "size": s}, ...]
            depth_levels: Number of depth levels to analyze
        
        Returns:
            Order book analysis results
        """
        if not bids or not asks:
            return {
                "imbalance_ratio": 1.0,
                "pressure": "neutral",
                "bid_depth": 0,
                "ask_depth": 0
            }
        
        # Calculate bid and ask depth (volume)
        bid_volume = sum(b.get('size', 0) for b in bids[:depth_levels])
        ask_volume = sum(a.get('size', 0) for a in asks[:depth_levels])
        
        # Calculate imbalance ratio
        total_volume = bid_volume + ask_volume
        if total_volume > 0:
            imbalance_ratio = bid_volume / total_volume
        else:
            imbalance_ratio = 0.5
        
        # Determine pressure
        if imbalance_ratio > 0.6:
            pressure = "strong_buy"
        elif imbalance_ratio > 0.55:
            pressure = "buy"
        elif imbalance_ratio < 0.4:
            pressure = "strong_sell"
        elif imbalance_ratio < 0.45:
            pressure = "sell"
        else:
            pressure = "neutral"
        
        # Calculate spread
        best_bid = bids[0].get('price', 0) if bids else 0
        best_ask = asks[0].get('price', 0) if asks else 0
        spread = best_ask - best_bid if best_bid and best_ask else 0
        spread_pct = (spread / best_bid * 100) if best_bid > 0 else 0
        
        return {
            "imbalance_ratio": imbalance_ratio,
            "pressure": pressure,
            "bid_depth": bid_volume,
            "ask_depth": ask_volume,
            "total_depth": total_volume,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "spread_pct": spread_pct
        }
    
    def detect_large_orders(
        self,
        recent_trades: List[Dict[str, Any]],
        time_window_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Detect large orders from recent trades
        
        Args:
            recent_trades: List of recent trades
            time_window_seconds: Time window to analyze
        
        Returns:
            Large order detection results
        """
        if not recent_trades:
            return {
                "large_orders": [],
                "large_buy_orders": 0,
                "large_sell_orders": 0,
                "total_large_volume": 0
            }
        
        # Filter for recent large orders
        cutoff_time = datetime.now() - timedelta(seconds=time_window_seconds)
        large_orders = []
        
        for trade in recent_trades:
            trade_time = trade.get('timestamp', datetime.now())
            if isinstance(trade_time, str):
                trade_time = datetime.fromisoformat(trade_time)
            
            trade_size_value = trade.get('size', 0) * trade.get('price', 0)
            
            if trade_time >= cutoff_time and trade_size_value >= self.large_order_threshold:
                large_orders.append(trade)
        
        # Categorize by side
        large_buy_orders = [o for o in large_orders if o.get('side') == 'buy']
        large_sell_orders = [o for o in large_orders if o.get('side') == 'sell']
        
        total_large_volume = sum(o.get('size', 0) * o.get('price', 0) for o in large_orders)
        
        # Store for history
        self.large_orders.extend(large_orders)
        if len(self.large_orders) > 1000:
            self.large_orders = self.large_orders[-1000:]
        
        return {
            "large_orders": large_orders,
            "large_buy_orders": len(large_buy_orders),
            "large_sell_orders": len(large_sell_orders),
            "total_large_volume": total_large_volume,
            "net_large_order_flow": len(large_buy_orders) - len(large_sell_orders)
        }
    
    def analyze_tape(
        self,
        recent_trades: List[Dict[str, Any]],
        time_window_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Analyze time & sales (tape reading)
        
        Args:
            recent_trades: List of recent trades
            time_window_seconds: Time window to analyze
        
        Returns:
            Tape reading analysis
        """
        if not recent_trades:
            return {
                "trade_count": 0,
                "buy_trades": 0,
                "sell_trades": 0,
                "avg_trade_size": 0,
                "buy_sell_ratio": 1.0
            }
        
        # Filter recent trades
        cutoff_time = datetime.now() - timedelta(seconds=time_window_seconds)
        recent = []
        
        for trade in recent_trades:
            trade_time = trade.get('timestamp', datetime.now())
            if isinstance(trade_time, str):
                trade_time = datetime.fromisoformat(trade_time)
            
            if trade_time >= cutoff_time:
                recent.append(trade)
        
        if not recent:
            return {
                "trade_count": 0,
                "buy_trades": 0,
                "sell_trades": 0,
                "avg_trade_size": 0,
                "buy_sell_ratio": 1.0
            }
        
        # Categorize trades
        buy_trades = [t for t in recent if t.get('side') == 'buy']
        sell_trades = [t for t in recent if t.get('side') == 'sell']
        
        # Calculate metrics
        avg_trade_size = np.mean([t.get('size', 0) for t in recent])
        total_buy_volume = sum(t.get('size', 0) for t in buy_trades)
        total_sell_volume = sum(t.get('size', 0) for t in sell_trades)
        
        buy_sell_ratio = total_buy_volume / total_sell_volume if total_sell_volume > 0 else 1.0
        
        # Determine market character
        if buy_sell_ratio > 1.5:
            character = "aggressive_buying"
        elif buy_sell_ratio > 1.1:
            character = "buying"
        elif buy_sell_ratio < 0.67:
            character = "aggressive_selling"
        elif buy_sell_ratio < 0.9:
            character = "selling"
        else:
            character = "balanced"
        
        return {
            "trade_count": len(recent),
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "avg_trade_size": float(avg_trade_size),
            "total_buy_volume": total_buy_volume,
            "total_sell_volume": total_sell_volume,
            "buy_sell_ratio": buy_sell_ratio,
            "market_character": character
        }
    
    def calculate_order_flow_strength(
        self,
        order_book_data: Dict[str, Any],
        large_order_data: Dict[str, Any],
        tape_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate overall order flow strength score
        
        Args:
            order_book_data: Order book analysis
            large_order_data: Large order detection results
            tape_data: Tape reading analysis
        
        Returns:
            Order flow strength score and interpretation
        """
        # Score components (0-10 each)
        scores = {
            "order_book": 0,
            "large_orders": 0,
            "tape": 0
        }
        
        # Order book score
        imbalance = order_book_data.get('imbalance_ratio', 0.5)
        if imbalance > 0.6:
            scores["order_book"] = min(10, (imbalance - 0.5) * 20)
        elif imbalance < 0.4:
            scores["order_book"] = max(-10, (imbalance - 0.5) * 20)
        
        # Large order score
        net_flow = large_order_data.get('net_large_order_flow', 0)
        scores["large_orders"] = min(10, max(-10, net_flow * 2))
        
        # Tape score
        buy_sell_ratio = tape_data.get('buy_sell_ratio', 1.0)
        if buy_sell_ratio > 1:
            scores["tape"] = min(10, (buy_sell_ratio - 1) * 10)
        else:
            scores["tape"] = max(-10, (buy_sell_ratio - 1) * 10)
        
        # Overall score (weighted average)
        overall_score = (
            scores["order_book"] * 0.4 +
            scores["large_orders"] * 0.4 +
            scores["tape"] * 0.2
        )
        
        # Interpretation
        if overall_score > 5:
            strength = "very_strong_buy"
        elif overall_score > 2:
            strength = "strong_buy"
        elif overall_score > 0:
            strength = "mild_buy"
        elif overall_score > -2:
            strength = "neutral"
        elif overall_score > -5:
            strength = "mild_sell"
        elif overall_score > -7:
            strength = "strong_sell"
        else:
            strength = "very_strong_sell"
        
        return {
            "overall_score": overall_score,
            "strength": strength,
            "component_scores": scores,
            "confidence": min(1.0, abs(overall_score) / 10)
        }
    
    def detect_spoofing(
        self,
        order_book_history: List[Dict[str, Any]],
        time_window_seconds: int = 10
    ) -> Dict[str, Any]:
        """
        Detect potential spoofing (fake orders)
        
        Args:
            order_book_history: Historical order book snapshots
            time_window_seconds: Time window to analyze
        
        Returns:
            Spoofing detection results
        """
        # Simplified spoofing detection
        # In production, would need more sophisticated analysis
        
        if len(order_book_history) < 3:
            return {
                "spoofing_detected": False,
                "confidence": 0.0
            }
        
        # Look for large orders that appear and disappear quickly
        # without being filled
        
        return {
            "spoofing_detected": False,
            "confidence": 0.0,
            "note": "Spoofing detection requires more historical data"
        }
