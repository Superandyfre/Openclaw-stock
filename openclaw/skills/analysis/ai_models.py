"""
AI Models Manager for OpenClaw Trading System
Manages both dedicated models (high-frequency) and LLM (anomaly-triggered)
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np
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


class AIModelManager:
    """
    Manages AI models for trading analysis
    
    Architecture:
    - Dedicated models: Used in high-frequency loop (~50-100ms)
    - LLM: Triggered only on anomalies (~2-3s)
    """
    
    def __init__(self):
        """Initialize AI model manager"""
        self.models = {}
        self.tokenizers = {}
        self.isolation_forest = None
        self._load_models()
    
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
