"""
Sentiment analysis for news and market data
"""
from typing import Dict, List, Any
from datetime import datetime
from loguru import logger


class SentimentAnalysis:
    """Analyze sentiment from various sources"""
    
    def __init__(self):
        """Initialize sentiment analyzer"""
        self.sentiment_history: List[Dict[str, Any]] = []
    
    def analyze_news_sentiment(
        self,
        news_articles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze sentiment from news articles
        
        Args:
            news_articles: List of news articles
        
        Returns:
            Aggregated sentiment score
        """
        if not news_articles:
            return {
                "overall_sentiment": "neutral",
                "score": 0.0,
                "confidence": 0.0,
                "article_count": 0
            }
        
        sentiments = []
        for article in news_articles:
            text = f"{article.get('title', '')} {article.get('description', '')}"
            sentiment = self._analyze_text(text)
            sentiments.append(sentiment)
        
        # Aggregate sentiments
        avg_score = sum(s['score'] for s in sentiments) / len(sentiments)
        
        overall = "neutral"
        if avg_score > 0.3:
            overall = "positive"
        elif avg_score < -0.3:
            overall = "negative"
        
        result = {
            "overall_sentiment": overall,
            "score": avg_score,
            "confidence": sum(s['confidence'] for s in sentiments) / len(sentiments),
            "article_count": len(news_articles),
            "timestamp": datetime.now().isoformat()
        }
        
        self.sentiment_history.append(result)
        return result
    
    def _analyze_text(self, text: str) -> Dict[str, Any]:
        """Simple sentiment analysis (fallback)"""
        text_lower = text.lower()
        
        positive_words = [
            'good', 'great', 'excellent', 'positive', 'growth', 'profit',
            'increase', 'rise', 'up', 'gain', 'bull', 'surge', 'rally'
        ]
        negative_words = [
            'bad', 'poor', 'negative', 'decline', 'loss', 'decrease',
            'down', 'fall', 'bear', 'drop', 'crash', 'plunge'
        ]
        
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        
        total = pos_count + neg_count
        if total == 0:
            return {"score": 0.0, "confidence": 0.5}
        
        score = (pos_count - neg_count) / total
        confidence = min(1.0, total / 10)
        
        return {"score": score, "confidence": confidence}
    
    def analyze_market_sentiment(
        self,
        price_data: Dict[str, Any],
        volume_ratio: float,
        rsi: float
    ) -> Dict[str, Any]:
        """
        Analyze market sentiment from price action
        
        Args:
            price_data: Price information
            volume_ratio: Volume vs average
            rsi: RSI value
        
        Returns:
            Market sentiment analysis
        """
        sentiment_score = 0.0
        factors = []
        
        # Price movement
        price_change_pct = price_data.get('change_pct', 0)
        if price_change_pct > 2:
            sentiment_score += 0.3
            factors.append("strong_price_increase")
        elif price_change_pct < -2:
            sentiment_score -= 0.3
            factors.append("strong_price_decrease")
        
        # Volume
        if volume_ratio > 1.5:
            if price_change_pct > 0:
                sentiment_score += 0.2
                factors.append("high_volume_buying")
            else:
                sentiment_score -= 0.2
                factors.append("high_volume_selling")
        
        # RSI
        if rsi > 70:
            sentiment_score -= 0.1
            factors.append("overbought")
        elif rsi < 30:
            sentiment_score += 0.1
            factors.append("oversold")
        
        # Determine overall sentiment
        if sentiment_score > 0.3:
            overall = "bullish"
        elif sentiment_score < -0.3:
            overall = "bearish"
        else:
            overall = "neutral"
        
        return {
            "market_sentiment": overall,
            "score": sentiment_score,
            "factors": factors,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_sentiment_index(self) -> float:
        """
        Calculate overall market sentiment index
        
        Returns:
            Sentiment index (-1 to 1)
        """
        if not self.sentiment_history:
            return 0.0
        
        # Use recent sentiments (last 10)
        recent = self.sentiment_history[-10:]
        return sum(s['score'] for s in recent) / len(recent)
