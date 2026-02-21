"""
增强版AI交易顾问

整合所有监控模块和免费数据源：
1. 市场深度分析（MarketDepthAnalyzer）
2. 高级技术指标（AdvancedIndicatorMonitor）
3. 衍生品数据（DerivativesDataMonitor）
4. 市场情绪（MarketSentimentAnalyzer）
5. 智能信号聚合（SmartSignalAggregator）
6. 免费数据源（FreeDataSourceConnector）
"""
import os
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

# 导入分析模块
try:
    from openclaw.skills.analysis.market_depth_analyzer import MarketDepthAnalyzer
    from openclaw.skills.analysis.advanced_indicator_monitor import AdvancedIndicatorMonitor
    from openclaw.skills.analysis.derivatives_data_monitor import DerivativesDataMonitor
    from openclaw.skills.analysis.market_sentiment_analyzer import MarketSentimentAnalyzer
    from openclaw.skills.analysis.smart_signal_aggregator import SmartSignalAggregator
    ANALYSIS_MODULES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"分析模块导入失败: {e}")
    ANALYSIS_MODULES_AVAILABLE = False

# 导入数据源
try:
    from openclaw.skills.data_collection.free_data_sources import FreeDataSourceConnector
    DATA_SOURCE_AVAILABLE = True
except ImportError:
    logger.warning("免费数据源连接器未找到")
    DATA_SOURCE_AVAILABLE = False

