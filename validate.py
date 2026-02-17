#!/usr/bin/env python3
"""
OpenClaw System Validation Script

This script validates the installation and basic functionality
of the OpenClaw trading system.
"""
import sys
from pathlib import Path

# Add openclaw to path
sys.path.insert(0, str(Path(__file__).parent))

def validate_imports():
    """Validate all core imports"""
    print("=" * 60)
    print("OpenClaw System Validation")
    print("=" * 60)
    print("\n1. Testing imports...")
    
    try:
        from openclaw.core.scheduler import Scheduler
        from openclaw.core.database import DatabaseManager
        from openclaw.core.engine import OpenClawEngine
        from openclaw.skills.analysis.technical_analysis import TechnicalAnalysis
        from openclaw.skills.analysis.risk_management import RiskManagement
        from openclaw.skills.analysis.sentiment_analysis import SentimentAnalysis
        from openclaw.skills.execution.position_tracker import PositionTracker
        from openclaw.skills.execution.order_manager import OrderManager
        from openclaw.utils.logger import setup_logger
        
        print("   ✅ All core modules imported successfully")
        return True
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False


def test_database():
    """Test database operations"""
    print("\n2. Testing database operations...")
    
    try:
        from openclaw.core.database import DatabaseManager
        
        db = DatabaseManager()
        
        # Test set/get
        db.set("test_key", {"value": 123, "name": "test"})
        result = db.get("test_key")
        assert result["value"] == 123
        
        # Test list operations
        db.append_to_list("test_list", "item1")
        db.append_to_list("test_list", "item2")
        items = db.get_list("test_list")
        assert len(items) == 2
        
        # Cleanup
        db.delete("test_key")
        db.delete("test_list")
        db.close()
        
        print("   ✅ Database operations work correctly")
        return True
    except Exception as e:
        print(f"   ❌ Database test failed: {e}")
        return False


def test_technical_analysis():
    """Test technical analysis calculations"""
    print("\n3. Testing technical analysis...")
    
    try:
        from openclaw.skills.analysis.technical_analysis import TechnicalAnalysis
        
        ta = TechnicalAnalysis()
        prices = [100, 102, 104, 103, 105, 107, 106, 108, 110, 109, 111, 113, 112, 115, 117, 116, 118, 120, 119, 122]
        
        # Test moving average
        ma = ta.calculate_ma(prices, 5)
        assert len(ma) > 0
        
        # Test RSI
        rsi = ta.calculate_rsi(prices)
        assert 0 <= rsi <= 100
        
        # Test Bollinger Bands
        bb = ta.calculate_bollinger_bands(prices)
        assert "upper" in bb and "middle" in bb and "lower" in bb
        
        # Test trend
        trend = ta.analyze_trend(prices)
        assert trend in ["uptrend", "downtrend", "sideways", "insufficient_data"]
        
        print(f"   ✅ Technical analysis works (RSI: {rsi:.1f}, Trend: {trend})")
        return True
    except Exception as e:
        print(f"   ❌ Technical analysis test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_risk_management():
    """Test risk management calculations"""
    print("\n4. Testing risk management...")
    
    try:
        from openclaw.skills.analysis.risk_management import RiskManagement
        
        config = {
            "max_position_size": 0.1,
            "max_loss_per_trade": 0.02,
            "max_daily_loss": 0.05,
            "max_drawdown": 0.15,
            "stop_loss": {"enabled": True, "type": "fixed", "percentage": 0.05},
            "take_profit": {"enabled": True, "type": "fixed", "percentage": 0.10}
        }
        
        risk_mgr = RiskManagement(config)
        
        # Test position sizing
        position_size = risk_mgr.calculate_position_size(
            portfolio_value=100000,
            entry_price=100
        )
        assert position_size > 0
        
        # Test stop loss
        stop_loss = risk_mgr.calculate_stop_loss(entry_price=100)
        assert abs(stop_loss - 95.0) < 0.1  # Allow small floating point error
        
        # Test take profit
        take_profit = risk_mgr.calculate_take_profit(entry_price=100)
        assert abs(take_profit - 110.0) < 0.1
        
        print(f"   ✅ Risk management works (Position: {position_size} shares, SL: ${stop_loss:.2f})")
        return True
    except Exception as e:
        print(f"   ❌ Risk management test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_position_tracker():
    """Test position tracking"""
    print("\n5. Testing position tracking...")
    
    try:
        from openclaw.skills.execution.position_tracker import PositionTracker
        
        tracker = PositionTracker(initial_capital=100000)
        
        # Open position
        result = tracker.open_position("AAPL", 100, 150.0)
        assert result["success"]
        assert tracker.cash == 100000 - 15000
        
        # Close position with profit
        result = tracker.close_position("AAPL", 100, 160.0)
        assert result["success"]
        assert result["closed_position"]["pnl"] == 1000.0
        
        # Check metrics
        metrics = tracker.calculate_performance_metrics({})
        assert metrics["total_return"] == 1000.0
        
        print(f"   ✅ Position tracking works (P&L: ${metrics['total_return']:.2f})")
        return True
    except Exception as e:
        print(f"   ❌ Position tracker test failed: {e}")
        return False


def test_engine_initialization():
    """Test engine initialization"""
    print("\n6. Testing engine initialization...")
    
    try:
        from openclaw.core.engine import OpenClawEngine
        
        engine = OpenClawEngine()
        
        assert engine.scheduler is not None
        assert engine.ai_models is not None
        assert engine.stock_monitor is not None
        assert engine.crypto_monitor is not None
        
        print("   ✅ Engine initialized successfully")
        return True
    except Exception as e:
        print(f"   ❌ Engine initialization failed: {e}")
        return False


def main():
    """Run all validation tests"""
    tests = [
        validate_imports,
        test_database,
        test_technical_analysis,
        test_risk_management,
        test_position_tracker,
        test_engine_initialization
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"   ❌ Test crashed: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    
    print(f"\nTests passed: {passed}/{total}")
    
    if all(results):
        print("\n✅ All validation tests passed!")
        print("\nNext steps:")
        print("1. Install AI dependencies: pip install -r requirements-ai.txt")
        print("2. Configure API keys in .env (optional)")
        print("3. Run the system: python main.py")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
