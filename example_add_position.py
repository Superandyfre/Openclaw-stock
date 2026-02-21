#!/usr/bin/env python3
"""
示例：如何添加和管理持仓
"""
import redis
from openclaw.skills.execution.position_tracker import PositionTracker
from openclaw.core.portfolio_manager import PortfolioManager

print("📝 持仓管理示例")
print("="*60)

# 初始化
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
tracker = PositionTracker(r)
pm = PortfolioManager(tracker)

print("✅ 系统初始化完成\n")

# 查看 PositionTracker 的方法
print("📋 PositionTracker 可用方法:")
methods = [m for m in dir(tracker) if not m.startswith('_') and callable(getattr(tracker, m))]
for method in methods:
    print(f"   • {method}")

print("\n" + "="*60)

# 示例：如果有 add_position 或类似方法
if hasattr(tracker, 'add_position'):
    print("\n💡 示例：添加持仓")
    print("   tracker.add_position('005930', quantity=10, price=181200)")

if hasattr(tracker, 'positions'):
    print("\n💡 示例：查看所有持仓")
    print("   positions = tracker.positions")
    
    try:
        positions = tracker.positions
        print(f"\n   当前持仓: {positions}")
    except Exception as e:
        print(f"\n   ⚠️  {e}")

print("\n" + "="*60)
print("✅ 示例完成")
