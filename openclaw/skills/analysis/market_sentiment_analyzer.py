"""
市场情绪分析

功能：
- 社交媒体情绪监控 (Twitter, Reddit, Telegram等)
- 新闻情绪分析
- 恐慌贪婪指数
- 搜索热度追踪
- 市场情绪聚合
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from loguru import logger


class MarketSentimentAnalyzer:
    """
    市场情绪分析器
    
    聚合多个来源的情绪数据，生成综合情绪指标
    """
    
    def __init__(self):
        """初始化情绪分析器"""
        # 配置参数
        self.sentiment_threshold_positive = 0.6
        self.sentiment_threshold_negative = 0.4
        
        # 数据缓存
        self.sentiment_history: Dict[str, List[Dict[str, Any]]] = {}
        self.news_sentiment_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.social_media_cache: Dict[str, List[Dict[str, Any]]] = {}
        
        logger.info("✅ MarketSentimentAnalyzer 初始化成功")
    
    def analyze_social_media_sentiment(
        self,
        symbol: str,
        posts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析社交媒体情绪
        
        Args:
            symbol: 交易对
            posts: 帖子列表 [{content, timestamp, platform, likes, comments, sentiment_score}, ...]
        
        Returns:
            社媒情绪分析
        """
        if not posts:
            return {"error": "无社交媒体数据"}
        
        # 计算平均情绪得分（-1到1）
        sentiment_scores = [p.get('sentiment_score', 0) for p in posts]
        avg_sentiment = np.mean(sentiment_scores)
        std_sentiment = np.std(sentiment_scores)
        
        # 计算加权情绪（考虑点赞/评论数）
        weighted_scores = []
        for post in posts:
            score = post.get('sentiment_score', 0)
            weight = (post.get('likes', 0) + post.get('comments', 0) * 2) + 1
            weighted_scores.append(score * weight)
        
        weighted_sentiment = sum(weighted_scores) / sum(
            (p.get('likes', 0) + p.get('comments', 0) * 2) + 1 for p in posts
        ) if posts else 0
        
        # 情绪分类
        if weighted_sentiment > 0.3:
            sentiment_label = 'BULLISH'
        elif weighted_sentiment > 0.1:
            sentiment_label = 'SLIGHTLY_BULLISH'
        elif weighted_sentiment < -0.3:
            sentiment_label = 'BEARISH'
        elif weighted_sentiment < -0.1:
            sentiment_label = 'SLIGHTLY_BEARISH'
        else:
            sentiment_label = 'NEUTRAL'
        
        # 按平台分组
        platforms = {}
        for post in posts:
            platform = post.get('platform', 'unknown')
            if platform not in platforms:
                platforms[platform] = {'count': 0, 'avg_sentiment': []}
            
            platforms[platform]['count'] += 1
            platforms[platform]['avg_sentiment'].append(post.get('sentiment_score', 0))
        
        platform_sentiments = {
            p: {
                'count': data['count'],
                'avg_sentiment': np.mean(data['avg_sentiment'])
            }
            for p, data in platforms.items()
        }
        
        # 趋势分析（最近vs之前）
        if len(posts) >= 10:
            recent_posts = sorted(posts, key=lambda x: x.get('timestamp', ''))[-5:]
            earlier_posts = sorted(posts, key=lambda x: x.get('timestamp', ''))[:-5][:5]
            
            recent_sentiment = np.mean([p.get('sentiment_score', 0) for p in recent_posts])
            earlier_sentiment = np.mean([p.get('sentiment_score', 0) for p in earlier_posts])
            
            sentiment_change = recent_sentiment - earlier_sentiment
            
            if sentiment_change > 0.2:
                trend = 'IMPROVING'
            elif sentiment_change < -0.2:
                trend = 'DETERIORATING'
            else:
                trend = 'STABLE'
        else:
            trend = 'INSUFFICIENT_DATA'
        
        # 缓存结果
        if symbol not in self.social_media_cache:
            self.social_media_cache[symbol] = []
        
        self.social_media_cache[symbol].append({
            'timestamp': datetime.now().isoformat(),
            'sentiment': weighted_sentiment,
            'label': sentiment_label
        })
        
        return {
            'symbol': symbol,
            'post_count': len(posts),
            'avg_sentiment': avg_sentiment,
            'weighted_sentiment': weighted_sentiment,
            'std_sentiment': std_sentiment,
            'sentiment_label': sentiment_label,
            'trend': trend,
            'platform_breakdown': platform_sentiments,
            'interpretation': self._interpret_social_sentiment(sentiment_label, trend)
        }
    
    def analyze_news_sentiment(
        self,
        symbol: str,
        news_articles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析新闻情绪
        
        Args:
            symbol: 交易对
            news_articles: 新闻列表 [{title, content, timestamp, source, sentiment_score}, ...]
        
        Returns:
            新闻情绪分析
        """
        if not news_articles:
            return {"error": "无新闻数据"}
        
        # 计算平均情绪
        sentiment_scores = [a.get('sentiment_score', 0) for a in news_articles]
        avg_sentiment = np.mean(sentiment_scores)
        
        # 时间加权（最近的新闻权重更高）
        now = datetime.now()
        weighted_scores = []
        
        for article in news_articles:
            score = article.get('sentiment_score', 0)
            timestamp = article.get('timestamp', now.isoformat())
            
            try:
                article_time = datetime.fromisoformat(timestamp)
                age_hours = (now - article_time).total_seconds() / 3600
                # 时间衰减：24小时内权重100%，之后每24小时衰减50%
                weight = max(0.1, 1.0 / (1 + age_hours / 24))
            except:
                weight = 0.5
            
            weighted_scores.append(score * weight)
        
        time_weighted_sentiment = np.mean(weighted_scores)
        
        # 情绪分类
        if time_weighted_sentiment > 0.3:
            sentiment_label = 'POSITIVE'
        elif time_weighted_sentiment > 0.1:
            sentiment_label = 'SLIGHTLY_POSITIVE'
        elif time_weighted_sentiment < -0.3:
            sentiment_label = 'NEGATIVE'
        elif time_weighted_sentiment < -0.1:
            sentiment_label = 'SLIGHTLY_NEGATIVE'
        else:
            sentiment_label = 'NEUTRAL'
        
        # 来源可信度分析
        credible_sources = ['bloomberg', 'reuters', 'coindesk', 'cointelegraph']
        credible_news = [a for a in news_articles if any(s in a.get('source', '').lower() for s in credible_sources)]
        
        if credible_news:
            credible_sentiment = np.mean([a.get('sentiment_score', 0) for a in credible_news])
        else:
            credible_sentiment = None
        
        # 缓存结果
        if symbol not in self.news_sentiment_cache:
            self.news_sentiment_cache[symbol] = []
        
        self.news_sentiment_cache[symbol].append({
            'timestamp': datetime.now().isoformat(),
            'sentiment': time_weighted_sentiment,
            'label': sentiment_label
        })
        
        return {
            'symbol': symbol,
            'article_count': len(news_articles),
            'avg_sentiment': avg_sentiment,
            'time_weighted_sentiment': time_weighted_sentiment,
            'sentiment_label': sentiment_label,
            'credible_news_count': len(credible_news),
            'credible_news_sentiment': credible_sentiment,
            'interpretation': self._interpret_news_sentiment(sentiment_label, credible_sentiment)
        }
    
    def calculate_fear_greed_index(
        self,
        symbol: str,
        metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        计算恐慌贪婪指数
        
        Args:
            symbol: 交易对
            metrics: 指标字典 {
                'volatility': 波动率(0-1),
                'volume': 成交量比率(0-1),
                'social_media': 社媒情绪(0-1),
                'market_momentum': 市场动量(0-1),
                'dominance': 市场主导性(0-1)
            }
        
        Returns:
            恐慌贪婪指数
        """
        # 权重配置
        weights = {
            'volatility': 0.25,
            'volume': 0.20,
            'social_media': 0.20,
            'market_momentum': 0.25,
            'dominance': 0.10
        }
        
        # 计算加权得分
        score = 0
        valid_metrics = 0
        
        for metric, value in metrics.items():
            if metric in weights:
                # 波动率需要反转（高波动=恐慌）
                if metric == 'volatility':
                    value = 1 - value
                
                score += value * weights[metric]
                valid_metrics += weights[metric]
        
        # 归一化到0-100
        if valid_metrics > 0:
            fear_greed_index = (score / valid_metrics) * 100
        else:
            fear_greed_index = 50
        
        # 分类
        if fear_greed_index >= 75:
            state = 'EXTREME_GREED'
            signal = 'SELL'  # 反向指标
        elif fear_greed_index >= 60:
            state = 'GREED'
            signal = 'CAUTION'
        elif fear_greed_index >= 40:
            state = 'NEUTRAL'
            signal = 'NEUTRAL'
        elif fear_greed_index >= 25:
            state = 'FEAR'
            signal = 'CAUTION'
        else:
            state = 'EXTREME_FEAR'
            signal = 'BUY'  # 反向指标
        
        return {
            'symbol': symbol,
            'index': fear_greed_index,
            'state': state,
            'signal': signal,
            'metrics': metrics,
            'interpretation': self._interpret_fear_greed(state, fear_greed_index)
        }
    
    def aggregate_sentiment_signals(
        self,
        symbol: str,
        social_sentiment: Optional[Dict[str, Any]] = None,
        news_sentiment: Optional[Dict[str, Any]] = None,
        fear_greed: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        聚合所有情绪信号
        
        Args:
            symbol: 交易对
            social_sentiment: 社媒情绪分析结果
            news_sentiment: 新闻情绪分析结果
            fear_greed: 恐慌贪婪指数
        
        Returns:
            综合情绪信号
        """
        signals = []
        scores = []
        
        # 社媒情绪
        if social_sentiment and 'sentiment_label' in social_sentiment:
            label = social_sentiment['sentiment_label']
            if 'BULLISH' in label:
                signals.append('社媒看涨')
                scores.append(0.7)
            elif 'BEARISH' in label:
                signals.append('社媒看跌')
                scores.append(0.7)
        
        # 新闻情绪
        if news_sentiment and 'sentiment_label' in news_sentiment:
            label = news_sentiment['sentiment_label']
            if 'POSITIVE' in label:
                signals.append('新闻积极')
                scores.append(0.8)
            elif 'NEGATIVE' in label:
                signals.append('新闻消极')
                scores.append(0.8)
        
        # 恐慌贪婪
        if fear_greed and 'signal' in fear_greed:
            signal = fear_greed['signal']
            if signal == 'BUY':
                signals.append('极度恐慌（反向买入）')
                scores.append(0.6)
            elif signal == 'SELL':
                signals.append('极度贪婪（反向卖出）')
                scores.append(0.6)
        
        # 综合判断
        if not signals:
            overall_signal = 'NEUTRAL'
            confidence = 0
        else:
            bullish_signals = sum(1 for s in signals if '看涨' in s or '买入' in s or '积极' in s)
            bearish_signals = sum(1 for s in signals if '看跌' in s or '卖出' in s or '消极' in s)
            
            if bullish_signals > bearish_signals:
                overall_signal = 'BULLISH'
                confidence = np.mean(scores[:bullish_signals])
            elif bearish_signals > bullish_signals:
                overall_signal = 'BEARISH'
                confidence = np.mean(scores[bullish_signals:bullish_signals+bearish_signals])
            else:
                overall_signal = 'NEUTRAL'
                confidence = 0
        
        # 记录历史
        if symbol not in self.sentiment_history:
            self.sentiment_history[symbol] = []
        
        self.sentiment_history[symbol].append({
            'timestamp': datetime.now().isoformat(),
            'signal': overall_signal,
            'confidence': confidence
        })
        
        return {
            'symbol': symbol,
            'overall_signal': overall_signal,
            'confidence': confidence,
            'signals': signals,
            'signal_sources': {
                'social_media': social_sentiment is not None,
                'news': news_sentiment is not None,
                'fear_greed': fear_greed is not None
            }
        }
    
    def _interpret_social_sentiment(self, label: str, trend: str) -> str:
        """解释社媒情绪"""
        base = {
            'BULLISH': '社交媒体情绪积极，看涨声音占主导',
            'SLIGHTLY_BULLISH': '社交媒体情绪偏积极',
            'NEUTRAL': '社交媒体情绪中性',
            'SLIGHTLY_BEARISH': '社交媒体情绪偏消极',
            'BEARISH': '社交媒体情绪消极，看跌声音占主导'
        }.get(label, '')
        
        if trend == 'IMPROVING':
            base += '，且情绪正在改善'
        elif trend == 'DETERIORATING':
            base += '，且情绪正在恶化'
        
        return base
    
    def _interpret_news_sentiment(self, label: str, credible_sentiment: Optional[float]) -> str:
        """解释新闻情绪"""
        base = {
            'POSITIVE': '新闻报道积极正面',
            'SLIGHTLY_POSITIVE': '新闻报道偏正面',
            'NEUTRAL': '新闻报道中性',
            'SLIGHTLY_NEGATIVE': '新闻报道偏负面',
            'NEGATIVE': '新闻报道消极负面'
        }.get(label, '')
        
        if credible_sentiment is not None:
            if credible_sentiment > 0.2:
                base += '，主流媒体态度积极'
            elif credible_sentiment < -0.2:
                base += '，主流媒体态度消极'
        
        return base
    
    def _interpret_fear_greed(self, state: str, index: float) -> str:
        """解释恐慌贪婪指数"""
        interpretations = {
            'EXTREME_GREED': f'极度贪婪（{index:.0f}），市场可能过热，考虑获利了结',
            'GREED': f'贪婪（{index:.0f}），市场情绪乐观，保持警惕',
            'NEUTRAL': f'中性（{index:.0f}），市场情绪平衡',
            'FEAR': f'恐慌（{index:.0f}），市场情绪悲观，可能存在机会',
            'EXTREME_FEAR': f'极度恐慌（{index:.0f}），市场可能超卖，考虑逢低买入'
        }
        
        return interpretations.get(state, '')


if __name__ == '__main__':
    # 测试
    analyzer = MarketSentimentAnalyzer()
    
    # 模拟社交媒体数据
    posts = [
        {'content': 'BTC to the moon!', 'sentiment_score': 0.8, 'likes': 100, 'platform': 'twitter'},
        {'content': 'Great buy opportunity', 'sentiment_score': 0.6, 'likes': 50, 'platform': 'reddit'},
        {'content': 'Not sure about this', 'sentiment_score': -0.2, 'likes': 20, 'platform': 'twitter'},
    ]
    
    social_analysis = analyzer.analyze_social_media_sentiment('BTC', posts)
    print("\n=== 社交媒体情绪分析 ===")
    print(f"加权情绪: {social_analysis['weighted_sentiment']:.2f}")
    print(f"标签: {social_analysis['sentiment_label']}")
    print(f"解释: {social_analysis['interpretation']}")
    
    # 恐慌贪婪指数
    metrics = {
        'volatility': 0.7,
        'volume': 0.6,
        'social_media': 0.8,
        'market_momentum': 0.5,
        'dominance': 0.4
    }
    
    fg_index = analyzer.calculate_fear_greed_index('BTC', metrics)
    print("\n=== 恐慌贪婪指数 ===")
    print(f"指数: {fg_index['index']:.0f}")
    print(f"状态: {fg_index['state']}")
    print(f"解释: {fg_index['interpretation']}")
