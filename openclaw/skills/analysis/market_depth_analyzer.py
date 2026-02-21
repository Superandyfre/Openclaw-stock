"""
市场深度分析器

功能：
- 5档/20档订单簿分析
- Bid/Ask 不对称率
- 大单墙检测
- 成交主动性分析
- 冲击成本估算
- 杠杆清算区域识别
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import numpy as np
from loguru import logger


class MarketDepthAnalyzer:
    """
    市场深度分析器
    
    分析订单簿数据，识别市场微观结构信号
    """
    
    def __init__(self):
        """初始化深度分析器"""
        # 配置参数
        self.large_order_threshold = 1000000  # 大单阈值（金额）
        self.wall_detection_ratio = 5.0  # 订单墙检测比率（5倍于平均）
        self.impact_basis_points = 10  # 冲击成本计算基点
        
        # 历史数据缓存
        self.depth_history: List[Dict[str, Any]] = []
        self.max_history = 100
        
        logger.info("✅ MarketDepthAnalyzer 初始化成功")
    
    def analyze_orderbook(
        self,
        symbol: str,
        orderbook: Dict[str, Any],
        trade_amount: float = 0
    ) -> Dict[str, Any]:
        """
        分析订单簿
        
        Args:
            symbol: 交易对
            orderbook: 订单簿数据 {bids: [[price, size], ...], asks: [[price, size], ...]}
            trade_amount: 交易金额（用于冲击成本估算）
        
        Returns:
            分析结果
        """
        try:
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            
            if not bids or not asks:
                return {"error": "订单簿数据不完整"}
            
            # 1. 基础深度指标
            depth_5 = self._analyze_depth_levels(bids[:5], asks[:5], levels=5)
            depth_20 = self._analyze_depth_levels(bids[:20], asks[:20], levels=20)
            
            # 2. Bid/Ask 不对称率
            imbalance = self._calculate_imbalance(bids, asks)
            
            # 3. 大单墙检测
            bid_walls = self._detect_walls(bids, 'bid')
            ask_walls = self._detect_walls(asks, 'ask')
            
            # 4. 流动性分析
            liquidity = self._analyze_liquidity(bids, asks)
            
            # 5. 冲击成本估算
            impact_cost = self._estimate_impact_cost(bids, asks, trade_amount) if trade_amount > 0 else None
            
            # 6. 杠杆清算区域识别
            liquidation_zones = self._identify_liquidation_zones(bids, asks)
            
            # 7. 市场压力指标
            pressure = self._calculate_market_pressure(bids, asks)
            
            # 综合结果
            analysis = {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'depth_5_levels': depth_5,
                'depth_20_levels': depth_20,
                'bid_ask_imbalance': imbalance,
                'bid_walls': bid_walls,
                'ask_walls': ask_walls,
                'liquidity': liquidity,
                'impact_cost': impact_cost,
                'liquidation_zones': liquidation_zones,
                'market_pressure': pressure,
                'spread': {
                    'absolute': asks[0][0] - bids[0][0],
                    'relative': (asks[0][0] - bids[0][0]) / bids[0][0] * 100
                }
            }
            
            # 缓存历史
            self._cache_depth_data(analysis)
            
            return analysis
        
        except Exception as e:
            logger.error(f"订单簿分析失败 {symbol}: {e}")
            return {"error": str(e)}
    
    def _analyze_depth_levels(
        self,
        bids: List[List[float]],
        asks: List[List[float]],
        levels: int
    ) -> Dict[str, Any]:
        """分析N档深度"""
        bid_volume = sum(size for _, size in bids)
        ask_volume = sum(size for _, size in asks)
        bid_value = sum(price * size for price, size in bids)
        ask_value = sum(price * size for price, size in asks)
        
        return {
            'levels': levels,
            'bid_volume': bid_volume,
            'ask_volume': ask_volume,
            'bid_value': bid_value,
            'ask_value': ask_value,
            'volume_ratio': bid_volume / ask_volume if ask_volume > 0 else 0,
            'value_ratio': bid_value / ask_value if ask_value > 0 else 0
        }
    
    def _calculate_imbalance(
        self,
        bids: List[List[float]],
        asks: List[List[float]]
    ) -> Dict[str, Any]:
        """
        计算 Bid/Ask 不对称率
        
        不对称率 > 0: 买盘强
        不对称率 < 0: 卖盘强
        """
        # 计算前N档的总量
        levels = [5, 10, 20]
        imbalances = {}
        
        for n in levels:
            bid_vol = sum(size for _, size in bids[:n])
            ask_vol = sum(size for _, size in asks[:n])
            total_vol = bid_vol + ask_vol
            
            if total_vol > 0:
                imbalance_ratio = (bid_vol - ask_vol) / total_vol
                imbalances[f'{n}_levels'] = {
                    'ratio': imbalance_ratio,
                    'bid_volume': bid_vol,
                    'ask_volume': ask_vol,
                    'signal': 'BUY' if imbalance_ratio > 0.2 else ('SELL' if imbalance_ratio < -0.2 else 'NEUTRAL')
                }
        
        return imbalances
    
    def _detect_walls(
        self,
        orders: List[List[float]],
        side: str
    ) -> List[Dict[str, Any]]:
        """
        检测订单墙（大单聚集）
        
        Args:
            orders: 订单列表 [[price, size], ...]
            side: 'bid' 或 'ask'
        
        Returns:
            订单墙列表
        """
        if len(orders) < 5:
            return []
        
        # 计算平均订单量
        avg_size = np.mean([size for _, size in orders[:20]])
        
        walls = []
        for i, (price, size) in enumerate(orders[:20]):
            # 订单量超过平均值的N倍
            if size > avg_size * self.wall_detection_ratio:
                wall_value = price * size
                
                walls.append({
                    'level': i + 1,
                    'price': price,
                    'size': size,
                    'value': wall_value,
                    'ratio': size / avg_size,
                    'side': side,
                    'type': 'SUPPORT' if side == 'bid' else 'RESISTANCE'
                })
        
        return walls
    
    def _analyze_liquidity(
        self,
        bids: List[List[float]],
        asks: List[List[float]]
    ) -> Dict[str, Any]:
        """分析流动性"""
        # 计算不同价格范围内的流动性
        if not bids or not asks:
            return {}
        
        mid_price = (bids[0][0] + asks[0][0]) / 2
        
        # 计算±1%、±5%、±10%范围内的流动性
        ranges = [0.01, 0.05, 0.10]
        liquidity_by_range = {}
        
        for r in ranges:
            lower_bound = mid_price * (1 - r)
            upper_bound = mid_price * (1 + r)
            
            bid_liquidity = sum(size for price, size in bids if price >= lower_bound)
            ask_liquidity = sum(size for price, size in asks if price <= upper_bound)
            
            liquidity_by_range[f'{int(r*100)}pct'] = {
                'bid_liquidity': bid_liquidity,
                'ask_liquidity': ask_liquidity,
                'total_liquidity': bid_liquidity + ask_liquidity
            }
        
        return {
            'mid_price': mid_price,
            'by_range': liquidity_by_range,
            'total_bid_depth': sum(size for _, size in bids),
            'total_ask_depth': sum(size for _, size in asks)
        }
    
    def _estimate_impact_cost(
        self,
        bids: List[List[float]],
        asks: List[List[float]],
        trade_amount: float
    ) -> Dict[str, Any]:
        """
        估算冲击成本
        
        Args:
            bids: 买单列表
            asks: 卖单列表
            trade_amount: 交易金额
        
        Returns:
            冲击成本估算
        """
        mid_price = (bids[0][0] + asks[0][0]) / 2
        
        # 买入冲击成本（吃掉卖单）
        buy_impact = self._calculate_slippage(asks, trade_amount, 'buy')
        
        # 卖出冲击成本（吃掉买单）
        sell_impact = self._calculate_slippage(bids, trade_amount, 'sell')
        
        return {
            'trade_amount': trade_amount,
            'mid_price': mid_price,
            'buy_impact': buy_impact,
            'sell_impact': sell_impact,
            'avg_impact_bps': (buy_impact['impact_bps'] + sell_impact['impact_bps']) / 2
        }
    
    def _calculate_slippage(
        self,
        orders: List[List[float]],
        amount: float,
        side: str
    ) -> Dict[str, Any]:
        """计算滑点"""
        remaining = amount
        total_cost = 0
        filled_volume = 0
        
        for price, size in orders:
            if remaining <= 0:
                break
            
            order_value = price * size
            
            if order_value >= remaining:
                # 部分成交
                filled = remaining / price
                total_cost += remaining
                filled_volume += filled
                remaining = 0
            else:
                # 全部成交
                total_cost += order_value
                filled_volume += size
                remaining -= order_value
        
        if filled_volume == 0:
            return {
                'avg_price': 0,
                'slippage': 0,
                'impact_bps': 0,
                'filled': False
            }
        
        avg_price = total_cost / filled_volume
        initial_price = orders[0][0]
        slippage = avg_price - initial_price if side == 'buy' else initial_price - avg_price
        impact_bps = (slippage / initial_price) * 10000
        
        return {
            'avg_price': avg_price,
            'initial_price': initial_price,
            'slippage': slippage,
            'impact_bps': impact_bps,
            'filled': remaining == 0,
            'filled_volume': filled_volume
        }
    
    def _identify_liquidation_zones(
        self,
        bids: List[List[float]],
        asks: List[List[float]]
    ) -> Dict[str, Any]:
        """
        识别杠杆清算区域
        
        基于订单簿异常聚集识别可能的清算价位
        """
        if not bids or not asks:
            return {}
        
        mid_price = (bids[0][0] + asks[0][0]) / 2
        
        # 计算订单量的标准差
        all_sizes = [size for _, size in bids[:20]] + [size for _, size in asks[:20]]
        avg_size = np.mean(all_sizes)
        std_size = np.std(all_sizes)
        
        # 识别异常大的订单聚集（可能的清算墙）
        threshold = avg_size + 2 * std_size
        
        liquidation_levels = {
            'long_liquidations': [],  # 多头清算区（下方买单墙）
            'short_liquidations': []  # 空头清算区（上方卖单墙）
        }
        
        # 多头清算区（价格下跌触发）
        for price, size in bids:
            if size > threshold:
                distance_pct = (mid_price - price) / mid_price * 100
                liquidation_levels['long_liquidations'].append({
                    'price': price,
                    'size': size,
                    'distance_pct': distance_pct,
                    'leverage_estimate': 100 / distance_pct if distance_pct > 0 else 0
                })
        
        # 空头清算区（价格上涨触发）
        for price, size in asks:
            if size > threshold:
                distance_pct = (price - mid_price) / mid_price * 100
                liquidation_levels['short_liquidations'].append({
                    'price': price,
                    'size': size,
                    'distance_pct': distance_pct,
                    'leverage_estimate': 100 / distance_pct if distance_pct > 0 else 0
                })
        
        return liquidation_levels
    
    def _calculate_market_pressure(
        self,
        bids: List[List[float]],
        asks: List[List[float]]
    ) -> Dict[str, Any]:
        """
        计算市场压力指标
        
        综合买卖盘强度、深度、分布等因素
        """
        # 计算前20档的加权压力
        bid_pressure = sum(
            price * size * (21 - i) for i, (price, size) in enumerate(bids[:20], 1)
        )
        ask_pressure = sum(
            price * size * (21 - i) for i, (price, size) in enumerate(asks[:20], 1)
        )
        
        total_pressure = bid_pressure + ask_pressure
        
        if total_pressure == 0:
            return {}
        
        # 压力比率
        pressure_ratio = (bid_pressure - ask_pressure) / total_pressure
        
        # 压力信号
        if pressure_ratio > 0.3:
            signal = 'STRONG_BUY'
        elif pressure_ratio > 0.1:
            signal = 'BUY'
        elif pressure_ratio < -0.3:
            signal = 'STRONG_SELL'
        elif pressure_ratio < -0.1:
            signal = 'SELL'
        else:
            signal = 'NEUTRAL'
        
        return {
            'bid_pressure': bid_pressure,
            'ask_pressure': ask_pressure,
            'pressure_ratio': pressure_ratio,
            'signal': signal,
            'strength': abs(pressure_ratio)
        }
    
    def _cache_depth_data(self, analysis: Dict[str, Any]):
        """缓存深度数据用于趋势分析"""
        self.depth_history.append({
            'timestamp': analysis['timestamp'],
            'imbalance': analysis.get('bid_ask_imbalance', {}),
            'pressure': analysis.get('market_pressure', {})
        })
        
        # 限制历史长度
        if len(self.depth_history) > self.max_history:
            self.depth_history = self.depth_history[-self.max_history:]
    
    def detect_depth_anomalies(self, symbol: str) -> List[Dict[str, Any]]:
        """
        检测订单簿异常
        
        Returns:
            异常列表
        """
        if len(self.depth_history) < 10:
            return []
        
        anomalies = []
        
        # 检查不对称率的突变
        recent = self.depth_history[-10:]
        imbalance_5 = [d['imbalance'].get('5_levels', {}).get('ratio', 0) for d in recent]
        
        if len(imbalance_5) >= 2:
            current = imbalance_5[-1]
            avg_before = np.mean(imbalance_5[:-1])
            
            # 不对称率突变
            if abs(current - avg_before) > 0.3:
                anomalies.append({
                    'type': 'IMBALANCE_SHIFT',
                    'severity': 'HIGH' if abs(current - avg_before) > 0.5 else 'MEDIUM',
                    'direction': 'BUY' if current > avg_before else 'SELL',
                    'value': current,
                    'change': current - avg_before
                })
        
        return anomalies
    
    def get_trading_signal(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据深度分析生成交易信号
        
        Args:
            analysis: 深度分析结果
        
        Returns:
            交易信号
        """
        signals = []
        confidence_scores = []
        
        # 1. 不对称率信号
        imbalance_5 = analysis.get('bid_ask_imbalance', {}).get('5_levels', {})
        if imbalance_5:
            signal = imbalance_5.get('signal', 'NEUTRAL')
            ratio = imbalance_5.get('ratio', 0)
            
            if signal != 'NEUTRAL':
                signals.append(signal)
                confidence_scores.append(abs(ratio))
        
        # 2. 市场压力信号
        pressure = analysis.get('market_pressure', {})
        if pressure:
            signal = pressure.get('signal', 'NEUTRAL')
            strength = pressure.get('strength', 0)
            
            if 'BUY' in signal or 'SELL' in signal:
                signals.append('BUY' if 'BUY' in signal else 'SELL')
                confidence_scores.append(strength)
        
        # 3. 订单墙信号
        bid_walls = analysis.get('bid_walls', [])
        ask_walls = analysis.get('ask_walls', [])
        
        if bid_walls and not ask_walls:
            signals.append('BUY')
            confidence_scores.append(0.6)
        elif ask_walls and not bid_walls:
            signals.append('SELL')
            confidence_scores.append(0.6)
        
        # 综合信号
        if not signals:
            return {'action': 'HOLD', 'confidence': 0, 'reasons': []}
        
        # 统计信号方向
        buy_count = signals.count('BUY')
        sell_count = signals.count('SELL')
        
        if buy_count > sell_count:
            action = 'BUY'
            confidence = np.mean(confidence_scores)
        elif sell_count > buy_count:
            action = 'SELL'
            confidence = np.mean(confidence_scores)
        else:
            action = 'HOLD'
            confidence = 0
        
        return {
            'action': action,
            'confidence': confidence,
            'signals_count': len(signals),
            'buy_signals': buy_count,
            'sell_signals': sell_count,
            'reasons': self._generate_signal_reasons(analysis)
        }
    
    def _generate_signal_reasons(self, analysis: Dict[str, Any]) -> List[str]:
        """生成信号原因"""
        reasons = []
        
        # 不对称率
        imbalance = analysis.get('bid_ask_imbalance', {}).get('5_levels', {})
        if imbalance and imbalance.get('signal') != 'NEUTRAL':
            ratio = imbalance.get('ratio', 0)
            reasons.append(f"5档不对称率: {ratio:+.2%} ({'买盘强' if ratio > 0 else '卖盘强'})")
        
        # 订单墙
        bid_walls = analysis.get('bid_walls', [])
        ask_walls = analysis.get('ask_walls', [])
        
        if bid_walls:
            reasons.append(f"检测到 {len(bid_walls)} 个买单墙（支撑）")
        if ask_walls:
            reasons.append(f"检测到 {len(ask_walls)} 个卖单墙（阻力）")
        
        # 市场压力
        pressure = analysis.get('market_pressure', {})
        if pressure:
            signal = pressure.get('signal', '')
            if 'STRONG' in signal:
                reasons.append(f"市场压力: {signal}")
        
        return reasons


if __name__ == '__main__':
    # 测试
    analyzer = MarketDepthAnalyzer()
    
    # 模拟订单簿数据
    test_orderbook = {
        'bids': [
            [50000, 1.5],
            [49900, 2.0],
            [49800, 1.2],
            [49700, 5.0],  # 大单墙
            [49600, 1.8],
        ],
        'asks': [
            [50100, 1.3],
            [50200, 1.9],
            [50300, 1.5],
            [50400, 1.7],
            [50500, 2.1],
        ]
    }
    
    analysis = analyzer.analyze_orderbook('BTC-USDT', test_orderbook, trade_amount=100000)
    
    print("\n=== 订单簿分析结果 ===")
    print(f"5档不对称率: {analysis['bid_ask_imbalance']['5_levels']['ratio']:.2%}")
    print(f"买单墙: {len(analysis['bid_walls'])}个")
    print(f"卖单墙: {len(analysis['ask_walls'])}个")
    print(f"市场压力: {analysis['market_pressure']['signal']}")
    
    signal = analyzer.get_trading_signal(analysis)
    print(f"\n交易信号: {signal['action']} (置信度: {signal['confidence']:.2%})")
    print(f"原因: {', '.join(signal['reasons'])}")
