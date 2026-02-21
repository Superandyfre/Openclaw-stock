"""
智能信号聚合系统

整合多个监控模块的信号，生成综合交易建议：
- 市场深度分析 (MarketDepthAnalyzer)
- 高级技术指标 (AdvancedIndicatorMonitor)
- 衍生品数据 (DerivativesDataMonitor)
- 市场情绪 (MarketSentimentAnalyzer)
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import numpy as np
from loguru import logger


class SmartSignalAggregator:
    """
    智能信号聚合器
    
    融合多个监控器的信号，使用加权投票和贝叶斯方法生成最终交易建议
    """
    
    def __init__(self, custom_weights: Optional[Dict[str, float]] = None):
        """
        初始化聚合器
        
        Args:
            custom_weights: 自定义权重 {
                'market_depth': 0.20,
                'technical': 0.30,
                'derivatives': 0.30,
                'sentiment': 0.20
            }
        """
        # 默认权重配置
        self.weights = custom_weights or {
            'market_depth': 0.20,  # 订单簿深度
            'technical': 0.30,      # 技术指标
            'derivatives': 0.30,    # 衍生品数据
            'sentiment': 0.20       # 市场情绪
        }
        
        # 信号历史
        self.signal_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # 最低置信度阈值
        self.min_confidence_threshold = 0.5
        
        logger.info(f"✅ SmartSignalAggregator 初始化成功，权重: {self.weights}")
    
    def aggregate_signals(
        self,
        symbol: str,
        market_depth: Optional[Dict[str, Any]] = None,
        technical: Optional[Dict[str, Any]] = None,
        derivatives: Optional[Dict[str, Any]] = None,
        sentiment: Optional[Dict[str, Any]] = None,
        current_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        聚合所有信号源
        
        Args:
            symbol: 交易对
            market_depth: 市场深度分析结果（来自MarketDepthAnalyzer）
            technical: 技术指标分析结果（来自AdvancedIndicatorMonitor）
            derivatives: 衍生品分析结果（来自DerivativesDataMonitor）
            sentiment: 市场情绪分析结果（来自MarketSentimentAnalyzer）
            current_price: 当前价格
        
        Returns:
            综合交易建议
        """
        # 提取各模块信号
        signals = {}
        confidences = {}
        
        # 1. 市场深度信号
        if market_depth:
            depth_signal = self._extract_depth_signal(market_depth)
            if depth_signal:
                signals['market_depth'] = depth_signal
                confidences['market_depth'] = self._calculate_depth_confidence(market_depth)
        
        # 2. 技术指标信号
        if technical:
            tech_signal = self._extract_technical_signal(technical)
            if tech_signal:
                signals['technical'] = tech_signal
                confidences['technical'] = technical.get('signals', {}).get('confidence', 0.5)
        
        # 3. 衍生品信号
        if derivatives:
            deriv_signal = self._extract_derivatives_signal(derivatives)
            if deriv_signal:
                signals['derivatives'] = deriv_signal
                confidences['derivatives'] = self._calculate_derivatives_confidence(derivatives)
        
        # 4. 情绪信号
        if sentiment:
            sent_signal = self._extract_sentiment_signal(sentiment)
            if sent_signal:
                signals['sentiment'] = sent_signal
                confidences['sentiment'] = sentiment.get('confidence', 0.5)
        
        # 聚合信号
        aggregated = self._combine_signals(signals, confidences)
        
        # 生成交易建议
        recommendation = self._generate_recommendation(
            symbol, 
            aggregated, 
            current_price,
            signals,
            confidences
        )
        
        # 记录历史
        if symbol not in self.signal_history:
            self.signal_history[symbol] = []
        
        self.signal_history[symbol].append({
            'timestamp': datetime.now().isoformat(),
            'action': recommendation['action'],
            'confidence': recommendation['confidence']
        })
        
        return recommendation
    
    def _extract_depth_signal(self, market_depth: Dict[str, Any]) -> Optional[str]:
        """提取市场深度信号"""
        # 从market_pressure获取信号
        pressure = market_depth.get('market_pressure', {})
        signal = pressure.get('signal', '')
        
        if 'BUY' in signal:
            return 'BUY'
        elif 'SELL' in signal:
            return 'SELL'
        else:
            return 'NEUTRAL'
    
    def _calculate_depth_confidence(self, market_depth: Dict[str, Any]) -> float:
        """计算深度信号置信度"""
        pressure = market_depth.get('market_pressure', {})
        strength = pressure.get('strength', 'WEAK')
        
        strength_map = {
            'STRONG': 0.85,
            'MODERATE': 0.65,
            'WEAK': 0.45
        }
        
        return strength_map.get(strength, 0.5)
    
    def _extract_technical_signal(self, technical: Dict[str, Any]) -> Optional[str]:
        """提取技术指标信号"""
        signals = technical.get('signals', {})
        action = signals.get('action', 'NEUTRAL')
        
        return action
    
    def _extract_derivatives_signal(self, derivatives: Dict[str, Any]) -> Optional[str]:
        """提取衍生品信号"""
        # 综合资金费率、未平仓量、多空比
        signals = []
        
        if 'funding_rate' in derivatives:
            fr_signal = derivatives['funding_rate'].get('signal', '')
            if fr_signal:
                signals.append(fr_signal)
        
        if 'open_interest' in derivatives:
            oi_signal = derivatives['open_interest'].get('signal', '')
            if oi_signal:
                signals.append(oi_signal)
        
        if 'long_short_ratio' in derivatives:
            ls_signal = derivatives['long_short_ratio'].get('signal', '')
            if ls_signal:
                signals.append(ls_signal)
        
        # 投票
        if not signals:
            return 'NEUTRAL'
        
        buy_votes = sum(1 for s in signals if 'BUY' in s)
        sell_votes = sum(1 for s in signals if 'SELL' in s)
        
        if buy_votes > sell_votes:
            return 'BUY'
        elif sell_votes > buy_votes:
            return 'SELL'
        else:
            return 'NEUTRAL'
    
    def _calculate_derivatives_confidence(self, derivatives: Dict[str, Any]) -> float:
        """计算衍生品信号置信度"""
        # 基于多个指标的一致性
        signals = []
        
        if 'funding_rate' in derivatives:
            signals.append(derivatives['funding_rate'].get('signal', ''))
        
        if 'open_interest' in derivatives:
            signals.append(derivatives['open_interest'].get('signal', ''))
        
        if 'long_short_ratio' in derivatives:
            signals.append(derivatives['long_short_ratio'].get('signal', ''))
        
        if not signals:
            return 0.5
        
        # 一致性越高，置信度越高
        buy_count = sum(1 for s in signals if 'BUY' in s)
        sell_count = sum(1 for s in signals if 'SELL' in s)
        
        max_count = max(buy_count, sell_count)
        consistency = max_count / len(signals)
        
        # 转换为置信度（50%-90%）
        confidence = 0.5 + (consistency * 0.4)
        
        return confidence
    
    def _extract_sentiment_signal(self, sentiment: Dict[str, Any]) -> Optional[str]:
        """提取情绪信号"""
        overall_signal = sentiment.get('overall_signal', 'NEUTRAL')
        
        if overall_signal == 'BULLISH':
            return 'BUY'
        elif overall_signal == 'BEARISH':
            return 'SELL'
        else:
            return 'NEUTRAL'
    
    def _combine_signals(
        self,
        signals: Dict[str, str],
        confidences: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        组合多个信号
        
        使用加权投票法
        """
        if not signals:
            return {
                'action': 'NEUTRAL',
                'confidence': 0,
                'vote_breakdown': {}
            }
        
        # 计算加权投票
        buy_weight = 0
        sell_weight = 0
        neutral_weight = 0
        
        vote_breakdown = {}
        
        for source, signal in signals.items():
            weight = self.weights.get(source, 0)
            confidence = confidences.get(source, 0.5)
            
            # 有效权重 = 配置权重 × 置信度
            effective_weight = weight * confidence
            
            vote_breakdown[source] = {
                'signal': signal,
                'weight': weight,
                'confidence': confidence,
                'effective_weight': effective_weight
            }
            
            if signal == 'BUY':
                buy_weight += effective_weight
            elif signal == 'SELL':
                sell_weight += effective_weight
            else:
                neutral_weight += effective_weight
        
        # 确定最终信号
        total_weight = buy_weight + sell_weight + neutral_weight
        
        if total_weight == 0:
            return {
                'action': 'NEUTRAL',
                'confidence': 0,
                'vote_breakdown': vote_breakdown
            }
        
        # 归一化
        buy_pct = buy_weight / total_weight
        sell_pct = sell_weight / total_weight
        neutral_pct = neutral_weight / total_weight
        
        # 确定行动
        if buy_pct > sell_pct and buy_pct > neutral_pct:
            action = 'BUY'
            confidence = buy_pct
        elif sell_pct > buy_pct and sell_pct > neutral_pct:
            action = 'SELL'
            confidence = sell_pct
        else:
            action = 'NEUTRAL'
            confidence = neutral_pct
        
        return {
            'action': action,
            'confidence': confidence,
            'vote_breakdown': vote_breakdown,
            'vote_percentages': {
                'buy': buy_pct,
                'sell': sell_pct,
                'neutral': neutral_pct
            }
        }
    
    def _generate_recommendation(
        self,
        symbol: str,
        aggregated: Dict[str, Any],
        current_price: Optional[float],
        signals: Dict[str, str],
        confidences: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        生成最终交易建议
        """
        action = aggregated['action']
        confidence = aggregated['confidence']
        
        # 置信度检查
        should_execute = confidence >= self.min_confidence_threshold
        
        # 生成建议文本
        recommendation_text = self._create_recommendation_text(
            action, 
            confidence, 
            aggregated.get('vote_breakdown', {})
        )
        
        # 风险评估
        risk_level = self._assess_risk(action, confidence, signals)
        
        # 建议仓位大小（基于置信度）
        if action == 'BUY' or action == 'SELL':
            if confidence >= 0.8:
                position_size = 'LARGE'  # 大仓位（如30-50%）
            elif confidence >= 0.65:
                position_size = 'MEDIUM'  # 中等仓位（如15-30%）
            else:
                position_size = 'SMALL'  # 小仓位（如5-15%）
        else:
            position_size = 'NONE'
        
        # 止损止盈建议
        stop_loss_pct = None
        take_profit_pct = None
        
        if current_price and action in ['BUY', 'SELL']:
            if action == 'BUY':
                stop_loss_pct = -10  # 默认-10%止损
                take_profit_pct = 20  # 默认+20%止盈
            else:  # SELL
                stop_loss_pct = 10   # 做空止损+10%
                take_profit_pct = -20  # 做空止盈-20%
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'confidence': confidence,
            'should_execute': should_execute,
            'position_size': position_size,
            'risk_level': risk_level,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'current_price': current_price,
            'recommendation_text': recommendation_text,
            'signal_breakdown': {
                'sources': signals,
                'confidences': confidences,
                'vote_percentages': aggregated.get('vote_percentages', {}),
                'vote_breakdown': aggregated.get('vote_breakdown', {})
            }
        }
    
    def _create_recommendation_text(
        self,
        action: str,
        confidence: float,
        vote_breakdown: Dict[str, Any]
    ) -> str:
        """生成建议文本"""
        if action == 'BUY':
            base = f"建议买入，综合置信度 {confidence:.1%}"
        elif action == 'SELL':
            base = f"建议卖出，综合置信度 {confidence:.1%}"
        else:
            base = f"建议观望，信号不明确"
        
        # 添加支持的信号源
        supporting = [
            source for source, data in vote_breakdown.items()
            if data.get('signal') == action
        ]
        
        if supporting:
            sources_text = '、'.join(supporting)
            base += f"。支持信号来自：{sources_text}"
        
        return base
    
    def _assess_risk(
        self,
        action: str,
        confidence: float,
        signals: Dict[str, str]
    ) -> str:
        """评估风险等级"""
        # 信号一致性
        if action == 'NEUTRAL':
            return 'MEDIUM'
        
        matching_signals = sum(1 for s in signals.values() if s == action)
        total_signals = len(signals)
        
        consistency = matching_signals / total_signals if total_signals > 0 else 0
        
        # 综合评估
        if confidence >= 0.75 and consistency >= 0.75:
            return 'LOW'  # 低风险
        elif confidence >= 0.5 and consistency >= 0.5:
            return 'MEDIUM'  # 中等风险
        else:
            return 'HIGH'  # 高风险
    
    def get_signal_history(
        self,
        symbol: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取信号历史"""
        history = self.signal_history.get(symbol, [])
        return history[-limit:]
    
    def get_summary_report(self, recommendation: Dict[str, Any]) -> str:
        """生成摘要报告"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"交易建议报告 - {recommendation['symbol']}")
        lines.append("=" * 60)
        lines.append(f"时间: {recommendation['timestamp']}")
        lines.append(f"当前价格: {recommendation.get('current_price', 'N/A')}")
        lines.append("")
        lines.append(f"【建议行动】{recommendation['action']}")
        lines.append(f"【置信度】{recommendation['confidence']:.1%}")
        lines.append(f"【是否执行】{'是' if recommendation['should_execute'] else '否'}")
        lines.append(f"【仓位大小】{recommendation['position_size']}")
        lines.append(f"【风险等级】{recommendation['risk_level']}")
        lines.append("")
        
        if recommendation.get('stop_loss_pct'):
            lines.append(f"【止损】{recommendation['stop_loss_pct']:+.1f}%")
            lines.append(f"【止盈】{recommendation['take_profit_pct']:+.1f}%")
            lines.append("")
        
        lines.append("【信号投票分布】")
        vote_pct = recommendation['signal_breakdown'].get('vote_percentages', {})
        lines.append(f"  看涨: {vote_pct.get('buy', 0):.1%}")
        lines.append(f"  看跌: {vote_pct.get('sell', 0):.1%}")
        lines.append(f"  中性: {vote_pct.get('neutral', 0):.1%}")
        lines.append("")
        
        lines.append("【各模块信号】")
        for source, signal in recommendation['signal_breakdown']['sources'].items():
            conf = recommendation['signal_breakdown']['confidences'].get(source, 0)
            lines.append(f"  {source}: {signal} (置信度: {conf:.1%})")
        lines.append("")
        
        lines.append(f"【建议说明】{recommendation['recommendation_text']}")
        lines.append("=" * 60)
        
        return "\n".join(lines)


if __name__ == '__main__':
    # 测试
    aggregator = SmartSignalAggregator()
    
    # 模拟各模块输出
    market_depth_result = {
        'market_pressure': {
            'signal': 'BUY',
            'strength': 'STRONG'
        }
    }
    
    technical_result = {
        'signals': {
            'action': 'BUY',
            'confidence': 0.75
        }
    }
    
    derivatives_result = {
        'funding_rate': {'signal': 'CAUTION_SELL'},
        'open_interest': {'signal': 'BULLISH'},
        'long_short_ratio': {'signal': 'NEUTRAL'}
    }
    
    sentiment_result = {
        'overall_signal': 'BULLISH',
        'confidence': 0.65
    }
    
    # 聚合信号
    recommendation = aggregator.aggregate_signals(
        symbol='BTC-USDT',
        market_depth=market_depth_result,
        technical=technical_result,
        derivatives=derivatives_result,
        sentiment=sentiment_result,
        current_price=50000
    )
    
    # 打印报告
    print(aggregator.get_summary_report(recommendation))
