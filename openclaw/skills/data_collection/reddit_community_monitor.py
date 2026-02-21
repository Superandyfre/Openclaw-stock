"""
Reddit社区监控器

监控加密货币相关的Reddit社区（subreddit），分析讨论热度和散户情绪

免费使用Reddit API
"""
import asyncio
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

try:
    import praw
    from praw.models import Submission, Comment
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    logger.warning("praw未安装，Reddit监控将使用模拟数据")


class RedditCommunityMonitor:
    """
    Reddit社区监控器
    
    监控加密货币相关的热门subreddit
    需要免费Reddit API密钥
    """
    
    # 预设的重要社区列表
    IMPORTANT_SUBREDDITS = {
        'CryptoCurrency': {
            'name': '加密货币综合',
            'members': '7.5M+',
            'description': '最大的加密货币社区',
            'keywords': ['Bitcoin', 'Ethereum', 'altcoin', 'trading', 'HODL']
        },
        'Bitcoin': {
            'name': '比特币',
            'members': '6.0M+',
            'description': '比特币官方社区',
            'keywords': ['BTC', 'mining', 'Lightning', 'halving', 'adoption']
        },
        'ethtrader': {
            'name': '以太坊交易',
            'members': '1.5M+',
            'description': '以太坊交易讨论',
            'keywords': ['ETH', 'DeFi', 'gas', 'Layer2', 'staking']
        },
        'wallstreetbets': {
            'name': '华尔街赌场',
            'members': '16M+',
            'description': '散户情绪风向标（包含加密讨论）',
            'keywords': ['crypto', 'Bitcoin', 'moon', 'diamond hands', 'YOLO']
        },
        'CryptoMarkets': {
            'name': '加密市场',
            'members': '2.5M+',
            'description': '加密货币市场分析',
            'keywords': ['trading', 'TA', 'chart', 'support', 'resistance']
        },
        'btc': {
            'name': '比特币技术',
            'members': '400K+',
            'description': '比特币技术讨论',
            'keywords': ['protocol', 'node', 'blockchain', 'development']
        }
    }
    
    # 重要人物关键词
    INFLUENCER_KEYWORDS = {
        'elon_musk': ['Elon Musk', 'ElonMusk', 'Elon', 'Tesla', 'SpaceX'],
        'michael_saylor': ['Michael Saylor', 'Saylor', 'MicroStrategy'],
        'cz': ['CZ', 'Changpeng Zhao', 'Binance CEO'],
        'vitalik': ['Vitalik', 'Vitalik Buterin', 'Ethereum founder'],
        'cathie_wood': ['Cathie Wood', 'ARK Invest', 'ARKK'],
        'gary_gensler': ['Gary Gensler', 'SEC Chair'],
    }
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: str = 'OpenClaw Crypto Monitor',
        subreddits: Optional[List[str]] = None
    ):
        """
        初始化Reddit监控器
        
        Args:
            client_id: Reddit API Client ID（从 https://www.reddit.com/prefs/apps 获取）
            client_secret: Reddit API Client Secret
            user_agent: User Agent字符串
            subreddits: 要监控的社区列表
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        
        # 监控的社区（默认监控所有重要社区）
        if subreddits:
            self.subreddits = subreddits
        else:
            self.subreddits = list(self.IMPORTANT_SUBREDDITS.keys())
        
        # Reddit客户端
        self.reddit = None
        
        # 数据缓存
        self.post_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.analysis_cache: Dict[str, List[Dict[str, Any]]] = {}
        
        logger.info(f"✅ RedditCommunityMonitor 初始化")
        logger.info(f"   监控社区: {len(self.subreddits)}个")
    
    def connect(self):
        """连接到Reddit API"""
        if not PRAW_AVAILABLE:
            logger.warning("PRAW未安装，使用模拟模式")
            return False
        
        if not self.client_id or not self.client_secret:
            logger.warning("未提供Reddit API凭证，使用模拟模式")
            return False
        
        try:
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )
            
            # 测试连接
            self.reddit.user.me()
            
            logger.info("✅ 已连接到Reddit API")
            return True
        except Exception as e:
            logger.error(f"连接Reddit失败: {e}")
            logger.info("将使用模拟模式")
            return False
    
    def fetch_hot_posts(
        self,
        subreddit_name: str,
        limit: int = 25,
        time_filter: str = 'day'
    ) -> List[Dict[str, Any]]:
        """
        获取热门帖子
        
        Args:
            subreddit_name: 社区名称
            limit: 获取数量
            time_filter: 时间过滤 (hour, day, week, month, year, all)
        
        Returns:
            帖子列表
        """
        # 如果没有连接，使用模拟数据
        if not self.reddit or not PRAW_AVAILABLE:
            return self._generate_mock_posts(subreddit_name, limit)
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = []
            
            for submission in subreddit.hot(limit=limit):
                # 计算帖子年龄（小时）
                post_age = (datetime.now() - datetime.fromtimestamp(submission.created_utc)).total_seconds() / 3600
                
                # 只获取最近24小时的帖子
                if post_age > 24:
                    continue
                
                posts.append({
                    'id': submission.id,
                    'subreddit': subreddit_name,
                    'title': submission.title,
                    'text': submission.selftext[:500] if submission.selftext else '',
                    'author': str(submission.author),
                    'score': submission.score,
                    'upvote_ratio': submission.upvote_ratio,
                    'num_comments': submission.num_comments,
                    'created_utc': datetime.fromtimestamp(submission.created_utc).isoformat(),
                    'url': submission.url,
                    'flair': submission.link_flair_text,
                    'timestamp': datetime.now().isoformat()
                })
            
            logger.info(f"获取 r/{subreddit_name} 的 {len(posts)} 个热门帖子")
            return posts
        
        except Exception as e:
            logger.error(f"获取Reddit帖子失败 r/{subreddit_name}: {e}")
            return self._generate_mock_posts(subreddit_name, limit)
    
    def analyze_posts(
        self,
        posts: List[Dict[str, Any]],
        subreddit_name: str
    ) -> Dict[str, Any]:
        """
        分析社区帖子
        
        Args:
            posts: 帖子列表
            subreddit_name: 社区名称
        
        Returns:
            分析结果
        """
        if not posts:
            return {'error': '无帖子数据'}
        
        subreddit_info = self.IMPORTANT_SUBREDDITS.get(subreddit_name, {})
        keywords = subreddit_info.get('keywords', [])
        
        # 1. 关键词统计
        keyword_counts = {kw: 0 for kw in keywords}
        for post in posts:
            title = post.get('title', '').lower()
            text = post.get('text', '').lower()
            combined_text = title + ' ' + text
            
            for kw in keywords:
                if kw.lower() in combined_text:
                    keyword_counts[kw] += 1
        
        # 2. 重要人物提及
        influencer_mentions = {}
        for influencer, keywords_list in self.INFLUENCER_KEYWORDS.items():
            count = 0
            for post in posts:
                title = post.get('title', '')
                text = post.get('text', '')
                combined = title + ' ' + text
                
                if any(kw in combined for kw in keywords_list):
                    count += 1
            
            if count > 0:
                influencer_mentions[influencer] = count
        
        # 3. 情绪分析（基于标题和内容关键词）
        bullish_keywords = [
            'bullish', 'moon', 'pump', 'rally', 'surge', 'breakout', 'ATH', 
            'buy', 'buying', 'accumulate', 'HODL', 'diamond hands', 'to the moon'
        ]
        bearish_keywords = [
            'bearish', 'dump', 'crash', 'drop', 'fall', 'sell', 'selling',
            'correction', 'bubble', 'scam', 'rug pull', 'paper hands'
        ]
        
        bullish_count = 0
        bearish_count = 0
        
        for post in posts:
            title = post.get('title', '').lower()
            text = post.get('text', '').lower()
            combined = title + ' ' + text
            
            bullish_count += sum(1 for kw in bullish_keywords if kw in combined)
            bearish_count += sum(1 for kw in bearish_keywords if kw in combined)
        
        total_sentiment_signals = bullish_count + bearish_count
        if total_sentiment_signals > 0:
            sentiment_score = (bullish_count - bearish_count) / total_sentiment_signals
        else:
            sentiment_score = 0
        
        # 情绪分类
        if sentiment_score > 0.3:
            sentiment_label = 'BULLISH'
        elif sentiment_score > 0.1:
            sentiment_label = 'SLIGHTLY_BULLISH'
        elif sentiment_score < -0.3:
            sentiment_label = 'BEARISH'
        elif sentiment_score < -0.1:
            sentiment_label = 'SLIGHTLY_BEARISH'
        else:
            sentiment_label = 'NEUTRAL'
        
        # 4. 互动热度
        total_score = sum(post.get('score', 0) for post in posts)
        total_comments = sum(post.get('num_comments', 0) for post in posts)
        avg_score = total_score / len(posts) if posts else 0
        avg_comments = total_comments / len(posts) if posts else 0
        avg_upvote_ratio = sum(post.get('upvote_ratio', 0) for post in posts) / len(posts) if posts else 0
        
        # 5. 热门帖子（按得分排序前5）
        top_posts = sorted(
            posts,
            key=lambda x: x.get('score', 0),
            reverse=True
        )[:5]
        
        # 6. 讨论热度趋势（如果有缓存）
        trend = 'UNKNOWN'
        if subreddit_name in self.analysis_cache and self.analysis_cache[subreddit_name]:
            last_analysis = self.analysis_cache[subreddit_name][-1]
            last_avg_score = last_analysis.get('engagement', {}).get('avg_score', 0)
            
            if avg_score > last_avg_score * 1.2:
                trend = 'RISING'
            elif avg_score < last_avg_score * 0.8:
                trend = 'FALLING'
            else:
                trend = 'STABLE'
        
        analysis = {
            'subreddit': subreddit_name,
            'subreddit_name': subreddit_info.get('name', subreddit_name),
            'members': subreddit_info.get('members', 'Unknown'),
            'timestamp': datetime.now().isoformat(),
            'post_count': len(posts),
            'keyword_mentions': keyword_counts,
            'influencer_mentions': influencer_mentions,
            'sentiment': {
                'score': sentiment_score,
                'label': sentiment_label,
                'bullish_signals': bullish_count,
                'bearish_signals': bearish_count
            },
            'engagement': {
                'total_score': total_score,
                'total_comments': total_comments,
                'avg_score': avg_score,
                'avg_comments': avg_comments,
                'avg_upvote_ratio': avg_upvote_ratio
            },
            'trend': trend,
            'top_posts': [
                {
                    'title': post['title'],
                    'score': post.get('score', 0),
                    'comments': post.get('num_comments', 0),
                    'upvote_ratio': post.get('upvote_ratio', 0)
                }
                for post in top_posts
            ]
        }
        
        # 缓存结果
        if subreddit_name not in self.post_cache:
            self.post_cache[subreddit_name] = []
        if subreddit_name not in self.analysis_cache:
            self.analysis_cache[subreddit_name] = []
        
        self.post_cache[subreddit_name].extend(posts)
        self.analysis_cache[subreddit_name].append(analysis)
        
        # 限制缓存大小
        if len(self.post_cache[subreddit_name]) > 200:
            self.post_cache[subreddit_name] = self.post_cache[subreddit_name][-200:]
        if len(self.analysis_cache[subreddit_name]) > 100:
            self.analysis_cache[subreddit_name] = self.analysis_cache[subreddit_name][-100:]
        
        return analysis
    
    def monitor_all_subreddits(
        self,
        limit_per_subreddit: int = 25
    ) -> List[Dict[str, Any]]:
        """
        监控所有配置的社区
        
        Args:
            limit_per_subreddit: 每个社区获取帖子数
        
        Returns:
            所有社区的分析结果
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🔄 开始Reddit社区监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*70}")
        
        results = []
        
        for subreddit in self.subreddits:
            try:
                # 获取帖子
                posts = self.fetch_hot_posts(subreddit, limit=limit_per_subreddit)
                
                # 分析帖子
                if posts:
                    analysis = self.analyze_posts(posts, subreddit)
                    results.append(analysis)
                    
                    # 打印摘要
                    sentiment = analysis.get('sentiment', {})
                    engagement = analysis.get('engagement', {})
                    
                    logger.info(f"📊 r/{subreddit}: {analysis['post_count']}个帖子, "
                              f"情绪={sentiment['label']}, "
                              f"平均{engagement['avg_score']:.0f}分/{engagement['avg_comments']:.0f}评论")
                
                # 避免速率限制
                import time
                time.sleep(2)
            
            except Exception as e:
                logger.error(f"监控社区失败 r/{subreddit}: {e}")
        
        logger.info(f"{'='*70}")
        logger.info(f"✅ Reddit监控完成，共分析 {len(results)} 个社区")
        logger.info(f"{'='*70}\n")
        
        return results
    
    def _generate_mock_posts(self, subreddit: str, limit: int) -> List[Dict[str, Any]]:
        """生成模拟帖子（用于测试）"""
        import random
        
        mock_titles = [
            "Bitcoin just broke $67k! Is this the start of the bull run? 🚀",
            "Ethereum gas fees are finally down to reasonable levels",
            "PSA: Don't FOMO into altcoins at ATH, learned the hard way",
            "Michael Saylor's MicroStrategy buys another 500 BTC",
            "SEC delays Bitcoin ETF decision again - thoughts?",
            "Vitalik's new Ethereum roadmap looks promising",
            "Chart analysis: BTC might test $70k resistance soon",
            "Just started DCA into Bitcoin, wish me luck!",
            "Warning: New scam targeting crypto holders on social media",
            "Unpopular opinion: Most altcoins won't survive the next bear market"
        ]
        
        posts = []
        base_time = datetime.now()
        
        for i in range(min(limit, len(mock_titles) * 2)):
            posts.append({
                'id': f'mock_{i}',
                'subreddit': subreddit,
                'title': random.choice(mock_titles),
                'text': 'Mock post content for testing purposes.',
                'author': f'user{random.randint(1000, 9999)}',
                'score': random.randint(50, 5000),
                'upvote_ratio': random.uniform(0.7, 0.98),
                'num_comments': random.randint(10, 500),
                'created_utc': (base_time - timedelta(hours=random.randint(1, 23))).isoformat(),
                'url': f'https://reddit.com/r/{subreddit}/mock_{i}',
                'flair': random.choice(['Discussion', 'News', 'Analysis', 'Comedy']),
                'timestamp': datetime.now().isoformat()
            })
        
        return posts
    
    def get_summary_report(self, analyses: List[Dict[str, Any]]) -> str:
        """
        生成Reddit监控摘要报告
        
        Args:
            analyses: 社区分析结果列表
        
        Returns:
            报告文本
        """
        if not analyses:
            return "无Reddit监控数据"
        
        report = []
        report.append("\n" + "="*70)
        report.append("🗣️  Reddit社区监控报告")
        report.append("="*70)
        report.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"监控社区: {len(analyses)}个")
        report.append("")
        
        # 整体情绪统计
        total_bullish = sum(1 for a in analyses if a.get('sentiment', {}).get('label') in ['BULLISH', 'SLIGHTLY_BULLISH'])
        total_bearish = sum(1 for a in analyses if a.get('sentiment', {}).get('label') in ['BEARISH', 'SLIGHTLY_BEARISH'])
        total_neutral = len(analyses) - total_bullish - total_bearish
        
        report.append("【整体情绪】")
        report.append(f"  看涨社区: {total_bullish}个")
        report.append(f"  看跌社区: {total_bearish}个")
        report.append(f"  中性社区: {total_neutral}个")
        report.append("")
        
        # 重要人物提及汇总
        all_influencer_mentions = {}
        for analysis in analyses:
            for influencer, count in analysis.get('influencer_mentions', {}).items():
                if influencer not in all_influencer_mentions:
                    all_influencer_mentions[influencer] = 0
                all_influencer_mentions[influencer] += count
        
        if all_influencer_mentions:
            report.append("【重要人物提及】")
            for influencer, count in sorted(all_influencer_mentions.items(), key=lambda x: x[1], reverse=True):
                name = influencer.replace('_', ' ').title()
                report.append(f"  {name}: {count}次")
            report.append("")
        
        # 各社区详情
        report.append("【社区详情】")
        for analysis in analyses:
            subreddit_name = analysis.get('subreddit_name', analysis['subreddit'])
            post_count = analysis['post_count']
            sentiment = analysis.get('sentiment', {})
            engagement = analysis.get('engagement', {})
            
            report.append(f"\n  📊 {subreddit_name} (r/{analysis['subreddit']})")
            report.append(f"     成员: {analysis.get('members', 'Unknown')}")
            report.append(f"     帖子数: {post_count}")
            report.append(f"     情绪: {sentiment.get('label', 'UNKNOWN')} (得分: {sentiment.get('score', 0):.2f})")
            report.append(f"     互动: 平均{engagement.get('avg_score', 0):.0f}分, {engagement.get('avg_comments', 0):.0f}评论")
            report.append(f"     支持率: {engagement.get('avg_upvote_ratio', 0)*100:.1f}%")
            report.append(f"     热度趋势: {analysis.get('trend', 'UNKNOWN')}")
            
            # 关键词提及
            keyword_mentions = analysis.get('keyword_mentions', {})
            top_keywords = sorted(keyword_mentions.items(), key=lambda x: x[1], reverse=True)[:3]
            if top_keywords:
                keywords_str = ', '.join([f"{kw}({count})" for kw, count in top_keywords if count > 0])
                if keywords_str:
                    report.append(f"     热词: {keywords_str}")
        
        report.append("\n" + "="*70)
        
        return '\n'.join(report)
