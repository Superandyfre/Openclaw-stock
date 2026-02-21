"""
重要人物RSS订阅监控器

订阅加密货币领域重要人物的博客、文章和官方声明

完全免费，无需API密钥
"""
import asyncio
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
import requests
from xml.etree import ElementTree as ET

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    logger.warning("feedparser未安装，RSS监控将使用模拟数据")


class InfluencerRSSMonitor:
    """
    重要人物RSS订阅监控器
    
    监控加密货币领域重要人物的博客和文章
    完全免费，无需API密钥
    """
    
    # 预设的重要人物RSS订阅源
    IMPORTANT_FEEDS = {
        'vitalik_buterin': {
            'name': 'Vitalik Buterin',
            'role': 'Ethereum创始人',
            'rss_url': 'https://vitalik.eth.limo/feed.xml',
            'website': 'https://vitalik.eth.limo',
            'keywords': ['Ethereum', 'blockchain', 'scaling', 'Layer2', 'PoS'],
            'importance': 'VERY_HIGH'
        },
        'michael_saylor': {
            'name': 'Michael Saylor',
            'role': 'MicroStrategy CEO',
            'rss_url': None,  # 需要通过Twitter或Medium获取
            'website': 'https://michael.com',
            'keywords': ['Bitcoin', 'MicroStrategy', 'digital asset', 'store of value'],
            'importance': 'HIGH'
        },
        'ark_invest': {
            'name': 'ARK Invest (Cathie Wood)',
            'role': '投资机构',
            'rss_url': 'https://ark-invest.com/articles/feed/',
            'website': 'https://ark-invest.com',
            'keywords': ['Bitcoin', 'innovation', 'disruptive', 'technology'],
            'importance': 'HIGH'
        },
        'coindesk': {
            'name': 'CoinDesk',
            'role': '加密新闻媒体',
            'rss_url': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
            'website': 'https://www.coindesk.com',
            'keywords': ['Bitcoin', 'Ethereum', 'crypto', 'regulation', 'market'],
            'importance': 'MEDIUM'
        },
        'cointelegraph': {
            'name': 'Cointelegraph',
            'role': '加密新闻媒体',
            'rss_url': 'https://cointelegraph.com/rss',
            'website': 'https://cointelegraph.com',
            'keywords': ['cryptocurrency', 'blockchain', 'Bitcoin', 'Ethereum'],
            'importance': 'MEDIUM'
        },
        'bitcoin_magazine': {
            'name': 'Bitcoin Magazine',
            'role': 'Bitcoin新闻媒体',
            'rss_url': 'https://bitcoinmagazine.com/.rss/full/',
            'website': 'https://bitcoinmagazine.com',
            'keywords': ['Bitcoin', 'Lightning Network', 'mining', 'adoption'],
            'importance': 'MEDIUM'
        },
        'ethereum_foundation': {
            'name': 'Ethereum Foundation',
            'role': 'Ethereum官方',
            'rss_url': 'https://blog.ethereum.org/feed.xml',
            'website': 'https://blog.ethereum.org',
            'keywords': ['Ethereum', 'EIP', 'upgrade', 'research', 'development'],
            'importance': 'HIGH'
        },
        'a16z_crypto': {
            'name': 'a16z Crypto',
            'role': '投资机构',
            'rss_url': 'https://a16zcrypto.com/feed/',
            'website': 'https://a16zcrypto.com',
            'keywords': ['crypto', 'web3', 'investment', 'regulation', 'innovation'],
            'importance': 'HIGH'
        }
    }
    
    def __init__(
        self,
        feeds: Optional[List[str]] = None,
        update_interval_minutes: int = 60
    ):
        """
        初始化RSS监控器
        
        Args:
            feeds: 要监控的订阅源列表（key）
            update_interval_minutes: 更新间隔（分钟）
        """
        # 监控的订阅源（默认监控所有）
        if feeds:
            self.feeds = feeds
        else:
            self.feeds = list(self.IMPORTANT_FEEDS.keys())
        
        self.update_interval = update_interval_minutes
        
        # 数据缓存
        self.article_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.last_update_time: Dict[str, datetime] = {}
        
        logger.info(f"✅ InfluencerRSSMonitor 初始化")
        logger.info(f"   监控订阅源: {len(self.feeds)}个")
    
    def fetch_feed(
        self,
        feed_key: str,
        since_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        获取RSS订阅源内容
        
        Args:
            feed_key: 订阅源key
            since_hours: 获取多少小时内的文章
        
        Returns:
            文章列表
        """
        feed_info = self.IMPORTANT_FEEDS.get(feed_key)
        if not feed_info:
            logger.error(f"未知的订阅源: {feed_key}")
            return []
        
        rss_url = feed_info.get('rss_url')
        if not rss_url:
            logger.warning(f"{feed_info['name']} 暂无RSS订阅源")
            return self._generate_mock_articles(feed_key, 5)
        
        # 如果没有feedparser，使用模拟数据
        if not FEEDPARSER_AVAILABLE:
            return self._generate_mock_articles(feed_key, 5)
        
        try:
            # 获取RSS内容
            feed = feedparser.parse(rss_url)
            
            articles = []
            cutoff_time = datetime.now() - timedelta(hours=since_hours)
            
            for entry in feed.entries[:20]:  # 最多获取20篇
                # 解析发布时间
                published_time = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_time = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published_time = datetime(*entry.updated_parsed[:6])
                
                # 只获取指定时间内的文章
                if published_time and published_time < cutoff_time:
                    continue
                
                # 提取内容摘要
                summary = ''
                if hasattr(entry, 'summary'):
                    summary = entry.summary[:500]
                elif hasattr(entry, 'description'):
                    summary = entry.description[:500]
                
                # 清理HTML标签
                summary = re.sub(r'<[^>]+>', '', summary)
                
                articles.append({
                    'feed': feed_key,
                    'author': feed_info['name'],
                    'title': entry.title if hasattr(entry, 'title') else 'No title',
                    'summary': summary,
                    'link': entry.link if hasattr(entry, 'link') else '',
                    'published': published_time.isoformat() if published_time else datetime.now().isoformat(),
                    'timestamp': datetime.now().isoformat()
                })
            
            logger.info(f"获取 {feed_info['name']} 的 {len(articles)} 篇文章")
            return articles
        
        except Exception as e:
            logger.error(f"获取RSS订阅失败 {feed_info['name']}: {e}")
            return self._generate_mock_articles(feed_key, 5)
    
    def analyze_articles(
        self,
        articles: List[Dict[str, Any]],
        feed_key: str
    ) -> Dict[str, Any]:
        """
        分析文章内容
        
        Args:
            articles: 文章列表
            feed_key: 订阅源key
        
        Returns:
            分析结果
        """
        if not articles:
            return {'error': '无文章数据'}
        
        feed_info = self.IMPORTANT_FEEDS.get(feed_key, {})
        keywords = feed_info.get('keywords', [])
        
        # 1. 关键词统计
        keyword_counts = {kw: 0 for kw in keywords}
        for article in articles:
            title = article.get('title', '').lower()
            summary = article.get('summary', '').lower()
            combined_text = title + ' ' + summary
            
            for kw in keywords:
                if kw.lower() in combined_text:
                    keyword_counts[kw] += 1
        
        # 2. 情绪分析（基于关键词）
        bullish_keywords = [
            'bullish', 'positive', 'growth', 'adoption', 'breakthrough', 'innovation',
            'surge', 'rally', 'optimistic', 'upgrade', 'improvement', 'success'
        ]
        bearish_keywords = [
            'bearish', 'negative', 'crisis', 'regulation', 'ban', 'crackdown',
            'drop', 'crash', 'concern', 'risk', 'warning', 'decline'
        ]
        
        bullish_count = 0
        bearish_count = 0
        
        for article in articles:
            title = article.get('title', '').lower()
            summary = article.get('summary', '').lower()
            combined = title + ' ' + summary
            
            bullish_count += sum(1 for kw in bullish_keywords if kw in combined)
            bearish_count += sum(1 for kw in bearish_keywords if kw in combined)
        
        total_sentiment_signals = bullish_count + bearish_count
        if total_sentiment_signals > 0:
            sentiment_score = (bullish_count - bearish_count) / total_sentiment_signals
        else:
            sentiment_score = 0
        
        # 情绪分类
        if sentiment_score > 0.3:
            sentiment_label = 'POSITIVE'
        elif sentiment_score > 0.1:
            sentiment_label = 'SLIGHTLY_POSITIVE'
        elif sentiment_score < -0.3:
            sentiment_label = 'NEGATIVE'
        elif sentiment_score < -0.1:
            sentiment_label = 'SLIGHTLY_NEGATIVE'
        else:
            sentiment_label = 'NEUTRAL'
        
        # 3. 主题分类
        topics = {
            'Bitcoin': 0,
            'Ethereum': 0,
            'DeFi': 0,
            'NFT': 0,
            'Regulation': 0,
            'Technology': 0,
            'Market': 0
        }
        
        topic_keywords = {
            'Bitcoin': ['bitcoin', 'btc', 'satoshi'],
            'Ethereum': ['ethereum', 'eth', 'vitalik'],
            'DeFi': ['defi', 'decentralized finance', 'liquidity', 'yield'],
            'NFT': ['nft', 'non-fungible', 'collectible', 'metaverse'],
            'Regulation': ['regulation', 'sec', 'government', 'policy', 'law'],
            'Technology': ['technology', 'protocol', 'upgrade', 'development', 'scalability'],
            'Market': ['market', 'price', 'trading', 'investment', 'valuation']
        }
        
        for article in articles:
            title = article.get('title', '').lower()
            summary = article.get('summary', '').lower()
            combined = title + ' ' + summary
            
            for topic, kws in topic_keywords.items():
                if any(kw in combined for kw in kws):
                    topics[topic] += 1
        
        # 4. 重要性评分（基于作者权重）
        importance = feed_info.get('importance', 'MEDIUM')
        importance_score = {
            'VERY_HIGH': 1.0,
            'HIGH': 0.8,
            'MEDIUM': 0.6,
            'LOW': 0.4
        }.get(importance, 0.6)
        
        analysis = {
            'feed': feed_key,
            'author': feed_info.get('name', feed_key),
            'role': feed_info.get('role', 'Unknown'),
            'importance': importance,
            'importance_score': importance_score,
            'timestamp': datetime.now().isoformat(),
            'article_count': len(articles),
            'keyword_mentions': keyword_counts,
            'sentiment': {
                'score': sentiment_score,
                'label': sentiment_label,
                'positive_signals': bullish_count,
                'negative_signals': bearish_count
            },
            'topics': topics,
            'recent_articles': [
                {
                    'title': article['title'],
                    'summary': article['summary'][:150] + '...' if len(article['summary']) > 150 else article['summary'],
                    'link': article['link'],
                    'published': article['published']
                }
                for article in articles[:5]  # 最近5篇
            ]
        }
        
        # 缓存结果
        if feed_key not in self.article_cache:
            self.article_cache[feed_key] = []
        
        self.article_cache[feed_key].extend(articles)
        
        # 限制缓存大小
        if len(self.article_cache[feed_key]) > 100:
            self.article_cache[feed_key] = self.article_cache[feed_key][-100:]
        
        self.last_update_time[feed_key] = datetime.now()
        
        return analysis
    
    def monitor_all_feeds(
        self,
        since_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        监控所有配置的订阅源
        
        Args:
            since_hours: 获取多少小时内的文章
        
        Returns:
            所有订阅源的分析结果
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🔄 开始RSS订阅监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*70}")
        
        results = []
        
        for feed_key in self.feeds:
            try:
                # 获取文章
                articles = self.fetch_feed(feed_key, since_hours=since_hours)
                
                # 分析文章
                if articles:
                    analysis = self.analyze_articles(articles, feed_key)
                    results.append(analysis)
                    
                    # 打印摘要
                    sentiment = analysis.get('sentiment', {})
                    logger.info(f"📰 {analysis['author']}: {analysis['article_count']}篇文章, "
                              f"情绪={sentiment['label']}, "
                              f"重要性={analysis['importance']}")
                
                # 避免速率限制
                import time
                time.sleep(1)
            
            except Exception as e:
                logger.error(f"监控订阅源失败 {feed_key}: {e}")
        
        logger.info(f"{'='*70}")
        logger.info(f"✅ RSS监控完成，共分析 {len(results)} 个订阅源")
        logger.info(f"{'='*70}\n")
        
        return results
    
    def _generate_mock_articles(self, feed_key: str, count: int) -> List[Dict[str, Any]]:
        """生成模拟文章（用于测试）"""
        import random
        
        feed_info = self.IMPORTANT_FEEDS.get(feed_key, {})
        author = feed_info.get('name', 'Unknown Author')
        
        mock_titles = [
            "The Future of Ethereum: Scaling Solutions and Layer 2 Networks",
            "Bitcoin's Role as Digital Gold in the Modern Economy",
            "Understanding DeFi: Opportunities and Risks",
            "Regulatory Landscape for Cryptocurrencies in 2026",
            "Innovation in Blockchain Technology: What's Next?",
            "MicroStrategy's Bitcoin Strategy: A Deep Dive",
            "Ethereum Merge Anniversary: One Year Later",
            "The Rise of Institutional Crypto Adoption"
        ]
        
        articles = []
        base_time = datetime.now()
        
        for i in range(count):
            articles.append({
                'feed': feed_key,
                'author': author,
                'title': random.choice(mock_titles),
                'summary': 'This is a mock article summary for testing purposes. The full content would contain detailed analysis and insights about cryptocurrency markets and technology.',
                'link': f'https://example.com/article/{i}',
                'published': (base_time - timedelta(hours=random.randint(1, 23))).isoformat(),
                'timestamp': datetime.now().isoformat()
            })
        
        return articles
    
    def get_summary_report(self, analyses: List[Dict[str, Any]]) -> str:
        """
        生成RSS监控摘要报告
        
        Args:
            analyses: 订阅源分析结果列表
        
        Returns:
            报告文本
        """
        if not analyses:
            return "无RSS订阅数据"
        
        report = []
        report.append("\n" + "="*70)
        report.append("📚 重要人物RSS订阅报告")
        report.append("="*70)
        report.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"监控订阅源: {len(analyses)}个")
        report.append("")
        
        # 整体情绪统计
        total_positive = sum(1 for a in analyses if a.get('sentiment', {}).get('label') in ['POSITIVE', 'SLIGHTLY_POSITIVE'])
        total_negative = sum(1 for a in analyses if a.get('sentiment', {}).get('label') in ['NEGATIVE', 'SLIGHTLY_NEGATIVE'])
        total_neutral = len(analyses) - total_positive - total_negative
        
        report.append("【整体情绪】")
        report.append(f"  正面: {total_positive}个订阅源")
        report.append(f"  负面: {total_negative}个订阅源")
        report.append(f"  中性: {total_neutral}个订阅源")
        report.append("")
        
        # 热门主题
        all_topics = {}
        for analysis in analyses:
            for topic, count in analysis.get('topics', {}).items():
                if topic not in all_topics:
                    all_topics[topic] = 0
                all_topics[topic] += count
        
        if all_topics:
            report.append("【热门主题】")
            for topic, count in sorted(all_topics.items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    report.append(f"  {topic}: {count}篇文章")
            report.append("")
        
        # 各订阅源详情
        report.append("【订阅源详情】")
        # 按重要性排序
        sorted_analyses = sorted(analyses, key=lambda x: x.get('importance_score', 0), reverse=True)
        
        for analysis in sorted_analyses:
            author = analysis.get('author', 'Unknown')
            role = analysis.get('role', '')
            article_count = analysis['article_count']
            sentiment = analysis.get('sentiment', {})
            importance = analysis.get('importance', 'MEDIUM')
            
            report.append(f"\n  📰 {author} ({role})")
            report.append(f"     重要性: {importance}")
            report.append(f"     文章数: {article_count}")
            report.append(f"     情绪: {sentiment.get('label', 'UNKNOWN')} (得分: {sentiment.get('score', 0):.2f})")
            
            # 最新文章标题
            recent_articles = analysis.get('recent_articles', [])
            if recent_articles:
                report.append(f"     最新文章:")
                for i, article in enumerate(recent_articles[:2], 1):  # 只显示最新2篇
                    title = article['title'][:60] + '...' if len(article['title']) > 60 else article['title']
                    report.append(f"       {i}. {title}")
        
        report.append("\n" + "="*70)
        
        return '\n'.join(report)
