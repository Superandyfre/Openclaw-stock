"""
Telegram公开频道监控器

监控重要人物/机构的Telegram公开频道，获取实时消息和市场情绪

免费使用，无API费用
"""
import asyncio
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

try:
    from telethon import TelegramClient
    from telethon.tl.types import Message
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    logger.warning("telethon未安装，Telegram监控将使用模拟数据")


class TelegramChannelMonitor:
    """
    Telegram公开频道监控器
    
    监控加密货币相关的重要Telegram频道
    完全免费，无需API密钥（仅需Telegram账号）
    """
    
    # 预设的重要频道列表
    IMPORTANT_CHANNELS = {
        'whale_alert': {
            'username': 'whale_alert',
            'name': '巨鲸转账告警',
            'description': '实时追踪大额加密货币转账',
            'keywords': ['BTC', 'ETH', 'USDT', 'transferred', 'whale']
        },
        'cointelegraph': {
            'username': 'cointelegraph',
            'name': 'CoinTelegraph新闻',
            'description': '加密货币新闻快讯',
            'keywords': ['Bitcoin', 'Ethereum', 'crypto', 'market', 'price']
        },
        'coindesk': {
            'username': 'CoinDesk',
            'name': 'CoinDesk新闻',
            'description': '加密货币行业新闻',
            'keywords': ['Bitcoin', 'Ethereum', 'regulation', 'adoption']
        },
        'binance_announcements': {
            'username': 'binance_announcements',
            'name': 'Binance官方公告',
            'description': 'Binance交易所官方公告',
            'keywords': ['listing', 'delisting', 'maintenance', 'promotion']
        },
        'crypto_news_official': {
            'username': 'crypto_news_official',
            'name': '加密新闻聚合',
            'description': '加密货币新闻聚合频道',
            'keywords': ['Bitcoin', 'Ethereum', 'altcoin', 'DeFi', 'NFT']
        }
    }
    
    # 重要人物关键词（用于识别提及）
    INFLUENCER_KEYWORDS = {
        'elon_musk': ['Elon Musk', 'ElonMusk', '@elonmusk', 'Tesla', 'SpaceX'],
        'michael_saylor': ['Michael Saylor', 'MicroStrategy', '@saylor'],
        'cz': ['CZ', 'Changpeng Zhao', 'Binance CEO', '@cz_binance'],
        'vitalik': ['Vitalik', 'Vitalik Buterin', 'Ethereum founder'],
        'cathie_wood': ['Cathie Wood', 'ARK Invest', 'ARKK'],
        'gary_gensler': ['Gary Gensler', 'SEC Chair', 'SEC'],
        'christine_lagarde': ['Christine Lagarde', 'ECB', 'European Central Bank']
    }
    
    def __init__(
        self,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        phone: Optional[str] = None,
        session_name: str = 'telegram_monitor',
        channels: Optional[List[str]] = None
    ):
        """
        初始化Telegram监控器
        
        Args:
            api_id: Telegram API ID（从 https://my.telegram.org 获取）
            api_hash: Telegram API Hash
            phone: 手机号（用于首次登录）
            session_name: 会话文件名
            channels: 要监控的频道列表（username）
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_name = session_name
        
        # 监控的频道（默认监控所有重要频道）
        if channels:
            self.channels = channels
        else:
            self.channels = list(self.IMPORTANT_CHANNELS.keys())
        
        # 消息缓存
        self.message_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.last_check_time: Dict[str, datetime] = {}
        
        # Telegram客户端
        self.client = None
        
        logger.info(f"✅ TelegramChannelMonitor 初始化")
        logger.info(f"   监控频道: {len(self.channels)}个")
    
    async def connect(self):
        """连接到Telegram"""
        if not TELETHON_AVAILABLE:
            logger.warning("Telethon未安装，使用模拟模式")
            return False
        
        if not self.api_id or not self.api_hash:
            logger.warning("未提供Telegram API凭证，使用模拟模式")
            return False
        
        try:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.start(phone=self.phone)
            logger.info("✅ 已连接到Telegram")
            return True
        except Exception as e:
            logger.error(f"连接Telegram失败: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self.client:
            await self.client.disconnect()
            logger.info("已断开Telegram连接")
    
    async def fetch_channel_messages(
        self,
        channel_username: str,
        limit: int = 20,
        since_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """
        获取频道最新消息
        
        Args:
            channel_username: 频道用户名（不含@）
            limit: 获取消息数量
            since_minutes: 获取多少分钟内的消息
        
        Returns:
            消息列表
        """
        # 如果没有连接，使用模拟数据
        if not self.client or not TELETHON_AVAILABLE:
            return self._generate_mock_messages(channel_username, limit)
        
        try:
            # 获取频道实体
            channel = await self.client.get_entity(channel_username)
            
            # 获取消息
            messages = []
            since_time = datetime.now() - timedelta(minutes=since_minutes)
            
            async for message in self.client.iter_messages(channel, limit=limit):
                # 只获取指定时间内的消息
                if message.date.replace(tzinfo=None) < since_time:
                    break
                
                if message.text:
                    messages.append({
                        'id': message.id,
                        'channel': channel_username,
                        'text': message.text,
                        'date': message.date.isoformat(),
                        'views': message.views or 0,
                        'forwards': message.forwards or 0,
                        'timestamp': datetime.now().isoformat()
                    })
            
            logger.info(f"获取 @{channel_username} 的 {len(messages)} 条消息")
            return messages
        
        except Exception as e:
            logger.error(f"获取频道消息失败 @{channel_username}: {e}")
            return self._generate_mock_messages(channel_username, limit)
    
    def analyze_messages(
        self,
        messages: List[Dict[str, Any]],
        channel_username: str
    ) -> Dict[str, Any]:
        """
        分析频道消息
        
        Args:
            messages: 消息列表
            channel_username: 频道用户名
        
        Returns:
            分析结果
        """
        if not messages:
            return {'error': '无消息数据'}
        
        channel_info = self.IMPORTANT_CHANNELS.get(channel_username, {})
        keywords = channel_info.get('keywords', [])
        
        # 1. 关键词匹配统计
        keyword_counts = {kw: 0 for kw in keywords}
        for msg in messages:
            text = msg.get('text', '').lower()
            for kw in keywords:
                if kw.lower() in text:
                    keyword_counts[kw] += 1
        
        # 2. 重要人物提及检测
        influencer_mentions = {}
        for influencer, keywords_list in self.INFLUENCER_KEYWORDS.items():
            count = 0
            for msg in messages:
                text = msg.get('text', '')
                if any(kw in text for kw in keywords_list):
                    count += 1
            if count > 0:
                influencer_mentions[influencer] = count
        
        # 3. 情绪分析（简单基于关键词）
        positive_keywords = ['bullish', 'moon', 'pump', 'rally', 'surge', 'breakout', 'ATH', 'adoption']
        negative_keywords = ['bearish', 'dump', 'crash', 'drop', 'fall', 'sell-off', 'correction', 'regulation']
        
        positive_count = 0
        negative_count = 0
        
        for msg in messages:
            text = msg.get('text', '').lower()
            positive_count += sum(1 for kw in positive_keywords if kw in text)
            negative_count += sum(1 for kw in negative_keywords if kw in text)
        
        total_sentiment_signals = positive_count + negative_count
        if total_sentiment_signals > 0:
            sentiment_score = (positive_count - negative_count) / total_sentiment_signals
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
        total_views = sum(msg.get('views', 0) for msg in messages)
        total_forwards = sum(msg.get('forwards', 0) for msg in messages)
        avg_views = total_views / len(messages) if messages else 0
        avg_forwards = total_forwards / len(messages) if messages else 0
        
        # 5. 热门消息（转发数最多的前3条）
        top_messages = sorted(
            messages,
            key=lambda x: x.get('forwards', 0),
            reverse=True
        )[:3]
        
        analysis = {
            'channel': channel_username,
            'channel_name': channel_info.get('name', channel_username),
            'timestamp': datetime.now().isoformat(),
            'message_count': len(messages),
            'keyword_mentions': keyword_counts,
            'influencer_mentions': influencer_mentions,
            'sentiment': {
                'score': sentiment_score,
                'label': sentiment_label,
                'positive_signals': positive_count,
                'negative_signals': negative_count
            },
            'engagement': {
                'total_views': total_views,
                'total_forwards': total_forwards,
                'avg_views': avg_views,
                'avg_forwards': avg_forwards
            },
            'top_messages': [
                {
                    'text': msg['text'][:200] + '...' if len(msg['text']) > 200 else msg['text'],
                    'views': msg.get('views', 0),
                    'forwards': msg.get('forwards', 0)
                }
                for msg in top_messages
            ]
        }
        
        # 缓存结果
        if channel_username not in self.message_cache:
            self.message_cache[channel_username] = []
        
        self.message_cache[channel_username].append(analysis)
        
        # 限制缓存大小
        if len(self.message_cache[channel_username]) > 100:
            self.message_cache[channel_username] = self.message_cache[channel_username][-100:]
        
        return analysis
    
    async def monitor_all_channels(
        self,
        limit_per_channel: int = 20,
        since_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """
        监控所有配置的频道
        
        Args:
            limit_per_channel: 每个频道获取消息数
            since_minutes: 获取多少分钟内的消息
        
        Returns:
            所有频道的分析结果
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"🔄 开始Telegram频道监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*70}")
        
        results = []
        
        for channel in self.channels:
            try:
                # 获取消息
                messages = await self.fetch_channel_messages(
                    channel,
                    limit=limit_per_channel,
                    since_minutes=since_minutes
                )
                
                # 分析消息
                if messages:
                    analysis = self.analyze_messages(messages, channel)
                    results.append(analysis)
                    
                    # 打印摘要
                    sentiment = analysis.get('sentiment', {})
                    logger.info(f"📢 @{channel}: {analysis['message_count']}条消息, "
                              f"情绪={sentiment['label']}, "
                              f"互动={analysis['engagement']['avg_views']:.0f}浏览")
                
                # 避免速率限制
                await asyncio.sleep(2)
            
            except Exception as e:
                logger.error(f"监控频道失败 @{channel}: {e}")
        
        logger.info(f"{'='*70}")
        logger.info(f"✅ Telegram监控完成，共分析 {len(results)} 个频道")
        logger.info(f"{'='*70}\n")
        
        return results
    
    def _generate_mock_messages(self, channel: str, limit: int) -> List[Dict[str, Any]]:
        """生成模拟消息（用于测试）"""
        import random
        
        mock_texts = [
            "Bitcoin surges past $67,000 as institutional adoption accelerates 🚀",
            "Ethereum network upgrade scheduled for next week - major scalability improvements expected",
            "Whale Alert: 1,000 BTC transferred from unknown wallet to Binance",
            "SEC delays decision on Bitcoin ETF approval - market sentiment turns cautious",
            "Vitalik Buterin presents new Ethereum roadmap at developer conference",
            "Michael Saylor's MicroStrategy purchases additional 500 BTC",
            "Crypto market sees $1B in liquidations as Bitcoin drops 5% in hours",
            "New DeFi protocol launches with innovative yield farming mechanism",
            "Binance announces new trading pairs and zero-fee promotion",
            "Regulatory concerns mount as governments discuss crypto taxation"
        ]
        
        messages = []
        base_time = datetime.now()
        
        for i in range(min(limit, len(mock_texts))):
            messages.append({
                'id': 1000 + i,
                'channel': channel,
                'text': random.choice(mock_texts),
                'date': (base_time - timedelta(minutes=i*5)).isoformat(),
                'views': random.randint(1000, 50000),
                'forwards': random.randint(10, 500),
                'timestamp': datetime.now().isoformat()
            })
        
        return messages
    
    def get_summary_report(self, analyses: List[Dict[str, Any]]) -> str:
        """
        生成Telegram监控摘要报告
        
        Args:
            analyses: 频道分析结果列表
        
        Returns:
            报告文本
        """
        if not analyses:
            return "无Telegram监控数据"
        
        report = []
        report.append("\n" + "="*70)
        report.append("📱 Telegram频道监控报告")
        report.append("="*70)
        report.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"监控频道: {len(analyses)}个")
        report.append("")
        
        # 整体情绪统计
        total_bullish = sum(1 for a in analyses if a.get('sentiment', {}).get('label') in ['BULLISH', 'SLIGHTLY_BULLISH'])
        total_bearish = sum(1 for a in analyses if a.get('sentiment', {}).get('label') in ['BEARISH', 'SLIGHTLY_BEARISH'])
        total_neutral = len(analyses) - total_bullish - total_bearish
        
        report.append("【整体情绪】")
        report.append(f"  看涨: {total_bullish}个频道")
        report.append(f"  看跌: {total_bearish}个频道")
        report.append(f"  中性: {total_neutral}个频道")
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
        
        # 各频道详情
        report.append("【频道详情】")
        for analysis in analyses:
            channel_name = analysis.get('channel_name', analysis['channel'])
            msg_count = analysis['message_count']
            sentiment = analysis.get('sentiment', {})
            engagement = analysis.get('engagement', {})
            
            report.append(f"\n  📢 {channel_name} (@{analysis['channel']})")
            report.append(f"     消息数: {msg_count}")
            report.append(f"     情绪: {sentiment.get('label', 'UNKNOWN')} (得分: {sentiment.get('score', 0):.2f})")
            report.append(f"     互动: 平均{engagement.get('avg_views', 0):.0f}浏览, {engagement.get('avg_forwards', 0):.0f}转发")
            
            # 关键词提及
            keyword_mentions = analysis.get('keyword_mentions', {})
            top_keywords = sorted(keyword_mentions.items(), key=lambda x: x[1], reverse=True)[:3]
            if top_keywords:
                keywords_str = ', '.join([f"{kw}({count})" for kw, count in top_keywords if count > 0])
                if keywords_str:
                    report.append(f"     热词: {keywords_str}")
        
        report.append("\n" + "="*70)
        
        return '\n'.join(report)
