#!/usr/bin/env python3
"""
简化但可用的持仓管理器
绕过原始代码的 bug
"""
import redis
import json
from typing import Dict, Any, Optional
from datetime import datetime


class SimplePositionManager:
    """简化的持仓管理器"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.positions_key = "simple_positions"
        self.trades_key = "simple_trades"
    
    def open_position(self, symbol: str, quantity: float, entry_price: float, note: str = ""):
        """开仓"""
        position = {
            'symbol': symbol,
            'quantity': quantity,
            'entry_price': entry_price,
            'entry_time': datetime.now().isoformat(),
            'cost': quantity * entry_price,
            'note': note
        }
        
        # 保存到 Redis
        self.redis.hset(self.positions_key, symbol, json.dumps(position))
        
        # 记录交易
        trade = {
            'symbol': symbol,
            'action': 'OPEN',
            'quantity': quantity,
            'price': entry_price,
            'time': datetime.now().isoformat(),
            'note': note
        }
        self.redis.lpush(self.trades_key, json.dumps(trade))
        
        print(f"✅ 开仓: {symbol} {quantity} @ ₩{entry_price:,.0f}")
        return position
    
    def close_position(self, symbol: str, exit_price: float, note: str = ""):
        """平仓"""
        position_data = self.redis.hget(self.positions_key, symbol)
        
        if not position_data:
            raise ValueError(f"Position {symbol} not found")
        
        position = json.loads(position_data)
        
        # 计算盈亏
        quantity = position['quantity']
        entry_price = position['entry_price']
        pnl = (exit_price - entry_price) * quantity
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        
        # 记录交易
        trade = {
            'symbol': symbol,
            'action': 'CLOSE',
            'quantity': quantity,
            'price': exit_price,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'time': datetime.now().isoformat(),
            'note': note
        }
        self.redis.lpush(self.trades_key, json.dumps(trade))
        
        # 删除持仓
        self.redis.hdel(self.positions_key, symbol)
        
        print(f"✅ 平仓: {symbol} PnL: ₩{pnl:,.0f} ({pnl_pct:+.2f}%)")
        return trade
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取单个持仓"""
        position_data = self.redis.hget(self.positions_key, symbol)
        if position_data:
            return json.loads(position_data)
        return None
    
    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """获取所有持仓"""
        positions = {}
        for symbol, data in self.redis.hgetall(self.positions_key).items():
            positions[symbol] = json.loads(data)
        return positions
    
    def get_stock_positions(self) -> Dict[str, Dict[str, Any]]:
        """获取股票持仓"""
        all_positions = self.get_all_positions()
        return {
            symbol: pos for symbol, pos in all_positions.items()
            if not symbol.startswith('KRW-') and not symbol.startswith('USDT-')
        }
    
    def get_crypto_positions(self) -> Dict[str, Dict[str, Any]]:
        """获取加密货币持仓"""
        all_positions = self.get_all_positions()
        return {
            symbol: pos for symbol, pos in all_positions.items()
            if symbol.startswith('KRW-') or symbol.startswith('USDT-')
        }
    
    def calculate_portfolio_value(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """计算组合价值"""
        positions = self.get_all_positions()
        
        total_cost = 0
        total_value = 0
        
        for symbol, position in positions.items():
            cost = position['cost']
            current_price = current_prices.get(symbol, position['entry_price'])
            value = position['quantity'] * current_price
            
            total_cost += cost
            total_value += value
        
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
        
        return {
            'total_cost': total_cost,
            'total_value': total_value,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'count': len(positions)
        }
    
    def calculate_portfolio_by_type(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """按类型计算组合"""
        stock_positions = self.get_stock_positions()
        crypto_positions = self.get_crypto_positions()
        
        # 计算股票
        stocks_cost = 0
        stocks_value = 0
        for symbol, position in stock_positions.items():
            stocks_cost += position['cost']
            current_price = current_prices.get(symbol, position['entry_price'])
            stocks_value += position['quantity'] * current_price
        
        stocks_pnl = stocks_value - stocks_cost
        stocks_pnl_pct = (stocks_pnl / stocks_cost * 100) if stocks_cost > 0 else 0
        
        # 计算加密货币
        crypto_cost = 0
        crypto_value = 0
        for symbol, position in crypto_positions.items():
            crypto_cost += position['cost']
            current_price = current_prices.get(symbol, position['entry_price'])
            crypto_value += position['quantity'] * current_price
        
        crypto_pnl = crypto_value - crypto_cost
        crypto_pnl_pct = (crypto_pnl / crypto_cost * 100) if crypto_cost > 0 else 0
        
        # 总计
        total_cost = stocks_cost + crypto_cost
        total_value = stocks_value + crypto_value
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
        
        return {
            'stocks': {
                'count': len(stock_positions),
                'total_cost': stocks_cost,
                'total_value': stocks_value,
                'total_pnl': stocks_pnl,
                'total_pnl_pct': stocks_pnl_pct,
            },
            'crypto': {
                'count': len(crypto_positions),
                'total_cost': crypto_cost,
                'total_value': crypto_value,
                'total_pnl': crypto_pnl,
                'total_pnl_pct': crypto_pnl_pct,
            },
            'total': {
                'count': len(stock_positions) + len(crypto_positions),
                'total_cost': total_cost,
                'total_value': total_value,
                'total_pnl': total_pnl,
                'total_pnl_pct': total_pnl_pct,
            }
        }
    
    def get_trades_history(self, limit: int = 50) -> list:
        """获取交易历史"""
        trades_data = self.redis.lrange(self.trades_key, 0, limit - 1)
        return [json.loads(trade) for trade in trades_data]
    
    def clear_all(self):
        """清除所有数据"""
        self.redis.delete(self.positions_key)
        self.redis.delete(self.trades_key)
        print("✅ 所有数据已清除")


# 测试
if __name__ == '__main__':
    print("🧪 测试 SimplePositionManager")
    print("="*60)
    
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    pm = SimplePositionManager(r)
    
    print("\n1️⃣ 添加持仓:")
    pm.open_position('005930', 10, 181200, '삼성전자')
    pm.open_position('035420', 5, 252500, 'NAVER')
    pm.open_position('KRW-BTC', 0.5, 60000000, 'Bitcoin')
    
    print("\n2️⃣ 查看所有持仓:")
    positions = pm.get_all_positions()
    for symbol, pos in positions.items():
        print(f"   {symbol}: {pos['quantity']} @ ₩{pos['entry_price']:,}")
    
    print("\n3️⃣ 计算组合价值:")
    current_prices = {
        '005930': 183000,   # +1%
        '035420': 255000,   # +1%
        'KRW-BTC': 61000000, # +1.67%
    }
    
    portfolio = pm.calculate_portfolio_value(current_prices)
    print(f"   总成本: ₩{portfolio['total_cost']:,.0f}")
    print(f"   总市值: ₩{portfolio['total_value']:,.0f}")
    print(f"   总盈亏: ₩{portfolio['total_pnl']:,.0f} ({portfolio['total_pnl_pct']:+.2f}%)")
    
    print("\n4️⃣ 按类型统计:")
    by_type = pm.calculate_portfolio_by_type(current_prices)
    
    print(f"   股票: ₩{by_type['stocks']['total_value']:,.0f} "
          f"(PnL: ₩{by_type['stocks']['total_pnl']:,.0f})")
    print(f"   加密: ₩{by_type['crypto']['total_value']:,.0f} "
          f"(PnL: ₩{by_type['crypto']['total_pnl']:,.0f})")
    
    print("\n5️⃣ 清理测试数据:")
    pm.clear_all()
    
    print("\n" + "="*60)
    print("✅ 测试完成")