# Gemini AI
try:
    from openclaw.skills.analysis.gemini_model_manager import GeminiModelManager
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class EnhancedAITradingAdvisor:
    """
    增强版AI交易顾问
    
    整合6大模块：
    1. 实时数据获取（Binance, CoinGecko等）
    2. 订单簿深度分析
    3. 技术指标监控
    4. 衍生品数据分析
    5. 市场情绪分析
    6. 智能信号聚合
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        enable_derivatives: bool = False  # 是否启用衍生品分析（杠杆相关）
    ):
        """
        初始化增强版AI交易顾问
        
        Args:
            api_key: Google AI API密钥
            enable_derivatives: 是否启用衍生品分析（默认关闭，适用于现货交易）
        """
        self.api_key = api_key or os.getenv('GOOGLE_AI_API_KEY')
        self.enable_derivatives = enable_derivatives
        
        # 初始化数据源
        if DATA_SOURCE_AVAILABLE:
            self.data_connector = FreeDataSourceConnector()
            logger.info("✅ 免费数据源连接器初始化成功")
        else:
            self.data_connector = None
            logger.warning("⚠️ 数据源连接器不可用")
        
        # 初始化分析模块
        if ANALYSIS_MODULES_AVAILABLE:
            self.depth_analyzer = MarketDepthAnalyzer()
            self.indicator_monitor = AdvancedIndicatorMonitor()
            self.sentiment_analyzer = MarketSentimentAnalyzer()
            
            # 衍生品模块（可选）
            if enable_derivatives:
                self.derivatives_monitor = DerivativesDataMonitor()
                logger.info("✅ 衍生品监控已启用")
            else:
                self.derivatives_monitor = None
                logger.info("ℹ️  衍生品监控已禁用（现货模式）")
            
            # 信号聚合器
            weights = {
                'market_depth': 0.25,
                'technical': 0.40,
                'derivatives': 0.15 if enable_derivatives else 0,
                'sentiment': 0.20 if not enable_derivatives else 0.35
            }
            self.signal_aggregator = SmartSignalAggregator(custom_weights=weights)
            
            logger.info("✅ 分析模块初始化成功")
        else:
            logger.error("❌ 分析模块不可用")
            self.depth_analyzer = None
            self.indicator_monitor = None
            self.derivatives_monitor = None
            self.sentiment_analyzer = None
            self.signal_aggregator = None
        
        # 初始化Gemini AI
        if GEMINI_AVAILABLE and self.api_key:
            try:
                self.model_manager = GeminiModelManager(
                    api_key=self.api_key,
                    default_task_type='standard'
                )
                logger.info("✅ Gemini AI初始化成功")
            except Exception as e:
                logger.error(f"Gemini AI初始化失败: {e}")
                self.model_manager = None
        else:
            self.model_manager = None
        
        # 建议历史
        self.advice_history: List[Dict[str, Any]] = []
    
    async def analyze_crypto(
        self,
        symbol: str,
        coin_id: str = 'bitcoin',
        depth_levels: int = 20
    ) -> Dict[str, Any]:
        """
        综合分析加密货币
        
        Args:
            symbol: Binance交易对（如 'BTCUSDT'）
            coin_id: CoinGecko币种ID（如 'bitcoin'）
            depth_levels: 订单簿深度（5/10/20/50）
        
        Returns:
            综合分析结果
        """
        logger.info(f"开始分析 {symbol}...")
        
        if not self.data_connector:
            return {"error": "数据源连接器不可用"}
        
        analysis_result = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'data': {},
            'signals': {},
            'recommendation': None
        }
        
        # ==================== 1. 获取实时数据 ====================
        logger.info("步骤1: 获取实时数据...")
        
        try:
            # Binance数据
            orderbook = self.data_connector.get_binance_orderbook(symbol, limit=depth_levels)
            klines = self.data_connector.get_binance_klines(symbol, interval='1h', limit=200)
            ticker_24h = self.data_connector.get_binance_ticker_24h(symbol)
            
            # CoinGecko数据
            cg_price = self.data_connector.get_coingecko_price(coin_id)
            
            # 恐慌贪婪指数
            fear_greed = self.data_connector.get_fear_greed_index()
            
            analysis_result['data'] = {
                'current_price': ticker_24h['last_price'] if ticker_24h else None,
                'orderbook': orderbook,
                'klines_count': len(klines) if klines else 0,
                'market_cap': cg_price['market_cap'] if cg_price else None,
                'fear_greed_index': fear_greed['value'] if fear_greed else None
            }
            
            logger.info(f"✅ 数据获取完成: 价格=${ticker_24h['last_price']:,.2f}" if ticker_24h else "✅ 数据获取完成")
        
        except Exception as e:
            logger.error(f"数据获取失败: {e}")
            return {"error": f"数据获取失败: {e}"}
        
        # ==================== 2. 市场深度分析 ====================
        if self.depth_analyzer and orderbook:
            logger.info("步骤2: 分析订单簿深度...")
            try:
                depth_analysis = self.depth_analyzer.analyze_orderbook(
                    symbol=symbol,
                    orderbook=orderbook,
                    trade_amount=10000  # 假设交易1万USD
                )
                
                analysis_result['signals']['market_depth'] = depth_analysis
                logger.info(f"✅ 深度分析: {depth_analysis.get('market_pressure', {}).get('signal', 'N/A')}")
            
            except Exception as e:
                logger.error(f"深度分析失败: {e}")
        
        # ==================== 3. 技术指标分析 ====================
        if self.indicator_monitor and klines:
            logger.info("步骤3: 分析技术指标...")
            try:
                # 更新K线数据
                for kline in klines:
                    self.indicator_monitor.update_price_data(
                        symbol=symbol,
                        candle={
                            'timestamp': kline['timestamp'],
                            'open': kline['open'],
                            'high': kline['high'],
                            'low': kline['low'],
                            'close': kline['close'],
                            'volume': kline['volume']
                        }
                    )
                
                # 分析指标
                tech_analysis = self.indicator_monitor.analyze_all_indicators(symbol)
                
                analysis_result['signals']['technical'] = tech_analysis
                logger.info(f"✅ 技术分析: {tech_analysis.get('signals', {}).get('action', 'N/A')}")
            
            except Exception as e:
                logger.error(f"技术分析失败: {e}")
        
        # ==================== 4. 市场情绪分析 ====================
        if self.sentiment_analyzer and fear_greed:
            logger.info("步骤4: 分析市场情绪...")
            try:
                # 构造恐慌贪婪指数的指标
                fg_metrics = {
                    'volatility': 0.5,  # 简化示例
                    'volume': ticker_24h['volume'] / 20000 if ticker_24h else 0.5,
                    'market_momentum': (ticker_24h['price_change_pct'] + 10) / 20 if ticker_24h else 0.5,
                    'social_media': fear_greed['value'] / 100,
                    'dominance': 0.5
                }
                
                sentiment_fg = self.sentiment_analyzer.calculate_fear_greed_index(
                    symbol=symbol,
                    metrics=fg_metrics
                )
                
                # 聚合情绪信号
                sentiment_aggregated = self.sentiment_analyzer.aggregate_sentiment_signals(
                    symbol=symbol,
                    fear_greed=sentiment_fg
                )
                
                analysis_result['signals']['sentiment'] = sentiment_aggregated
                logger.info(f"✅ 情绪分析: {sentiment_aggregated.get('overall_signal', 'N/A')}")
            
            except Exception as e:
                logger.error(f"情绪分析失败: {e}")
        
        # ==================== 5. 信号聚合 ====================
        if self.signal_aggregator:
            logger.info("步骤5: 聚合所有信号...")
            try:
                recommendation = self.signal_aggregator.aggregate_signals(
                    symbol=symbol,
                    market_depth=analysis_result['signals'].get('market_depth'),
                    technical=analysis_result['signals'].get('technical'),
                    derivatives=None,  # 现货模式不使用衍生品数据
                    sentiment=analysis_result['signals'].get('sentiment'),
                    current_price=ticker_24h['last_price'] if ticker_24h else None
                )
                
                analysis_result['recommendation'] = recommendation
                logger.info(f"✅ 最终建议: {recommendation['action']} (置信度: {recommendation['confidence']:.1%})")
            
            except Exception as e:
                logger.error(f"信号聚合失败: {e}")
        
        # ==================== 6. AI深度分析（可选）====================
        if self.model_manager and ticker_24h and fear_greed:
            logger.info("步骤6: AI深度分析...")
            try:
                ai_analysis = await self._ai_deep_analysis(
                    symbol=symbol,
                    current_price=ticker_24h['last_price'],
                    price_change_24h=ticker_24h['price_change_pct'],
                    fear_greed_index=fear_greed['value'],
                    recommendation=analysis_result.get('recommendation')
                )
                
                analysis_result['ai_analysis'] = ai_analysis
                logger.info("✅ AI分析完成")
            
            except Exception as e:
                logger.error(f"AI分析失败: {e}")
        
        # 记录历史
        self.advice_history.append(analysis_result)
        
        return analysis_result
    
    async def _ai_deep_analysis(
        self,
        symbol: str,
        current_price: float,
        price_change_24h: float,
        fear_greed_index: int,
        recommendation: Optional[Dict[str, Any]]
    ) -> str:
        """使用Gemini AI进行深度分析"""
        
        prompt = f"""作为加密货币交易专家，分析以下市场数据并给出专业建议：

