"""
AI Models Manager for OpenClaw Trading System
2026 Edition with Gemini 3 Flash and DeepSeek-R1

Manages both dedicated models (high-frequency) and LLM (anomaly-triggered)
Dual-model architecture: Gemini (primary) + DeepSeek (emergency backup)
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import asyncio
import os
import re
import yaml
from loguru import logger

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("Transformers not available, sentiment analysis will be limited")

try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("Scikit-learn not available, anomaly detection will be limited")

# 2026 LLM imports
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Google Generative AI not available, Gemini 3 disabled")

# Claude removed from architecture - using Gemini + DeepSeek only
ANTHROPIC_AVAILABLE = False

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI client not available, DeepSeek-R1 disabled")

# RSS feed parsing for global news
try:
    import feedparser
    import aiohttp
    from dateutil import parser as date_parser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    logger.warning("feedparser/aiohttp/dateutil not available, global news disabled")

# Currency converter
try:
    from ..utils.currency_converter import get_converter
    CURRENCY_CONVERTER_AVAILABLE = True
except ImportError:
    CURRENCY_CONVERTER_AVAILABLE = False
    logger.warning("Currency converter not available")


class AIModelManager:
    """
    Manages AI models for trading analysis
    
    Architecture (2026 Simplified Edition):
    - Dedicated models: Used in high-frequency loop (~50-100ms)
    - LLM (Dual-model): Gemini 3 Flash (primary, 100%) + DeepSeek-R1 (emergency backup)
    - Global news: 100+ sources from 7 continents
    - Currency: All prices in Korean Won (KRW)
    """
    
    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        """
        Initialize AI model manager
        
        Args:
            api_keys: Dictionary containing API keys for LLMs
                - google_ai_api_key: Google AI API key (required)
                - deepseek_api_key: DeepSeek API key (optional, emergency backup)
        """
        self.models = {}
        self.tokenizers = {}
        self.isolation_forest = None
        
        # Load API keys from environment or parameters
        self.api_keys = api_keys or {}
        if not self.api_keys.get('google_ai_api_key'):
            self.api_keys['google_ai_api_key'] = os.getenv('GOOGLE_AI_API_KEY', '')
        if not self.api_keys.get('deepseek_api_key'):
            self.api_keys['deepseek_api_key'] = os.getenv('DEEPSEEK_API_KEY', '')
        
        # Initialize 2026 LLM clients (dual-model architecture)
        self.gemini_client = None
        self.deepseek_client = None
        self._init_llm_clients()
        
        # Load global news configuration
        self.news_sources = {}
        self.asset_keywords = {}
        self._load_news_config()
        
        # News cache (5 minutes TTL)
        self.news_cache: Dict[str, Tuple[datetime, List[Dict[str, Any]]]] = {}
        self.news_cache_ttl = timedelta(minutes=5)
        
        # Model usage statistics (dual-model)
        self.model_stats = {
            'gemini': {'calls': 0, 'successes': 0, 'failures': 0},
            'deepseek': {'calls': 0, 'successes': 0, 'failures': 0},
        }
        
        # Currency converter
        self.currency_converter = None
        if CURRENCY_CONVERTER_AVAILABLE:
            try:
                self.currency_converter = get_converter()
            except Exception as e:
                logger.warning(f"Failed to initialize currency converter: {e}")
        
        # Load traditional models
        self._load_models()
    
    def _init_llm_clients(self):
        """Initialize 2026 LLM clients (dual-model architecture)"""
        # Gemini 3 Flash (Primary - 100% usage)
        if GEMINI_AVAILABLE and self.api_keys.get('google_ai_api_key'):
            try:
                genai.configure(api_key=self.api_keys['google_ai_api_key'])
                self.gemini_client = genai.GenerativeModel('gemini-1.5-flash')
                logger.info("✅ Gemini 3 Flash client initialized (primary model)")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")
        
        # DeepSeek-R1 (Emergency backup only)
        if OPENAI_AVAILABLE and self.api_keys.get('deepseek_api_key'):
            try:
                self.deepseek_client = AsyncOpenAI(
                    api_key=self.api_keys['deepseek_api_key'],
                    base_url="https://api.deepseek.com/v1"
                )
                logger.info("✅ DeepSeek-R1 client initialized (emergency backup)")
            except Exception as e:
                logger.warning(f"Failed to initialize DeepSeek client: {e}")
    
    def _load_news_config(self):
        """Load global news sources configuration"""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(base_dir, "config", "global_news_sources.yaml")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            self.news_sources = config.get('news_sources', {})
            self.asset_keywords = config.get('asset_keywords', {})
            self.news_processing_config = config.get('processing', {})
            
            # Count total sources
            total_sources = 0
            for region in self.news_sources.values():
                for country in region.values():
                    total_sources += len(country)
            
            logger.info(f"✅ Loaded {total_sources} global news sources")
        except Exception as e:
            logger.warning(f"Failed to load news config: {e}")
            self.news_sources = {}
            self.asset_keywords = {}
    
    def _load_models(self):
        """Load AI models into memory"""
        logger.info("🤖 Loading AI models...")
        
        # Load FinBERT for sentiment analysis (stocks)
        if TRANSFORMERS_AVAILABLE:
            try:
                logger.info("Loading FinBERT...")
                self.tokenizers['finbert'] = AutoTokenizer.from_pretrained(
                    "ProsusAI/finbert",
                    cache_dir="models/finbert"
                )
                self.models['finbert'] = AutoModelForSequenceClassification.from_pretrained(
                    "ProsusAI/finbert",
                    cache_dir="models/finbert"
                )
                self.models['finbert'].eval()
                logger.info("✅ FinBERT loaded")
            except Exception as e:
                logger.warning(f"Failed to load FinBERT: {e}")
        
        # Initialize Isolation Forest for anomaly detection
        if SKLEARN_AVAILABLE:
            try:
                logger.info("Initializing Isolation Forest...")
                self.isolation_forest = IsolationForest(
                    contamination=0.1,
                    random_state=42,
                    n_estimators=100
                )
                logger.info("✅ Isolation Forest initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Isolation Forest: {e}")
        
        logger.info("✅ AI models initialization complete")
    
    def analyze_sentiment(self, text: str, model_type: str = "finbert") -> Dict[str, Any]:
        """
        Analyze sentiment of text (news, announcements)
        
        Performance: ~50ms
        
        Args:
            text: Text to analyze
            model_type: Model to use (finbert or cryptobert)
        
        Returns:
            Sentiment analysis results
        """
        start_time = datetime.now()
        
        if not TRANSFORMERS_AVAILABLE or model_type not in self.models:
            # Fallback: Simple keyword-based sentiment
            return self._simple_sentiment(text)
        
        try:
            # Tokenize
            inputs = self.tokenizers[model_type](
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            )
            
            # Get predictions
            with torch.no_grad():
                outputs = self.models[model_type](**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            
            # Map to sentiment labels
            labels = ["negative", "neutral", "positive"]
            scores = predictions[0].tolist()
            sentiment_idx = scores.index(max(scores))
            
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                "sentiment": labels[sentiment_idx],
                "confidence": max(scores),
                "scores": dict(zip(labels, scores)),
                "processing_time_ms": elapsed
            }
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return self._simple_sentiment(text)
    
    def _simple_sentiment(self, text: str) -> Dict[str, Any]:
        """Simple keyword-based sentiment analysis (fallback)"""
        text_lower = text.lower()
        
        positive_words = ['up', 'gain', 'profit', 'bull', 'growth', 'increase', 'surge', 'rally']
        negative_words = ['down', 'loss', 'bear', 'decline', 'decrease', 'drop', 'fall', 'crash']
        
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        
        if pos_count > neg_count:
            sentiment = "positive"
            confidence = 0.6
        elif neg_count > pos_count:
            sentiment = "negative"
            confidence = 0.6
        else:
            sentiment = "neutral"
            confidence = 0.5
        
        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "scores": {
                "negative": 0.2 if sentiment != "negative" else 0.6,
                "neutral": 0.6 if sentiment == "neutral" else 0.2,
                "positive": 0.2 if sentiment != "positive" else 0.6
            },
            "processing_time_ms": 1.0,
            "method": "keyword_fallback"
        }
    
    def predict_price(
        self,
        historical_prices: List[float],
        horizon: int = 5
    ) -> Dict[str, Any]:
        """
        Predict future prices using time series model
        
        Performance: ~100ms
        
        Args:
            historical_prices: List of historical prices
            horizon: Number of future periods to predict
        
        Returns:
            Price predictions
        """
        start_time = datetime.now()
        
        if len(historical_prices) < 10:
            return {
                "predictions": [],
                "confidence": 0.0,
                "method": "insufficient_data"
            }
        
        try:
            # Simple linear extrapolation (fallback for Chronos)
            # In production, would use Chronos model here
            prices = np.array(historical_prices[-50:])
            
            # Calculate trend
            x = np.arange(len(prices))
            coeffs = np.polyfit(x, prices, deg=1)
            
            # Predict future
            future_x = np.arange(len(prices), len(prices) + horizon)
            predictions = np.polyval(coeffs, future_x)
            
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                "predictions": predictions.tolist(),
                "confidence": 0.7,
                "trend": "upward" if coeffs[0] > 0 else "downward",
                "processing_time_ms": elapsed,
                "method": "linear_extrapolation"
            }
        except Exception as e:
            logger.error(f"Price prediction failed: {e}")
            return {
                "predictions": [],
                "confidence": 0.0,
                "method": "error"
            }
    
    def detect_anomaly(
        self,
        features: List[float],
        historical_features: List[List[float]]
    ) -> Dict[str, Any]:
        """
        Detect anomalies using Isolation Forest
        
        Performance: ~10ms
        
        Args:
            features: Current feature vector
            historical_features: Historical feature vectors for training
        
        Returns:
            Anomaly detection results
        """
        start_time = datetime.now()
        
        if not SKLEARN_AVAILABLE or not self.isolation_forest:
            return self._simple_anomaly_detection(features, historical_features)
        
        try:
            # Train on historical data if we have enough samples
            if len(historical_features) >= 50:
                self.isolation_forest.fit(historical_features)
            
            # Predict
            score = self.isolation_forest.score_samples([features])[0]
            is_anomaly = score < -0.2  # Threshold for anomaly
            
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            
            severity = "high" if score < -0.5 else "medium" if score < -0.2 else "low"
            
            return {
                "is_anomaly": is_anomaly,
                "score": float(score),
                "severity": severity,
                "processing_time_ms": elapsed,
                "method": "isolation_forest"
            }
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return self._simple_anomaly_detection(features, historical_features)
    
    def _simple_anomaly_detection(
        self,
        features: List[float],
        historical_features: List[List[float]]
    ) -> Dict[str, Any]:
        """Simple statistical anomaly detection (fallback)"""
        if len(historical_features) < 10:
            return {
                "is_anomaly": False,
                "score": 0.0,
                "severity": "low",
                "method": "insufficient_data"
            }
        
        # Use z-score based detection
        historical_array = np.array(historical_features)
        current = np.array(features)
        
        mean = np.mean(historical_array, axis=0)
        std = np.std(historical_array, axis=0)
        
        # Avoid division by zero
        std = np.where(std == 0, 1, std)
        
        z_scores = np.abs((current - mean) / std)
        max_z_score = np.max(z_scores)
        
        is_anomaly = max_z_score > 3.0
        score = -max_z_score / 10.0  # Normalize to similar range as Isolation Forest
        
        severity = "high" if max_z_score > 4 else "medium" if max_z_score > 3 else "low"
        
        return {
            "is_anomaly": is_anomaly,
            "score": float(score),
            "severity": severity,
            "max_z_score": float(max_z_score),
            "method": "z_score_fallback"
        }
    
    async def analyze_anomaly_with_llm(
        self,
        anomaly_data: Dict[str, Any],
        market_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deep analysis of anomaly using LLM (Phi-3.5 Mini)
        
        Performance: ~2-3 seconds
        Only called when anomaly is detected
        
        Args:
            anomaly_data: Anomaly detection results
            market_context: Current market context (prices, indicators, news)
        
        Returns:
            LLM analysis results
        """
        start_time = datetime.now()
        
        # Construct prompt for LLM
        prompt = self._construct_anomaly_prompt(anomaly_data, market_context)
        
        # In production, would call Phi-3.5 Mini here
        # For now, using rule-based analysis
        analysis = self._rule_based_anomaly_analysis(anomaly_data, market_context)
        
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            **analysis,
            "processing_time_ms": elapsed,
            "model": "rule_based_fallback"
        }
    
    def _construct_anomaly_prompt(
        self,
        anomaly_data: Dict[str, Any],
        market_context: Dict[str, Any]
    ) -> str:
        """Construct prompt for LLM analysis"""
        return f"""
Analyze the following market anomaly:

Anomaly Details:
- Severity: {anomaly_data.get('severity', 'unknown')}
- Score: {anomaly_data.get('score', 0)}
- Type: {anomaly_data.get('type', 'unknown')}

Market Context:
- Current Price: {market_context.get('current_price', 0)}
- Price Change: {market_context.get('price_change_pct', 0)}%
- Volume: {market_context.get('volume', 0)}
- RSI: {market_context.get('rsi', 50)}
- Recent News: {market_context.get('recent_news', 'None')}

Provide:
1. Root cause analysis
2. Risk assessment (1-10)
3. Recommended action (BUY/HOLD/SELL)
4. Confidence level (0-1)
"""
    
    def construct_short_term_analysis_prompt(
        self,
        symbol: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Construct short-term trading analysis prompt for LLM
        
        Args:
            symbol: Asset symbol
            context: Market context with short-term data
        
        Returns:
            Formatted prompt for LLM analysis
        """
        prompt = f"""You are a professional short-term trader (intraday/swing). Analyze this opportunity for QUICK trading (holding period: minutes to 1 day).

**Asset**: {symbol}
**Current Price**: ${context.get('current_price', 0):.2f}

**Minute-Level Price Action**:
- 1-minute change: {context.get('change_1m', 0):.2f}%
- 5-minute change: {context.get('change_5m', 0):.2f}%
- 15-minute change: {context.get('change_15m', 0):.2f}%
- Intraday change: {context.get('change_today', 0):.2f}%

**Short-Term Technical Indicators**:
- 5-minute RSI: {context.get('rsi_5m', 50):.1f}
- 5-minute MACD: {context.get('macd_5m', 0):.2f}
- MA(5): ${context.get('ma5', 0):.2f}
- MA(15): ${context.get('ma15', 0):.2f}
- Breaking intraday high: {context.get('break_high', False)}
- Breaking intraday low: {context.get('break_low', False)}

**Order Flow & Volume**:
- 1-minute volume: {context.get('volume_1m', 0):,}
- 5-minute volume: {context.get('volume_5m', 0):,}
- Volume vs average: {context.get('volume_ratio', 1.0):.2f}x
- Buy/Sell ratio: {context.get('buy_sell_ratio', 1.0):.2f}
- Large order flow: {context.get('large_order_flow', 'None')}

**Recent News** (last 1 hour):
{context.get('recent_news', 'No recent news')}

**Current Position** (if any):
{context.get('current_position', 'No position')}

**SHORT-TERM TRADING REQUIREMENTS**:
- Maximum holding period: 1 day (prefer hours)
- Stop loss: 1-2% (tight)
- Take profit targets: 1.5% (quick), 2.5% (main), 5% (stretch)
- Focus on: Price action, momentum, volume spikes, order flow

**Please provide**:
1. **Action**: BUY / SELL / HOLD
2. **Position Size**: 10-30% of capital
3. **Entry Price**: Precise entry point
4. **Stop Loss**: Exact price level
5. **Take Profit**: 3 levels (quick/main/stretch)
6. **Expected Hold Time**: Minutes/hours/intraday close
7. **Key Risks**: Main concerns for this trade
8. **Confidence**: 1-10 scale

**Think like a scalper/day trader**: Quick in, quick out. Don't overthink it."""
        
        return prompt
    
    def _rule_based_anomaly_analysis(
        self,
        anomaly_data: Dict[str, Any],
        market_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Rule-based anomaly analysis (fallback for LLM)"""
        risk_score = 5
        action = "HOLD"
        confidence = 0.5
        
        # Analyze severity
        severity = anomaly_data.get('severity', 'low')
        if severity == 'high':
            risk_score += 3
        elif severity == 'medium':
            risk_score += 1
        
        # Analyze price movement
        price_change = market_context.get('price_change_pct', 0)
        if abs(price_change) > 5:
            risk_score += 2
        
        # Analyze RSI
        rsi = market_context.get('rsi', 50)
        if rsi < 30:
            action = "BUY"
            confidence = 0.7
        elif rsi > 70:
            action = "SELL"
            confidence = 0.7
        
        # Analyze volume
        volume_ratio = market_context.get('volume_ratio', 1.0)
        if volume_ratio > 3:
            risk_score += 1
            confidence += 0.1
        
        root_cause = f"Anomaly detected with {severity} severity"
        if abs(price_change) > 5:
            root_cause += f", significant price movement ({price_change:.2f}%)"
        if volume_ratio > 3:
            root_cause += f", unusual volume ({volume_ratio:.2f}x normal)"
        
        return {
            "root_cause": root_cause,
            "risk_score": min(10, risk_score),
            "recommended_action": action,
            "confidence": min(1.0, confidence),
            "analysis": f"Based on {severity} severity anomaly and market conditions"
        }
    
    # ==========================================
    # 2026 LLM Methods
    # ==========================================
    
    def _choose_model(
        self,
        context: Dict[str, Any],
        all_news: List[Dict[str, Any]]
    ) -> str:
        """
        Choose the LLM model for analysis (simplified dual-model architecture)
        
        Always uses Gemini 3 Flash as the primary model.
        DeepSeek is only used if Gemini fails.
        
        Args:
            context: Market context
            all_news: All relevant news
        
        Returns:
            Model name ('gemini' always, unless unavailable)
        """
        # Always use Gemini 3 Flash (primary model)
        if self.gemini_client:
            logger.info(f"⚡ Using Gemini 3 Flash (primary model)")
            return 'gemini'
        
        # Fallback to DeepSeek only if Gemini unavailable
        if self.deepseek_client:
            logger.warning(f"🔄 Gemini unavailable, using DeepSeek-R1 (emergency)")
            return 'deepseek'
        
        logger.error("No LLM available")
        return 'none'
    
    async def _call_gemini(
        self,
        prompt: str,
        timeout: int = 10
    ) -> Optional[str]:
        """
        Call Gemini 3 Flash API
        
        Args:
            prompt: Prompt text
            timeout: Timeout in seconds
        
        Returns:
            Response text or None
        """
        if not self.gemini_client:
            return None
        
        try:
            self.model_stats['gemini']['calls'] += 1
            
            # Generate response
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.gemini_client.generate_content,
                    prompt
                ),
                timeout=timeout
            )
            
            self.model_stats['gemini']['successes'] += 1
            return response.text
        
        except Exception as e:
            self.model_stats['gemini']['failures'] += 1
            logger.error(f"Gemini API call failed: {e}")
            return None
    
    async def _call_deepseek(
        self,
        prompt: str,
        timeout: int = 15
    ) -> Optional[str]:
        """
        Call DeepSeek-R1 API (emergency backup)
        
        Args:
            prompt: Prompt text
            timeout: Timeout in seconds
        
        Returns:
            Response text or None
        """
        if not self.deepseek_client:
            return None
        
        try:
            self.model_stats['deepseek']['calls'] += 1
            
            # Create chat completion
            response = await asyncio.wait_for(
                self.deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=2000
                ),
                timeout=timeout
            )
            
            self.model_stats['deepseek']['successes'] += 1
            return response.choices[0].message.content
        
        except Exception as e:
            self.model_stats['deepseek']['failures'] += 1
            logger.error(f"DeepSeek API call failed: {e}")
            return None
    
    async def _call_llm_with_fallback(
        self,
        prompt: str,
        preferred_model: str
    ) -> Tuple[Optional[str], str]:
        """
        Call LLM with automatic fallback (dual-model architecture)
        
        Fallback chain: Gemini ↔ DeepSeek
        
        Args:
            prompt: Prompt text
            preferred_model: Preferred model name ('gemini' or 'deepseek')
        
        Returns:
            (response_text, actual_model_used)
        """
        # Simplified fallback order for dual-model architecture
        if preferred_model == 'gemini':
            models_to_try = ['gemini', 'deepseek']
        elif preferred_model == 'deepseek':
            models_to_try = ['deepseek', 'gemini']
        else:
            models_to_try = ['gemini', 'deepseek']
        
        for model in models_to_try:
            try:
                if model == 'gemini':
                    response = await self._call_gemini(prompt)
                elif model == 'deepseek':
                    response = await self._call_deepseek(prompt)
                else:
                    continue
                
                if response:
                    logger.info(f"✅ LLM response received from {model}")
                    return response, model
            
            except Exception as e:
                logger.warning(f"Model {model} failed: {e}, trying next...")
                continue
        
        logger.error("All LLM models failed")
        return None, 'none'
    
    async def _fetch_global_news_for_llm(
        self,
        symbol: str,
        max_news: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Fetch global news for the asset
        
        Args:
            symbol: Asset symbol
            max_news: Maximum number of news articles to return
        
        Returns:
            List of relevant news articles
        """
        # Check cache first
        if symbol in self.news_cache:
            cache_time, cached_news = self.news_cache[symbol]
            if datetime.now() - cache_time < self.news_cache_ttl:
                logger.debug(f"Using cached news for {symbol}")
                return cached_news[:max_news]
        
        if not FEEDPARSER_AVAILABLE:
            logger.warning("feedparser not available, skipping global news")
            return []
        
        # Get keywords for this asset
        keywords = self.asset_keywords.get(symbol, [])
        global_keywords = self.asset_keywords.get('GLOBAL', [])
        all_keywords = keywords + global_keywords
        
        if not all_keywords:
            logger.warning(f"No keywords defined for {symbol}")
            return []
        
        # Fetch news from all sources concurrently
        all_news = []
        tasks = []
        
        # Flatten news sources
        for region in self.news_sources.values():
            for country in region.values():
                for source in country:
                    task = self._fetch_rss_source(source, all_keywords)
                    tasks.append(task)
        
        # Limit concurrent fetches
        max_concurrent = self.news_processing_config.get('concurrent_fetches', 20)
        
        # Fetch in batches
        for i in range(0, len(tasks), max_concurrent):
            batch = tasks[i:i+max_concurrent]
            results = await asyncio.gather(*batch, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    all_news.extend(result)
        
        # Filter by time (last N hours)
        max_age_hours = self.news_processing_config.get('max_age_hours', 1)
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        recent_news = [
            news for news in all_news
            if news.get('published_date', datetime.min) > cutoff_time
        ]
        
        # Deduplicate by title similarity
        unique_news = self._deduplicate_news(recent_news)
        
        # Score by relevance
        scored_news = self._score_news_relevance(unique_news, keywords)
        
        # Sort by score (descending)
        sorted_news = sorted(
            scored_news,
            key=lambda x: x.get('relevance_score', 0),
            reverse=True
        )
        
        # Cache results
        self.news_cache[symbol] = (datetime.now(), sorted_news)
        
        logger.info(f"📰 Fetched {len(sorted_news)} relevant news for {symbol}")
        
        return sorted_news[:max_news]
    
    async def _fetch_rss_source(
        self,
        source: Dict[str, Any],
        keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch news from single RSS source
        
        Args:
            source: Source configuration
            keywords: Keywords to match
        
        Returns:
            List of news articles
        """
        if not source.get('rss'):
            return []
        
        try:
            timeout = self.news_processing_config.get('source_timeout_seconds', 5)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(source['rss'], timeout=timeout) as response:
                    if response.status != 200:
                        return []
                    
                    content = await response.text()
            
            # Parse RSS feed
            feed = await asyncio.to_thread(feedparser.parse, content)
            
            articles = []
            for entry in feed.entries[:10]:  # Limit per source
                # Parse published date
                pub_date = datetime.now()
                if hasattr(entry, 'published'):
                    try:
                        pub_date = date_parser.parse(entry.published)
                    except:
                        pass
                
                # Extract title and description
                title = entry.get('title', '')
                description = entry.get('description', '') or entry.get('summary', '')
                
                # Quick keyword match
                text = (title + ' ' + description).lower()
                has_keyword = any(kw.lower() in text for kw in keywords)
                
                if has_keyword:
                    articles.append({
                        'title': title,
                        'description': description,
                        'link': entry.get('link', ''),
                        'source': source.get('name', 'Unknown'),
                        'language': source.get('language', 'en'),
                        'category': source.get('category', 'general'),
                        'published_date': pub_date
                    })
            
            return articles
        
        except Exception as e:
            logger.debug(f"Failed to fetch {source.get('name', 'unknown')}: {e}")
            return []
    
    def _deduplicate_news(
        self,
        news_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate news by title similarity"""
        if not news_list:
            return []
        
        unique = []
        seen_titles = set()
        
        for news in news_list:
            title = news.get('title', '').lower()
            # Simple deduplication by normalized title
            title_normalized = ''.join(c for c in title if c.isalnum())
            
            if title_normalized not in seen_titles:
                seen_titles.add(title_normalized)
                unique.append(news)
        
        return unique
    
    def _score_news_relevance(
        self,
        news_list: List[Dict[str, Any]],
        keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """Score news articles by relevance"""
        config = self.news_processing_config.get('relevance', {})
        title_weight = config.get('title_match_weight', 3.0)
        desc_weight = config.get('description_match_weight', 1.5)
        recency_weight = config.get('recency_weight', 2.0)
        
        for news in news_list:
            score = 0.0
            
            # Title match
            title = news.get('title', '').lower()
            title_matches = sum(1 for kw in keywords if kw.lower() in title)
            score += title_matches * title_weight
            
            # Description match
            desc = news.get('description', '').lower()
            desc_matches = sum(1 for kw in keywords if kw.lower() in desc)
            score += desc_matches * desc_weight
            
            # Recency
            pub_date = news.get('published_date', datetime.now())
            hours_old = (datetime.now() - pub_date).total_seconds() / 3600
            recency_score = max(0, 1 - (hours_old / 24))  # Decay over 24 hours
            score += recency_score * recency_weight
            
            news['relevance_score'] = score
        
        return news_list
    
    async def analyze_anomaly_with_llm_2026(
        self,
        symbol: str,
        anomaly_data: Dict[str, Any],
        market_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deep analysis of anomaly using 2026 LLM architecture
        
        Args:
            symbol: Asset symbol
            anomaly_data: Anomaly detection results
            market_context: Current market context
        
        Returns:
            LLM analysis results with KRW prices
        """
        start_time = datetime.now()
        
        # 1. Convert all prices to KRW
        if self.currency_converter:
            market_context = await self.currency_converter.convert_context_to_krw(
                symbol,
                market_context
            )
        
        # 2. Fetch global news
        all_news = await self._fetch_global_news_for_llm(symbol, max_news=30)
        
        # 3. Choose best model
        preferred_model = self._choose_model(market_context, all_news)
        
        # 4. Construct prompt with KRW prices and global news
        prompt = self._construct_2026_prompt(symbol, anomaly_data, market_context, all_news)
        
        # 5. Call LLM with fallback
        response_text, model_used = await self._call_llm_with_fallback(prompt, preferred_model)
        
        # 6. Parse response or use rule-based fallback
        if response_text:
            analysis = self._parse_llm_response(response_text)
        else:
            logger.warning("LLM failed, using rule-based analysis")
            analysis = self._rule_based_anomaly_analysis(anomaly_data, market_context)
        
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            **analysis,
            "processing_time_ms": elapsed,
            "model_used": model_used,
            "news_count": len(all_news),
            "currency": "KRW"
        }
    
    def _construct_2026_prompt(
        self,
        symbol: str,
        anomaly_data: Dict[str, Any],
        context: Dict[str, Any],
        news: List[Dict[str, Any]]
    ) -> str:
        """
        Construct 2026 prompt with KRW prices and global news
        
        Args:
            symbol: Asset symbol
            anomaly_data: Anomaly details
            context: Market context (in KRW)
            news: Global news list
        
        Returns:
            Formatted prompt
        """
        # Format prices in KRW
        if self.currency_converter:
            fmt_price = self.currency_converter.format_krw
            fmt_change = self.currency_converter.format_change
        else:
            fmt_price = lambda x: f"₩{x:,.0f}"
            fmt_change = lambda x: f"{x*100:+.2f}%"
        
        # Build news section
        news_section = "## 📰 Global News (Last Hour)\n\n"
        if news:
            # Group by region
            news_by_region = {}
            for article in news[:20]:  # Top 20 most relevant
                category = article.get('category', 'general')
                if category not in news_by_region:
                    news_by_region[category] = []
                news_by_region[category].append(article)
            
            for category, articles in news_by_region.items():
                news_section += f"### {category.title()}\n"
                for article in articles[:5]:  # Top 5 per category
                    flag = self._get_language_flag(article.get('language', 'en'))
                    news_section += f"- {flag} **[{article.get('source', 'Unknown')}]** {article.get('title', '')}\n"
                news_section += "\n"
        else:
            news_section += "No recent news available.\n\n"
        
        # Construct full prompt
        prompt = f"""You are an expert AI trading analyst for OpenClaw 2026.

## 🎯 Asset: {symbol}

## 🚨 Anomaly Detected
- Severity: {anomaly_data.get('severity', 'unknown')}
- Type: {anomaly_data.get('type', 'unknown')}
- Score: {anomaly_data.get('score', 0):.2f}

## 💱 Market Data (All prices in Korean Won ₩)
- Current Price: {fmt_price(context.get('current_price', 0))}
- 5-Min Change: {fmt_change(context.get('change_5m', 0) / 100)}
- 15-Min Change: {fmt_change(context.get('change_15m', 0) / 100)}
- Today Change: {fmt_change(context.get('change_today', 0) / 100)}
- Volume Ratio: {context.get('volume_ratio', 1.0):.2f}x
- RSI (5m): {context.get('rsi_5m', 50):.1f}
- MA5: {fmt_price(context.get('ma5', 0))}
- MA15: {fmt_price(context.get('ma15', 0))}

{news_section}

## 📋 Your Task

Analyze this anomaly and provide:

1. **Root Cause**: What's driving this anomaly? (2-3 sentences)
2. **Action**: BUY / SELL / HOLD
3. **Entry Price** (in KRW): Exact entry point
4. **Stop Loss** (in KRW): Risk management level
5. **Take Profit** (in KRW): Target exit
6. **Risk Score**: 1-10 (higher = riskier)
7. **Confidence**: 0-1 (higher = more confident)
8. **Reasoning**: Brief explanation (2-3 sentences)

**Important Notes:**
- All prices MUST be in Korean Won (₩)
- Consider global news sentiment
- Focus on short-term opportunities (hours to 1 day)
- Be concise and actionable

Provide your analysis in a structured format."""
        
        return prompt
    
    def _get_language_flag(self, language: str) -> str:
        """Get emoji flag for language"""
        flags = {
            'en': '🇺🇸',
            'ko': '🇰🇷',
            'ja': '🇯🇵',
            'zh': '🇨🇳',
            'de': '🇩🇪',
            'fr': '🇫🇷',
            'es': '🇪🇸',
            'pt': '🇧🇷',
        }
        return flags.get(language, '🌍')
    
    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured format
        
        Args:
            response_text: Raw LLM response
        
        Returns:
            Parsed analysis dict
        """
        # Simple parsing - in production would use more robust parsing
        result = {
            "root_cause": "LLM analysis completed",
            "recommended_action": "HOLD",
            "risk_score": 5,
            "confidence": 0.7,
            "analysis": response_text[:500],  # Truncate for storage
            "full_response": response_text
        }
        
        # Try to extract action
        response_lower = response_text.lower()
        if 'action: buy' in response_lower or 'action:** buy' in response_lower:
            result['recommended_action'] = 'BUY'
        elif 'action: sell' in response_lower or 'action:** sell' in response_lower:
            result['recommended_action'] = 'SELL'
        
        # Try to extract confidence
        conf_match = re.search(r'confidence[:\s]+([0-9.]+)', response_lower)
        if conf_match:
            try:
                result['confidence'] = float(conf_match.group(1))
            except:
                pass
        
        # Try to extract risk score
        risk_match = re.search(r'risk score[:\s]+([0-9]+)', response_lower)
        if risk_match:
            try:
                result['risk_score'] = int(risk_match.group(1))
            except:
                pass
        
        return result
    
    def get_model_statistics(self) -> Dict[str, Any]:
        """Get LLM usage statistics"""
        return {
            'models': self.model_stats,
            'total_calls': sum(m['calls'] for m in self.model_stats.values()),
            'total_successes': sum(m['successes'] for m in self.model_stats.values()),
            'total_failures': sum(m['failures'] for m in self.model_stats.values()),
        }
