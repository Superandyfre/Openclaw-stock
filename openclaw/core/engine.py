"""
OpenClaw Trading Engine - Main orchestration system

Architecture:
- High-frequency monitoring loop (15 seconds) using dedicated AI models
- Anomaly detection triggers LLM deep analysis
- News monitoring (hourly)
- Multi-asset support (stocks + crypto)
"""
import asyncio
import yaml
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
from loguru import logger

from .scheduler import Scheduler
from .database import DatabaseManager
from ..skills.data_collection import (
    StockMonitor,
    CryptoMonitor,
    NewsAggregator,
    AnnouncementMonitor
)
from ..skills.analysis import (
    AIModels,
    TechnicalAnalysis,
    SentimentAnalysis,
    RiskManagement,
    StrategyEngine
)
from ..skills.execution import OrderManager, PositionTracker
from ..skills.monitoring import SystemMonitor, AlertManager, AlertLevel


class OpenClawEngine:
    """Main trading engine orchestrating all components"""
    
    def __init__(self, config_dir: str = "openclaw/config"):
        """
        Initialize OpenClaw Engine
        
        Args:
            config_dir: Configuration directory path
        """
        logger.info("🦞 Initializing OpenClaw Trading Engine")
        
        # Load configurations
        self.config_dir = Path(config_dir)
        self.api_config = self._load_config("api_config.yaml")
        self.strategy_config = self._load_config("strategy_config.yaml")
        self.risk_config = self._load_config("risk_config.yaml")
        
        # Determine trading mode
        self.trading_mode = self.strategy_config.get('trading_mode', 'short_term')
        self.monitoring_interval = 5 if self.trading_mode == 'short_term' else 15
        
        logger.info(f"Trading mode: {self.trading_mode}")
        logger.info(f"Monitoring interval: {self.monitoring_interval} seconds")
        
        # Initialize components
        self.scheduler = Scheduler()
        self.db = DatabaseManager()
        self.ai_models = AIModels()
        self.technical_analysis = TechnicalAnalysis()
        self.sentiment_analysis = SentimentAnalysis()
        self.risk_manager = RiskManagement(self.risk_config['risk_management'])
        self.strategy_engine = StrategyEngine(
            self.strategy_config['strategies'],
            trading_mode=self.trading_mode
        )
        self.system_monitor = SystemMonitor()
        self.alert_manager = AlertManager()
        
        # Trading components
        self.order_manager = OrderManager(dry_run=True)
        self.position_tracker = PositionTracker()
        
        # Data collection
        self.stock_monitor = StockMonitor(
            symbols=self.api_config['yahoo_finance']['stocks'],
            rate_limit=self.api_config['yahoo_finance']['rate_limit']
        )
        
        self.crypto_monitor = CryptoMonitor(
            symbols=self.api_config['upbit']['cryptocurrencies'],
            websocket_url=self.api_config['upbit']['websocket_url']
        )
        
        self.news_aggregator = NewsAggregator(
            naver_client_id=self.api_config['naver'].get('client_id', ''),
            naver_client_secret=self.api_config['naver'].get('client_secret', ''),
            cryptopanic_api_key=self.api_config['cryptopanic'].get('api_key', '')
        )
        
        self.announcement_monitor = AnnouncementMonitor(
            dart_api_key=self.api_config['dart'].get('api_key', '')
        )
        
        # State
        self.running = False
        self.cycle_count = 0
        
        logger.info("✅ OpenClaw Engine initialized")
    
    def _load_config(self, filename: str) -> Dict[str, Any]:
        """Load YAML configuration file"""
        config_path = self.config_dir / filename
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config {filename}: {e}")
            return {}
    
    async def start(self):
        """Start the trading engine"""
        logger.info("🚀 Starting OpenClaw Trading Engine")
        logger.info(f"Mode: {self.trading_mode}, Monitoring: every {self.monitoring_interval}s")
        
        self.running = True
        self.scheduler.start()
        
        # Schedule high-frequency monitoring (5 seconds for short-term, 15 for long-term)
        await self.scheduler.schedule_periodic(
            "high_frequency_monitor",
            self._high_frequency_monitor_loop,
            self.monitoring_interval
        )
        
        # Schedule news monitoring (15 minutes for short-term, 1 hour for long-term)
        news_interval = 900 if self.trading_mode == 'short_term' else 3600  # 15 min vs 1 hour
        await self.scheduler.schedule_periodic(
            "news_monitor",
            self._news_monitor_loop,
            news_interval
        )
        
        # Schedule announcement monitoring (1 hour)
        await self.scheduler.schedule_periodic(
            "announcement_monitor",
            self._announcement_monitor_loop,
            3600  # 1 hour
        )
        
        # Start crypto WebSocket monitoring
        asyncio.create_task(self.crypto_monitor.start_monitoring())
        
        # Send startup alert
        await self.alert_manager.send_alert(
            "OpenClaw Trading Engine started successfully",
            AlertLevel.INFO
        )
        
        logger.info("✅ All monitoring loops started")
    
    async def _high_frequency_monitor_loop(self):
        """
        High-frequency monitoring loop (15 seconds)
        Uses dedicated AI models for fast analysis
        """
        start_time = datetime.now()
        self.cycle_count += 1
        
        logger.info(f"🔄 High-frequency cycle #{self.cycle_count}")
        
        try:
            # 1. Fetch market data
            stock_data = await self.stock_monitor.fetch_all_stocks()
            crypto_data = self.crypto_monitor.get_current_data()
            
            # 2. Analyze each asset
            for symbol, data in {**stock_data, **crypto_data}.items():
                await self._analyze_asset(symbol, data, "quick")
            
            # 3. Record performance
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            self.system_monitor.record_performance_metric(
                "high_freq_cycle_time",
                elapsed,
                "ms"
            )
            
            if elapsed > 500:
                logger.warning(f"⚠️  High-frequency cycle took {elapsed:.0f}ms (target < 500ms)")
            else:
                logger.debug(f"✅ High-frequency cycle completed in {elapsed:.0f}ms")
        
        except Exception as e:
            logger.error(f"Error in high-frequency monitor: {e}")
            await self.alert_manager.send_alert(
                f"High-frequency monitor error: {e}",
                AlertLevel.WARNING
            )
    
    async def _analyze_asset(self, symbol: str, data: Dict[str, Any], mode: str = "quick"):
        """
        Analyze a single asset
        
        Args:
            symbol: Asset symbol
            data: Current market data
            mode: Analysis mode (quick or deep)
        """
        try:
            # Get historical prices
            historical_prices = self.db.get_list(f"prices:{symbol}") or []
            historical_prices.append(data.get('current_price', 0))
            
            # Keep last 200 prices
            if len(historical_prices) > 200:
                historical_prices = historical_prices[-200:]
            
            # Store updated prices
            self.db.set(f"prices:{symbol}", historical_prices)
            
            # Calculate technical indicators
            if len(historical_prices) >= 50:
                indicators = self._calculate_indicators(historical_prices, data)
                
                # Quick sentiment analysis
                sentiment = {"score": 0.0, "overall_sentiment": "neutral"}
                
                # Anomaly detection
                features = self._extract_features(data, indicators)
                historical_features = self.db.get_list(f"features:{symbol}") or []
                
                anomaly_result = self.ai_models.detect_anomaly(features, historical_features)
                
                # Store features
                historical_features.append(features)
                if len(historical_features) > 500:
                    historical_features = historical_features[-500:]
                self.db.set(f"features:{symbol}", historical_features)
                
                # If anomaly detected, trigger deep analysis
                if anomaly_result['is_anomaly'] and anomaly_result['severity'] in ['medium', 'high']:
                    logger.warning(f"🚨 Anomaly detected for {symbol}: {anomaly_result}")
                    
                    await self.alert_manager.send_alert(
                        f"Anomaly detected in {symbol}",
                        AlertLevel.WARNING,
                        anomaly_result
                    )
                    
                    # Trigger LLM deep analysis (async, non-blocking)
                    asyncio.create_task(
                        self._deep_anomaly_analysis(symbol, data, indicators, anomaly_result)
                    )
                
                # Generate trading signals (fast)
                signals = self.strategy_engine.generate_signals(
                    symbol,
                    data,
                    indicators,
                    sentiment
                )
                
                if signals:
                    logger.info(f"📊 Signals for {symbol}: {len(signals)}")
                    decision = self.strategy_engine.aggregate_signals(signals)
                    
                    if decision['action'] in ['BUY', 'SELL'] and decision['confidence'] > 0.7:
                        await self._execute_signal(symbol, decision, data)
        
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
    
    def _calculate_indicators(self, prices: List[float], data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate technical indicators"""
        return {
            "ma_short": self.technical_analysis.calculate_ma(prices, 20)[-1] if len(prices) >= 20 else 0,
            "ma_long": self.technical_analysis.calculate_ma(prices, 50)[-1] if len(prices) >= 50 else 0,
            "rsi": self.technical_analysis.calculate_rsi(prices),
            "macd": self.technical_analysis.calculate_macd(prices),
            "bollinger_bands": self.technical_analysis.calculate_bollinger_bands(prices),
            "trend": self.technical_analysis.analyze_trend(prices),
            "volatility": self.technical_analysis.calculate_volatility(prices)
        }
    
    def _extract_features(self, data: Dict[str, Any], indicators: Dict[str, Any]) -> List[float]:
        """Extract feature vector for anomaly detection"""
        return [
            data.get('current_price', 0),
            data.get('change_pct', 0),
            data.get('volume', 0),
            indicators.get('rsi', 50),
            indicators.get('volatility', 0),
            indicators.get('macd', {}).get('histogram', 0)
        ]
    
    async def _deep_anomaly_analysis(
        self,
        symbol: str,
        data: Dict[str, Any],
        indicators: Dict[str, Any],
        anomaly_result: Dict[str, Any]
    ):
        """
        Deep LLM-based anomaly analysis (2-3 seconds)
        Runs asynchronously to not block main loop
        """
        logger.info(f"🤖 Starting deep LLM analysis for {symbol}")
        
        # Get recent news
        recent_news = self.db.get(f"news:{symbol}") or []
        
        # Prepare context
        market_context = {
            "current_price": data.get('current_price', 0),
            "price_change_pct": data.get('change_pct', 0),
            "volume": data.get('volume', 0),
            "volume_ratio": data.get('volume', 1) / data.get('avg_volume', 1) if data.get('avg_volume') else 1,
            "rsi": indicators.get('rsi', 50),
            "trend": indicators.get('trend', 'unknown'),
            "recent_news": recent_news[:3] if recent_news else []
        }
        
        # LLM analysis
        analysis = await self.ai_models.analyze_anomaly_with_llm(
            anomaly_result,
            market_context
        )
        
        logger.info(f"✅ LLM analysis complete for {symbol}: {analysis.get('recommended_action')}")
        
        # Send alert with LLM insights
        await self.alert_manager.send_alert(
            f"Deep analysis for {symbol}: {analysis.get('root_cause')}",
            AlertLevel.CRITICAL if analysis.get('risk_score', 0) > 7 else AlertLevel.WARNING,
            analysis
        )
    
    async def _news_monitor_loop(self):
        """News monitoring loop (hourly)"""
        logger.info("📰 Fetching news updates")
        
        try:
            # Fetch news for monitored assets
            news = await self.news_aggregator.fetch_relevant_news(
                self.api_config['yahoo_finance']['stocks'][:3],
                self.api_config['upbit']['cryptocurrencies'][:5]
            )
            
            logger.info(f"Fetched {len(news)} news articles")
            
            # Analyze sentiment
            if news:
                sentiment = self.sentiment_analysis.analyze_news_sentiment(news)
                logger.info(f"News sentiment: {sentiment.get('overall_sentiment')} ({sentiment.get('score'):.2f})")
                
                # Store news
                for article in news[:10]:
                    # Store by symbol if mentioned (simplified)
                    self.db.set(f"news:latest", news[:10])
        
        except Exception as e:
            logger.error(f"Error in news monitor: {e}")
    
    async def _announcement_monitor_loop(self):
        """Announcement monitoring loop (hourly)"""
        logger.info("📢 Checking for announcements")
        
        try:
            announcements = await self.announcement_monitor.monitor_announcements()
            
            if announcements:
                logger.info(f"Found {len(announcements)} significant announcements")
                
                await self.alert_manager.send_alert(
                    f"New announcements detected: {len(announcements)}",
                    AlertLevel.INFO,
                    {"count": len(announcements)}
                )
        
        except Exception as e:
            logger.error(f"Error in announcement monitor: {e}")
    
    async def _execute_signal(self, symbol: str, decision: Dict[str, Any], data: Dict[str, Any]):
        """Execute trading signal"""
        logger.info(f"💼 Executing signal for {symbol}: {decision['action']}")
        
        # Risk check
        portfolio_value = self.position_tracker.calculate_portfolio_value({symbol: data.get('current_price', 0)})
        
        # Calculate position size
        position_size = self.risk_manager.calculate_position_size(
            portfolio_value,
            data.get('current_price', 0)
        )
        
        if position_size > 0:
            # Create order (dry run mode)
            from ..skills.execution import OrderType
            
            order = self.order_manager.create_order(
                symbol=symbol,
                action=decision['action'],
                quantity=position_size,
                order_type=OrderType.MARKET,
                price=data.get('current_price', 0)
            )
            
            logger.info(f"Order created: {order.get('order_id', 'N/A')}")
    
    async def stop(self):
        """Stop the trading engine"""
        logger.info("⏹️  Stopping OpenClaw Trading Engine")
        
        self.running = False
        
        # Stop scheduler
        await self.scheduler.stop()
        
        # Stop crypto monitor
        await self.crypto_monitor.stop()
        
        # Close database
        self.db.close()
        
        # Send shutdown alert
        await self.alert_manager.send_alert(
            "OpenClaw Trading Engine stopped",
            AlertLevel.INFO
        )
        
        logger.info("✅ OpenClaw Engine stopped gracefully")