交易对: {symbol}
当前价格: ${current_price:,.2f}
24小时涨跌: {price_change_24h:+.2f}%
恐慌贪婪指数: {fear_greed_index}/100

"""
        
        if recommendation:
            prompt += f"""系统综合分析建议:
- 行动: {recommendation['action']}
- 置信度: {recommendation['confidence']:.1%}
- 风险等级: {recommendation['risk_level']}
- 建议仓位: {recommendation['position_size']}

"""
        
        prompt += """请提供：
1. 市场环境评估（当前趋势、关键支撑阻力位）
2. 风险提示（需要注意的风险因素）
3. 具体操作建议（进场点位、止损止盈）
4. 持仓建议（适合短线/中线/长线）

请用简洁专业的语言回答（200字以内）。"""
        
        try:
            model = self.model_manager.get_model('standard')
            response = await model.generate_content_async(prompt)
            return response.text
        
        except Exception as e:
            logger.error(f"AI分析失败: {e}")
            return f"AI分析暂时不可用: {e}"
    
    def get_summary_report(self, analysis_result: Dict[str, Any]) -> str:
        """生成文字摘要报告"""
        
        lines = []
        lines.append("=" * 70)
        lines.append(f"📊 加密货币综合分析报告 - {analysis_result['symbol']}")
        lines.append("=" * 70)
        lines.append(f"分析时间: {analysis_result['timestamp']}")
        lines.append("")
        
        # 基础数据
        data = analysis_result.get('data', {})
        if data.get('current_price'):
            lines.append(f"💰 当前价格: ${data['current_price']:,.2f}")
        
        if data.get('market_cap'):
            lines.append(f"📈 市值: ${data['market_cap']:,.0f}")
        
        if data.get('fear_greed_index') is not None:
            fg_value = data['fear_greed_index']
            fg_label = "极度恐慌" if fg_value < 25 else "恐慌" if fg_value < 45 else "中性" if fg_value < 55 else "贪婪" if fg_value < 75 else "极度贪婪"
            lines.append(f"😱 恐慌贪婪指数: {fg_value}/100 ({fg_label})")
        
        lines.append("")
        
        # 信号分析
        lines.append("🔍 【信号分析】")
        signals = analysis_result.get('signals', {})
        
        if 'market_depth' in signals:
            depth_signal = signals['market_depth'].get('market_pressure', {}).get('signal', 'N/A')
            lines.append(f"  📊 订单簿: {depth_signal}")
        
        if 'technical' in signals:
            tech_action = signals['technical'].get('signals', {}).get('action', 'N/A')
            tech_conf = signals['technical'].get('signals', {}).get('confidence', 0)
            lines.append(f"  📈 技术面: {tech_action} (置信度: {tech_conf:.1%})")
        
        if 'sentiment' in signals:
            sent_signal = signals['sentiment'].get('overall_signal', 'N/A')
            lines.append(f"  😊 情绪面: {sent_signal}")
        
        lines.append("")
        
        # 综合建议
        rec = analysis_result.get('recommendation')
        if rec:
            lines.append("💡 【综合建议】")
            lines.append(f"  行动: {rec['action']}")
            lines.append(f"  置信度: {rec['confidence']:.1%}")
            lines.append(f"  风险等级: {rec['risk_level']}")
            lines.append(f"  建议仓位: {rec['position_size']}")
            
            if rec.get('stop_loss_pct'):
                lines.append(f"  止损: {rec['stop_loss_pct']:+.1f}%")
                lines.append(f"  止盈: {rec['take_profit_pct']:+.1f}%")
            
            lines.append("")
            lines.append(f"  说明: {rec.get('recommendation_text', '')}")
        
        # AI分析
        if 'ai_analysis' in analysis_result:
            lines.append("")
            lines.append("🤖 【AI深度分析】")
            lines.append(analysis_result['ai_analysis'])
        
        lines.append("")
        lines.append("=" * 70)
        
        return "\n".join(lines)


if __name__ == '__main__':
    # 测试
    async def test():
        advisor = EnhancedAITradingAdvisor(enable_derivatives=False)
        
        # 分析BTC
        result = await advisor.analyze_crypto('BTCUSDT', coin_id='bitcoin', depth_levels=20)
        
        # 打印报告
        print(advisor.get_summary_report(result))
    
    asyncio.run(test())
