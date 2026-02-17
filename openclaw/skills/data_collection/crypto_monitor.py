"""
Cryptocurrency monitor using Upbit WebSocket
"""
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets not available")


class CryptoMonitor:
    """
    Monitors cryptocurrency prices via Upbit WebSocket
    
    Features:
    - Real-time updates (no rate limit)
    - 15 cryptocurrencies
    - WebSocket connection
    """
    
    def __init__(self, symbols: List[str], websocket_url: str):
        """
        Initialize crypto monitor
        
        Args:
            symbols: List of cryptocurrency symbols (e.g., KRW-BTC)
            websocket_url: Upbit WebSocket URL
        """
        self.symbols = symbols
        self.websocket_url = websocket_url
        self.websocket = None
        self.last_data: Dict[str, Dict[str, Any]] = {}
        self.running = False
    
    async def connect(self):
        """Establish WebSocket connection"""
        if not WEBSOCKETS_AVAILABLE:
            logger.warning("WebSocket not available, using mock data")
            return
        
        try:
            self.websocket = await websockets.connect(self.websocket_url)
            
            # Subscribe to ticker updates
            subscribe_message = [
                {"ticket": "openclaw"},
                {
                    "type": "ticker",
                    "codes": self.symbols
                }
            ]
            
            await self.websocket.send(json.dumps(subscribe_message))
            logger.info(f"✅ Connected to Upbit WebSocket for {len(self.symbols)} cryptocurrencies")
        except Exception as e:
            logger.error(f"Failed to connect to Upbit WebSocket: {e}")
            self.websocket = None
    
    async def start_monitoring(self):
        """Start monitoring cryptocurrency prices"""
        self.running = True
        
        if not self.websocket:
            # Use mock data if WebSocket not available
            asyncio.create_task(self._mock_data_loop())
            return
        
        try:
            while self.running:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=30.0
                    )
                    
                    # Parse message
                    data = json.loads(message)
                    self._process_ticker_data(data)
                
                except asyncio.TimeoutError:
                    logger.warning("WebSocket timeout, reconnecting...")
                    await self.connect()
                except Exception as e:
                    logger.error(f"Error receiving WebSocket message: {e}")
                    await asyncio.sleep(5)
        
        except Exception as e:
            logger.error(f"WebSocket monitoring error: {e}")
    
    def _process_ticker_data(self, data: Dict[str, Any]):
        """Process incoming ticker data"""
        try:
            symbol = data.get('code', '')
            
            ticker_data = {
                "symbol": symbol,
                "current_price": data.get('trade_price', 0),
                "opening_price": data.get('opening_price', 0),
                "high_price": data.get('high_price', 0),
                "low_price": data.get('low_price', 0),
                "prev_closing_price": data.get('prev_closing_price', 0),
                "change": data.get('change', 'RISE'),
                "change_price": data.get('change_price', 0),
                "change_rate": data.get('change_rate', 0) * 100,
                "volume": data.get('acc_trade_volume_24h', 0),
                "trade_volume": data.get('trade_volume', 0),
                "timestamp": datetime.now().isoformat()
            }
            
            self.last_data[symbol] = ticker_data
        
        except Exception as e:
            logger.error(f"Failed to process ticker data: {e}")
    
    async def _mock_data_loop(self):
        """Generate mock data for testing"""
        import random
        
        while self.running:
            for symbol in self.symbols:
                base_price = 50000000 if 'BTC' in symbol else 1000000
                change_rate = random.uniform(-5, 5)
                current_price = base_price * (1 + change_rate / 100)
                
                self.last_data[symbol] = {
                    "symbol": symbol,
                    "current_price": current_price,
                    "opening_price": base_price,
                    "high_price": current_price * 1.03,
                    "low_price": current_price * 0.97,
                    "prev_closing_price": base_price,
                    "change": "RISE" if change_rate > 0 else "FALL",
                    "change_price": current_price - base_price,
                    "change_rate": change_rate,
                    "volume": random.randint(1000, 10000),
                    "trade_volume": random.randint(100, 1000),
                    "timestamp": datetime.now().isoformat(),
                    "mock": True
                }
            
            await asyncio.sleep(1)  # Update every second for mock data
    
    def get_current_data(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current cryptocurrency data
        
        Args:
            symbol: Specific symbol or None for all
        
        Returns:
            Current data dictionary
        """
        if symbol:
            return self.last_data.get(symbol, {})
        return self.last_data.copy()
    
    async def stop(self):
        """Stop monitoring and close connection"""
        self.running = False
        
        if self.websocket:
            await self.websocket.close()
            logger.info("Closed Upbit WebSocket connection")
