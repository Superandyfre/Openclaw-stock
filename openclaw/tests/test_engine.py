"""
Tests for OpenClaw Trading Engine
"""
import pytest
import asyncio
from openclaw.core.engine import OpenClawEngine
from openclaw.core.scheduler import Scheduler
from openclaw.core.database import DatabaseManager
from openclaw.skills.analysis.technical_analysis import TechnicalAnalysis
from openclaw.skills.analysis.risk_management import RiskManagement
from openclaw.skills.execution.position_tracker import PositionTracker


class TestEngine:
    """Test OpenClaw Engine"""
    
    def test_engine_initialization(self):
        """Test engine initializes without errors"""
        engine = OpenClawEngine()
        assert engine is not None
        assert engine.scheduler is not None
        assert engine.ai_models is not None
    
    @pytest.mark.asyncio
    async def test_scheduler(self):
        """Test scheduler functionality"""
        scheduler = Scheduler()
        scheduler.start()
        
        counter = {"value": 0}
        
        async def increment():
            counter["value"] += 1
        
        await scheduler.schedule_periodic("test_task", increment, 1)
        await asyncio.sleep(2.5)
        
        await scheduler.stop()
        
        # Should have run at least 2 times
        assert counter["value"] >= 2


class TestDatabase:
    """Test database operations"""
    
    def test_database_set_get(self):
        """Test set and get operations"""
        db = DatabaseManager()
        
        # Test set and get
        db.set("test_key", {"value": 123})
        result = db.get("test_key")
        
        assert result == {"value": 123}
        
        # Test delete
        db.delete("test_key")
        assert db.get("test_key") is None
        
        db.close()
    
    def test_database_list_operations(self):
        """Test list operations"""
        db = DatabaseManager()
        
        # Append to list
        db.append_to_list("test_list", "item1")
        db.append_to_list("test_list", "item2")
        db.append_to_list("test_list", "item3")
        
        result = db.get_list("test_list")
        assert len(result) == 3
        assert "item1" in result
        
        db.delete("test_list")
        db.close()


class TestTechnicalAnalysis:
    """Test technical analysis functions"""
    
    def test_moving_average(self):
        """Test moving average calculation"""
        prices = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
        ma = TechnicalAnalysis.calculate_ma(prices, 5)
        
        assert len(ma) == 7  # 11 prices - 5 + 1
        assert ma[0] == 12.0  # Average of first 5
    
    def test_rsi(self):
        """Test RSI calculation"""
        prices = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 
                 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00]
        
        rsi = TechnicalAnalysis.calculate_rsi(prices, 14)
        
        assert 0 <= rsi <= 100
    
    def test_bollinger_bands(self):
        """Test Bollinger Bands calculation"""
        prices = [100 + i for i in range(50)]
        
        bb = TechnicalAnalysis.calculate_bollinger_bands(prices, 20, 2.0)
        
        assert "upper" in bb
        assert "middle" in bb
        assert "lower" in bb
        assert bb["upper"] > bb["middle"] > bb["lower"]


class TestRiskManagement:
    """Test risk management"""
    
    def test_position_sizing(self):
        """Test position size calculation"""
        config = {
            "max_position_size": 0.1,
            "max_loss_per_trade": 0.02,
            "max_daily_loss": 0.05,
            "max_drawdown": 0.15,
            "stop_loss": {"enabled": True, "type": "trailing", "percentage": 0.05},
            "take_profit": {"enabled": True, "type": "fixed", "percentage": 0.10}
        }
        
        risk_mgr = RiskManagement(config)
        
        portfolio_value = 100000
        entry_price = 100
        
        position_size = risk_mgr.calculate_position_size(portfolio_value, entry_price)
        
        assert position_size > 0
        assert position_size * entry_price <= portfolio_value * 0.1
    
    def test_stop_loss_calculation(self):
        """Test stop loss calculation"""
        config = {
            "max_position_size": 0.1,
            "max_loss_per_trade": 0.02,
            "stop_loss": {"enabled": True, "type": "fixed", "percentage": 0.05}
        }
        
        risk_mgr = RiskManagement(config)
        
        entry_price = 100
        stop_loss = risk_mgr.calculate_stop_loss(entry_price)
        
        assert stop_loss == 95.0  # 5% below entry
    
    def test_take_profit_calculation(self):
        """Test take profit calculation"""
        config = {
            "take_profit": {"enabled": True, "type": "fixed", "percentage": 0.10}
        }
        
        risk_mgr = RiskManagement(config)
        
        entry_price = 100
        take_profit = risk_mgr.calculate_take_profit(entry_price)
        
        assert take_profit == 110.0  # 10% above entry


class TestPositionTracker:
    """Test position tracking"""
    
    def test_open_position(self):
        """Test opening a position"""
        tracker = PositionTracker(initial_capital=100000)
        
        result = tracker.open_position("AAPL", 100, 150.0)
        
        assert result["success"] is True
        assert tracker.cash == 100000 - (100 * 150)
        assert "AAPL" in tracker.positions
    
    def test_close_position(self):
        """Test closing a position"""
        tracker = PositionTracker(initial_capital=100000)
        
        # Open position
        tracker.open_position("AAPL", 100, 150.0)
        
        # Close position with profit
        result = tracker.close_position("AAPL", 100, 160.0)
        
        assert result["success"] is True
        assert result["closed_position"]["pnl"] == 1000.0  # (160 - 150) * 100
        assert "AAPL" not in tracker.positions
    
    def test_portfolio_value(self):
        """Test portfolio value calculation"""
        tracker = PositionTracker(initial_capital=100000)
        
        tracker.open_position("AAPL", 100, 150.0)
        tracker.open_position("GOOGL", 50, 200.0)
        
        current_prices = {"AAPL": 160.0, "GOOGL": 210.0}
        
        portfolio_value = tracker.calculate_portfolio_value(current_prices)
        
        # Initial: 100000
        # Spent: (100 * 150) + (50 * 200) = 25000
        # Cash remaining: 75000
        # Position value: (100 * 160) + (50 * 210) = 26500
        # Total: 75000 + 26500 = 101500
        
        assert portfolio_value == 101500.0
    
    def test_performance_metrics(self):
        """Test performance metrics calculation"""
        tracker = PositionTracker(initial_capital=100000)
        
        # Make some trades
        tracker.open_position("AAPL", 100, 150.0)
        tracker.close_position("AAPL", 100, 160.0)  # Profit
        
        tracker.open_position("GOOGL", 50, 200.0)
        tracker.close_position("GOOGL", 50, 190.0)  # Loss
        
        current_prices = {}
        metrics = tracker.calculate_performance_metrics(current_prices)
        
        assert "portfolio_value" in metrics
        assert "total_return" in metrics
        assert "win_rate" in metrics
        assert metrics["num_closed_trades"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
