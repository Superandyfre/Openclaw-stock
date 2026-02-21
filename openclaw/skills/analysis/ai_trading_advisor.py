#!/usr/bin/env python3
"""
AI Trading Advisor - 智能交易建议系统
整合技术分析、情绪分析和LLM深度分析，生成交易建议
"""
import os
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

# Google AI (使用模型管理器)
try:
    from openclaw.skills.analysis.gemini_model_manager import GeminiModelManager
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Gemini模型管理器未安装，LLM分析功能不可用")


class AITradingAdvisor:
    """AI驱动的交易建议系统"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化AI交易顾问
        
        Args:
            api_key: Google AI API密钥
        """
        self.api_key = api_key or os.getenv('GOOGLE_AI_API_KEY')
        self.advice_history: List[Dict[str, Any]] = []
        
        # 初始化Gemini模型管理器
        if GEMINI_AVAILABLE and self.api_key:
            try:
                self.model_manager = GeminiModelManager(
                    api_key=self.api_key,
                    default_task_type='standard'  # 日常分析使用标准模型
                )
                logger.info("✅ AI Trading Advisor 初始化成功 (Gemini Model Manager)")
            except Exception as e:
                logger.error(f"初始化Gemini模型管理器失败: {e}")
                self.model_manager = None
        else:
            self.model_manager = None
            logger.warning("⚠️ AI Trading Advisor 运行在基础模式（无LLM）")
    
    async def generate_trading_advice(
        self,
        symbol: str,
        name: str,
        current_price: float,
        price_data: Dict[str, Any],
        technical_indicators: Dict[str, Any],
        sentiment: Dict[str, Any],
        news: List[Dict[str, Any]] = None,
        strategy_signals: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成综合交易建议
        
        Args:
            symbol: 股票代码
            name: 股票名称
            current_price: 当前价格
            price_data: 价格数据
            technical_indicators: 技术指标
            sentiment: 情绪分析结果
            news: 相关新闻
            strategy_signals: 策略信号
        
        Returns:
            交易建议
        """
        # 1. 基础分析（无需LLM）
        basic_analysis = self._basic_analysis(
            symbol, current_price, price_data, technical_indicators, sentiment
        )
        
        # 2. 信号聚合
        aggregated_signals = self._aggregate_signals(strategy_signals or [])
        
        # 3. 如果有LLM，进行深度分析
        if self.model_manager and news:
            llm_analysis = await self._llm_deep_analysis(
                symbol, name, current_price, price_data,
                technical_indicators, sentiment, news,
                basic_analysis, aggregated_signals
            )
        else:
            llm_analysis = None
        
        # 4. 生成最终建议
        advice = self._generate_final_advice(
            symbol, name, current_price,
            basic_analysis, aggregated_signals, llm_analysis
        )
        
        # 记录历史
        self.advice_history.append({
            'timestamp': datetime.now(),
            'symbol': symbol,
            'advice': advice
        })
        
        return advice
    
    def _basic_analysis(
        self,
        symbol: str,
        current_price: float,
        price_data: Dict[str, Any],
        technical_indicators: Dict[str, Any],
        sentiment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """基础技术分析"""
        analysis = {
            'trend': 'neutral',
            'momentum': 'neutral',
            'volatility': 'normal',
            'strength_score': 5.0  # 0-10
        }
        
        # 趋势判断
        change_pct = price_data.get('change_pct', 0)
        if change_pct > 2:
            analysis['trend'] = 'strong_bullish'
            analysis['strength_score'] += 2
        elif change_pct > 0.5:
            analysis['trend'] = 'bullish'
            analysis['strength_score'] += 1
        elif change_pct < -2:
            analysis['trend'] = 'strong_bearish'
            analysis['strength_score'] -= 2
        elif change_pct < -0.5:
            analysis['trend'] = 'bearish'
            analysis['strength_score'] -= 1
        
        # RSI分析
        rsi = technical_indicators.get('rsi', 50)
        if rsi > 70:
            analysis['momentum'] = 'overbought'
            analysis['strength_score'] -= 1
        elif rsi < 30:
            analysis['momentum'] = 'oversold'
            analysis['strength_score'] += 1.5  # 超卖反弹机会
        elif rsi > 60:
            analysis['momentum'] = 'bullish'
            analysis['strength_score'] += 0.5
        elif rsi < 40:
            analysis['momentum'] = 'bearish'
            analysis['strength_score'] -= 0.5
        
        # 波动性
        volume_ratio = price_data.get('volume_ratio', 1.0)
        if volume_ratio > 2.5:
            analysis['volatility'] = 'high'
            analysis['strength_score'] += 0.5  # 高成交量确认
        elif volume_ratio < 0.5:
            analysis['volatility'] = 'low'
            analysis['strength_score'] -= 0.5  # 低成交量警告
        
        # 情绪加权
        sentiment_score = sentiment.get('score', 0)
        if sentiment_score > 0.5:
            analysis['strength_score'] += 1
        elif sentiment_score < -0.5:
            analysis['strength_score'] -= 1
        
        # 限制分数范围
        analysis['strength_score'] = max(0, min(10, analysis['strength_score']))
        
        return analysis
    
    def _aggregate_signals(self, strategy_signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """聚合多个策略信号"""
        if not strategy_signals:
            return {
                'action': 'HOLD',
                'confidence': 0.0,
                'signal_count': 0,
                'buy_signals': 0,
                'sell_signals': 0
            }
        
        buy_count = sum(1 for s in strategy_signals if s.get('action') == 'BUY')
        sell_count = sum(1 for s in strategy_signals if s.get('action') == 'SELL')
        
        total_signals = len(strategy_signals)
        buy_weight = sum(s.get('weight', 1.0) for s in strategy_signals if s.get('action') == 'BUY')
        sell_weight = sum(s.get('weight', 1.0) for s in strategy_signals if s.get('action') == 'SELL')
        
        # 决定行动
        if buy_count > sell_count and buy_weight > sell_weight:
            action = 'BUY'
            confidence = buy_count / total_signals
        elif sell_count > buy_count and sell_weight > buy_weight:
            action = 'SELL'
            confidence = sell_count / total_signals
        else:
            action = 'HOLD'
            confidence = 0.5
        
        return {
            'action': action,
            'confidence': confidence,
            'signal_count': total_signals,
            'buy_signals': buy_count,
            'sell_signals': sell_count,
            'buy_weight': buy_weight,
            'sell_weight': sell_weight
        }
    
    async def _llm_deep_analysis(
        self,
        symbol: str,
        name: str,
        current_price: float,
        price_data: Dict[str, Any],
        technical_indicators: Dict[str, Any],
        sentiment: Dict[str, Any],
        news: List[Dict[str, Any]],
        basic_analysis: Dict[str, Any],
        aggregated_signals: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用LLM进行深度分析"""
        try:
            # 使用标准模型进行交易分析 (gemini-2.5-flash)
            model = self.model_manager.get_model('standard')
            if not model:
                return {'available': False, 'error': '模型未加载'}
            
            # 构建提示词
            prompt = self._build_analysis_prompt(
                symbol, name, current_price, price_data,
                technical_indicators, sentiment, news,
                basic_analysis, aggregated_signals
            )
            
            # 调用LLM
            response = await asyncio.to_thread(
                model.generate_content,
                prompt
            )
            
            # 解析响应
            ai_text = response.text
            
            return {
                'available': True,
                'analysis': ai_text,
                'recommendation': self._extract_recommendation(ai_text),
                'confidence': self._extract_confidence(ai_text),
                'key_points': self._extract_key_points(ai_text)
            }
            
        except Exception as e:
            logger.error(f"LLM分析失败: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    def _build_analysis_prompt(
        self,
        symbol: str,
        name: str,
        current_price: float,
        price_data: Dict[str, Any],
        technical_indicators: Dict[str, Any],
        sentiment: Dict[str, Any],
        news: List[Dict[str, Any]],
        basic_analysis: Dict[str, Any],
        aggregated_signals: Dict[str, Any]
    ) -> str:
        """构建LLM分析提示词"""
        
        # 新闻摘要
        news_summary = "\n".join([
            f"- {article.get('title', 'N/A')}" 
            for article in news[:5]  # 最多5条
        ]) if news else "无相关新闻"
        
        prompt = f"""你是一位资深的短线交易分析师。请基于以下信息，为 {name} ({symbol}) 提供10小时内的短线交易建议。

【🔥 短线交易策略 - 最高优先级】
- 交易时间窗口：买入到卖出不超过10小时
- 重点关注：盘中波动、短期技术面、即时成交量变化
- 目标：快速获利，日内或隔夜持仓，严格止损

【💰 严格风控要求 - 强制执行】
- 收益目标：必须有20%以上的收益预期，否则不推荐买入
- 止损红线：亏损绝对不能超过-10%，建议-8%止损
- 如果无法达到20%收益预期，请明确说明并建议HOLD或等待更好时机

【当前价格】
价格: ₩{current_price:,}
涨跌: {price_data.get('change_pct', 0):+.2f}%
成交量比率: {price_data.get('volume_ratio', 1.0):.2f}x

【技术指标】
RSI: {technical_indicators.get('rsi', 50):.2f}
MACD: {technical_indicators.get('macd', {}).get('macd', 0):.2f}
趋势: {basic_analysis.get('trend', 'neutral')}
动量: {basic_analysis.get('momentum', 'neutral')}

【情绪分析】
整体情绪: {sentiment.get('overall_sentiment', 'neutral')}
情绪得分: {sentiment.get('score', 0):.2f}
新闻数量: {sentiment.get('article_count', 0)}

【策略信号】
推荐动作: {aggregated_signals.get('action', 'HOLD')}
信号置信度: {aggregated_signals.get('confidence', 0):.1%}
买入信号: {aggregated_signals.get('buy_signals', 0)}
卖出信号: {aggregated_signals.get('sell_signals', 0)}

【相关新闻】
{news_summary}

请提供短线交易建议（10小时内）：
1. 交易建议: BUY / SELL / HOLD（必须明确）
2. 置信度: 1-10分（数字）
3. 买入时机: 具体的入场价位和时间点
4. 卖出目标: 10小时内的目标价位和预期收益
5. 止损位: 严格的止损价格
6. 关键理由: 2-3个短线交易要点
7. 风险提示: 短线操作的主要风险

请用简洁、专业的中文回答，聚焦10小时内的短线机会。"""
        
        return prompt
    
    def _extract_recommendation(self, ai_text: str) -> str:
        """从AI响应中提取推荐动作"""
        ai_upper = ai_text.upper()
        
        # 优先级: SELL > BUY > HOLD
        if 'SELL' in ai_upper or '卖出' in ai_text or '做空' in ai_text:
            return 'SELL'
        elif 'BUY' in ai_upper or '买入' in ai_text or '做多' in ai_text:
            return 'BUY'
        else:
            return 'HOLD'
    
    def _extract_confidence(self, ai_text: str) -> float:
        """从AI响应中提取置信度分数"""
        import re
        
        # 寻找1-10的数字评分
        patterns = [
            r'置信度[:：]\s*(\d+)',
            r'信心[:：]\s*(\d+)',
            r'评分[:：]\s*(\d+)',
            r'(\d+)\s*分',
            r'(\d+)/10'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, ai_text)
            if match:
                score = int(match.group(1))
                return min(10, max(1, score)) / 10.0
        
        return 0.5  # 默认中等置信度
    
    def _extract_key_points(self, ai_text: str) -> List[str]:
        """从AI响应中提取关键要点"""
        import re
        
        key_points = []
        
        # 寻找列表项
        patterns = [
            r'[•\-\*]\s+(.+)',
            r'\d+[\.\)]\s+(.+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, ai_text)
            if matches:
                key_points.extend(matches[:5])  # 最多5个要点
                break
        
        # 如果没有找到列表，尝试按句子分割
        if not key_points:
            sentences = [s.strip() for s in ai_text.split('。') if s.strip()]
            key_points = sentences[:3]
        
        return key_points
    
    def _generate_final_advice(
        self,
        symbol: str,
        name: str,
        current_price: float,
        basic_analysis: Dict[str, Any],
        aggregated_signals: Dict[str, Any],
        llm_analysis: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成最终交易建议"""
        
        # 如果有LLM分析，优先使用
        if llm_analysis and llm_analysis.get('available'):
            action = llm_analysis.get('recommendation', 'HOLD')
            confidence = llm_analysis.get('confidence', 0.5)
            reasoning = llm_analysis.get('analysis', '')
            key_points = llm_analysis.get('key_points', [])
            source = 'AI (Gemini)'
        else:
            # 否则使用聚合信号
            action = aggregated_signals.get('action', 'HOLD')
            confidence = aggregated_signals.get('confidence', 0.5)
            reasoning = self._generate_basic_reasoning(basic_analysis, aggregated_signals)
            key_points = self._generate_basic_key_points(basic_analysis, aggregated_signals)
            source = 'Technical Analysis'
        
        # 计算目标价位
        targets = self._calculate_targets(action, current_price, basic_analysis)
        
        return {
            'symbol': symbol,
            'name': name,
            'timestamp': datetime.now().isoformat(),
            'current_price': current_price,
            'action': action,
            'confidence': confidence,
            'confidence_level': self._get_confidence_level(confidence),
            'reasoning': reasoning,
            'key_points': key_points,
            'targets': targets,
            'basic_analysis': basic_analysis,
            'source': source,
            'strength_score': basic_analysis.get('strength_score', 5.0)
        }
    
    def _generate_basic_reasoning(
        self,
        basic_analysis: Dict[str, Any],
        aggregated_signals: Dict[str, Any]
    ) -> str:
        """生成基础推理说明"""
        trend = basic_analysis.get('trend', 'neutral')
        momentum = basic_analysis.get('momentum', 'neutral')
        signal_count = aggregated_signals.get('signal_count', 0)
        action = aggregated_signals.get('action', 'HOLD')
        
        reasoning = f"基于技术分析，当前趋势为{trend}，动量为{momentum}。"
        
        if signal_count > 0:
            buy_count = aggregated_signals.get('buy_signals', 0)
            sell_count = aggregated_signals.get('sell_signals', 0)
            reasoning += f" {signal_count}个策略中，{buy_count}个买入信号，{sell_count}个卖出信号。"
        
        reasoning += f" 综合建议: {action}。"
        
        return reasoning
    
    def _generate_basic_key_points(
        self,
        basic_analysis: Dict[str, Any],
        aggregated_signals: Dict[str, Any]
    ) -> List[str]:
        """生成基础关键要点"""
        points = []
        
        trend = basic_analysis.get('trend', 'neutral')
        if 'bullish' in trend:
            points.append(f"📈 价格趋势：{trend}")
        elif 'bearish' in trend:
            points.append(f"📉 价格趋势：{trend}")
        
        momentum = basic_analysis.get('momentum', 'neutral')
        if momentum in ['overbought', 'oversold']:
            points.append(f"⚡ 动量状态：{momentum}")
        
        volatility = basic_analysis.get('volatility', 'normal')
        if volatility != 'normal':
            points.append(f"📊 波动性：{volatility}")
        
        strength = basic_analysis.get('strength_score', 5.0)
        points.append(f"💪 综合强度：{strength:.1f}/10")
        
        return points
    
    def _calculate_targets(
        self,
        action: str,
        current_price: float,
        basic_analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """计算目标价位"""
        targets = {}
        
        if action == 'BUY':
            # 买入目标
            targets['entry'] = current_price
            targets['take_profit_1'] = current_price * 1.02  # +2%
            targets['take_profit_2'] = current_price * 1.05  # +5%
            targets['stop_loss'] = current_price * 0.98  # -2%
            
        elif action == 'SELL':
            # 卖出目标
            targets['entry'] = current_price
            targets['take_profit'] = current_price * 0.95  # -5%
            targets['stop_loss'] = current_price * 1.02  # +2%
        
        return targets
    
    def _get_confidence_level(self, confidence: float) -> str:
        """将置信度转换为等级"""
        if confidence >= 0.8:
            return '极高 (⭐⭐⭐⭐⭐)'
        elif confidence >= 0.6:
            return '高 (⭐⭐⭐⭐)'
        elif confidence >= 0.4:
            return '中等 (⭐⭐⭐)'
        elif confidence >= 0.2:
            return '低 (⭐⭐)'
        else:
            return '极低 (⭐)'
    
    def format_advice_for_telegram(self, advice: Dict[str, Any]) -> str:
        """格式化建议为Telegram消息"""
        symbol = advice['symbol']
        name = advice['name']
        action = advice['action']
        confidence = advice['confidence']
        confidence_level = advice['confidence_level']
        current_price = advice['current_price']
        targets = advice.get('targets', {})
        key_points = advice.get('key_points', [])
        strength = advice.get('strength_score', 5.0)
        source = advice.get('source', 'Analysis')
        
        # 表情符号
        action_emoji = {
            'BUY': '🟢 买入',
            'SELL': '🔴 卖出',
            'HOLD': '🟡 观望'
        }
        
        message = f"""
🤖 **AI 交易建议**

📊 **{name}** ({symbol})
💰 当前价格: ₩{current_price:,}

🎯 **建议**: {action_emoji.get(action, action)}
⭐ **置信度**: {confidence_level} ({confidence:.0%})
💪 **强度评分**: {strength:.1f}/10
🔍 **分析来源**: {source}
"""
        
        # 目标价位
        if targets:
            message += "\n📈 **目标价位**:\n"
            if 'entry' in targets:
                message += f"  入场: ₩{targets['entry']:,.0f}\n"
            if 'take_profit_1' in targets:
                message += f"  止盈1: ₩{targets['take_profit_1']:,.0f} (+2%)\n"
            if 'take_profit_2' in targets:
                message += f"  止盈2: ₩{targets['take_profit_2']:,.0f} (+5%)\n"
            if 'take_profit' in targets:
                message += f"  目标: ₩{targets['take_profit']:,.0f}\n"
            if 'stop_loss' in targets:
                message += f"  止损: ₩{targets['stop_loss']:,.0f}\n"
        
        # 关键要点
        if key_points:
            message += "\n💡 **关键要点**:\n"
            for i, point in enumerate(key_points[:5], 1):
                # 清理要点文本
                point_clean = point.strip().replace('*', '').replace('#', '')
                message += f"  {i}. {point_clean}\n"
        
        message += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    def get_advice_history(self, symbol: Optional[str] = None, hours: int = 24) -> List[Dict[str, Any]]:
        """获取历史建议"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        history = [
            h for h in self.advice_history
            if h['timestamp'] > cutoff
        ]
        
        if symbol:
            history = [h for h in history if h['symbol'] == symbol]
        
        return history


if __name__ == '__main__':
    # 测试
    async def test():
        advisor = AITradingAdvisor()
        
        # 模拟数据
        advice = await advisor.generate_trading_advice(
            symbol='005930',
            name='삼성전자',
            current_price=75000,
            price_data={'change_pct': 2.5, 'volume_ratio': 3.0},
            technical_indicators={'rsi': 45, 'macd': {'macd': 100}},
            sentiment={'overall_sentiment': 'positive', 'score': 0.6, 'article_count': 5},
            news=[{'title': '삼성전자 실적 호조'}],
            strategy_signals=[
                {'action': 'BUY', 'weight': 0.3},
                {'action': 'BUY', 'weight': 0.25}
            ]
        )
        
        print(advisor.format_advice_for_telegram(advice))
    
    asyncio.run(test())
