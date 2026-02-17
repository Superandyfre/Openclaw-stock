"""
Order manager for trade execution
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from loguru import logger


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(Enum):
    """Order type enumeration"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderManager:
    """Manages order creation and execution"""
    
    def __init__(self, dry_run: bool = True):
        """
        Initialize order manager
        
        Args:
            dry_run: If True, simulate orders without actual execution
        """
        self.dry_run = dry_run
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.order_counter = 0
    
    def create_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create a new order
        
        Args:
            symbol: Asset symbol
            action: BUY or SELL
            quantity: Number of shares/units
            order_type: Type of order
            price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
        
        Returns:
            Order details
        """
        # Validate order
        validation = self._validate_order(symbol, action, quantity, order_type, price)
        if not validation['valid']:
            logger.error(f"Order validation failed: {validation['reason']}")
            return {
                "status": "rejected",
                "reason": validation['reason']
            }
        
        # Generate order ID
        self.order_counter += 1
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d')}-{self.order_counter:06d}"
        
        order = {
            "order_id": order_id,
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "order_type": order_type.value,
            "price": price,
            "stop_price": stop_price,
            "status": OrderStatus.PENDING.value,
            "filled_quantity": 0,
            "filled_price": 0.0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "dry_run": self.dry_run
        }
        
        self.orders[order_id] = order
        
        logger.info(f"Created order {order_id}: {action} {quantity} {symbol} @ {order_type.value}")
        
        # Submit order
        if self.dry_run:
            self._simulate_order_execution(order_id)
        else:
            self._submit_order_to_exchange(order_id)
        
        return order
    
    def _validate_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: OrderType,
        price: Optional[float]
    ) -> Dict[str, Any]:
        """Validate order parameters"""
        if action not in ['BUY', 'SELL']:
            return {"valid": False, "reason": "Invalid action. Must be BUY or SELL"}
        
        if quantity <= 0:
            return {"valid": False, "reason": "Quantity must be positive"}
        
        if order_type == OrderType.LIMIT and price is None:
            return {"valid": False, "reason": "Limit orders require a price"}
        
        return {"valid": True, "reason": ""}
    
    def _simulate_order_execution(self, order_id: str):
        """Simulate order execution (dry run)"""
        order = self.orders[order_id]
        
        # Simulate immediate fill for market orders
        if order['order_type'] == OrderType.MARKET.value:
            order['status'] = OrderStatus.FILLED.value
            order['filled_quantity'] = order['quantity']
            order['filled_price'] = order.get('price', 0) or 100.0  # Mock price
            order['updated_at'] = datetime.now().isoformat()
            
            logger.info(f"✅ [DRY RUN] Order {order_id} filled at {order['filled_price']}")
        else:
            order['status'] = OrderStatus.SUBMITTED.value
            order['updated_at'] = datetime.now().isoformat()
            logger.info(f"📝 [DRY RUN] Order {order_id} submitted")
    
    def _submit_order_to_exchange(self, order_id: str):
        """Submit order to actual exchange"""
        order = self.orders[order_id]
        
        # This is where you would integrate with actual exchange APIs
        # For example: Binance, Upbit, Interactive Brokers, etc.
        
        try:
            # Placeholder for actual API call
            logger.warning(f"⚠️  Real trading not implemented. Order {order_id} not submitted.")
            order['status'] = OrderStatus.SUBMITTED.value
            order['updated_at'] = datetime.now().isoformat()
        except Exception as e:
            logger.error(f"Failed to submit order {order_id}: {e}")
            order['status'] = OrderStatus.REJECTED.value
            order['updated_at'] = datetime.now().isoformat()
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            True if cancelled successfully
        """
        if order_id not in self.orders:
            logger.error(f"Order {order_id} not found")
            return False
        
        order = self.orders[order_id]
        
        if order['status'] in [OrderStatus.FILLED.value, OrderStatus.CANCELLED.value]:
            logger.warning(f"Cannot cancel order {order_id} with status {order['status']}")
            return False
        
        order['status'] = OrderStatus.CANCELLED.value
        order['updated_at'] = datetime.now().isoformat()
        
        logger.info(f"Cancelled order {order_id}")
        return True
    
    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order details"""
        return self.orders.get(order_id)
    
    def get_all_orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all orders, optionally filtered by status
        
        Args:
            status: Filter by order status
        
        Returns:
            List of orders
        """
        if status:
            return [o for o in self.orders.values() if o['status'] == status]
        return list(self.orders.values())
    
    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get all open orders"""
        return [
            o for o in self.orders.values()
            if o['status'] in [OrderStatus.PENDING.value, OrderStatus.SUBMITTED.value, OrderStatus.PARTIALLY_FILLED.value]
        ]
