"""
社交媒体综合监控系统

整合Telegram频道、Reddit社区、RSS订阅三大数据源
每10分钟自动监控，生成综合情绪报告
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
from pathlib import Path
import json

try:
    from openclaw.skills.data_collection.telegram_channel_monitor import TelegramChannelMonitor
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("Telegram监控模块未找到")

try:
    from openclaw.skills.data_collection.reddit_community_monitor import RedditCommunityMonitor
    REDDIT_AVAILABLE = True
except ImportError:
    REDDIT_AVAILABLE = False
    logger.warning("Reddit监控模块未找到")

try:
    from openclaw.skills.data_collection.influencer_rss_monitor import InfluencerRSSMonitor
    RSS_AVAILABLE = True
except ImportError:
    RSS_AVAILABLE = False
    logger.warning("RSS监控模块未找到")


class SocialMediaMonitor:
    """
    社交媒体综合监控系统
    
    整合三大数据源：
    1. Telegram公开频道
    2. Reddit社区
    3. 重要人物RSS订阅
    
    每10分钟自动监控，生成综合情绪分析
    """
    
    def __init__(
        self,
        # Telegram配置
        telegram_api_id: Optional[int] = None,
        telegram_api_hash: Optional[str] = None,
        telegram_phone: Optional[str] = None,
        
        # Reddit配置
        reddit_client_id: Optional[str] = None,
        reddit_client_secret: Optional[str] = None,
        
        # 监控配置
        check_interval_minutes: int = 10,
        save_reports: bool = True,
        reports_dir: str = './reports/social_media'
    ):
        """
        初始化社交媒体监控系统
        
        Args:
            telegram_api_id: Telegram API ID（可选）
            telegram_api_hash: Telegram API Hash（可选）
            telegram_phone: Telegram手机号（可选）
            reddit_client_id: Reddit API Client ID（可选）
            reddit_client_secret: Reddit API Client Secret（可选）
            check_interval_minutes: 检查间隔（分钟）
            save_reports: 是否保存报告
            reports_dir: 报告保存目录
        """
        self.check_interval = check_interval_minutes
        self.save_reports = save_reports
        self.reports_dir = reports_dir
        
        # 初始化三个监控模块
        self.telegram_monitor = None
        self.reddit_monitor = None
        self.rss_monitor = None
        
        if TELEGRAM_AVAILABLE:
            self.telegram_monitor = TelegramChannelMonitor(
                api_id=telegram_api_id,
                api_hash=telegram_api_hash,
                phone=telegram_phone
            )
        
        if REDDIT_AVAILABLE:
            self.reddit_monitor = RedditCommunityMonitor(
                client_id=reddit_client_id,
                client_secret=reddit_client_secret
            )
        
        if RSS_AVAILABLE:
            self.rss_monitor = InfluencerRSSMonitor()
        
        # 历史数据
        self.monitor_history: List[Dict[str, Any]] = []
        
        # 创建报告目录
        if self.save_reports:
            Path(self.reports_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✅ SocialMediaMonitor 初始化成功")
        logger.info(f"   监控间隔: {check_interval_minutes}分钟")
        logger.info(f"   已启用模块: Telegram={TELEGRAM_AVAILABLE}, "
                   f"Reddit={REDDIT_AVAILABLE}, RSS={RSS_AVAILABLE}")
    
    async def check_all_sources(self) -> Dict[str, Any]:
        """
        检查所有社交媒体数据源
        
        Returns:
            综合分析结果
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🔄 开始社交媒体综合监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*80}\n")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'telegram': None,
            'reddit': None,
            'rss': None,
            '综合分析': {}
        }
        
        # 1. Telegram频道监控
        if self.telegram_monitor:
            try:
                logger.info("📱 监控Telegram频道...")
                telegram_results = await self.telegram_monitor.monitor_all_channels(
                    limit_per_channel=20,
                    since_minutes=self.check_interval
                )
                results['telegram'] = telegram_results
                logger.info(f"✅ Telegram监控完成: {len(telegram_results)}个频道")
            except Exception as e:
                logger.error(f"Telegram监控失败: {e}")
        
        # 2. Reddit社区监控
        if self.reddit_monitor:
            try:
                logger.info("\n🗣️  监控Reddit社区...")
                reddit_results = self.reddit_monitor.monitor_all_subreddits(
                    limit_per_subreddit=25
                )
                results['reddit'] = reddit_results
                logger.info(f"✅ Reddit监控完成: {len(reddit_results)}个社区")
            except Exception as e:
                logger.error(f"Reddit监控失败: {e}")
        
        # 3. RSS订阅监控
        if self.rss_monitor:
            try:
                logger.info("\n📚 监控RSS订阅...")
                rss_results = self.rss_monitor.monitor_all_feeds(
                    since_hours=int(self.check_interval / 60 * 24)  # 转换为小时
                )
                results['rss'] = rss_results
                logger.info(f"✅ RSS监控完成: {len(rss_results)}个订阅源")
            except Exception as e:
                logger.error(f"RSS监控失败: {e}")
        
        # 4. 生成综合分析
        comprehensive_analysis = self._generate_comprehensive_analysis(results)
        results['comprehensive_analysis'] = comprehensive_analysis
        
        # 5. 记录历史
        self.monitor_history.append(results)
        if len(self.monitor_history) > 100:
            self.monitor_history = self.monitor_history[-100:]
        
        # 6. 保存报告
        if self.save_reports:
            self._save_report(results)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ 社交媒体监控完成")
        logger.info(f"{'='*80}\n")
        
        return results
    
    def _generate_comprehensive_analysis(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成综合分析
        
        Args:
            results: 各平台监控结果
        
        Returns:
            综合分析结果
        """
        logger.info("\n📊 生成综合分析...")
        
        # 整体情绪统计
        all_sentiments = []
        
        # Telegram情绪
        if results.get('telegram'):
            for analysis in results['telegram']:
                sentiment = analysis.get('sentiment', {})
                if sentiment.get('label'):
                    all_sentiments.append({
                        'source': 'telegram',
                        'label': sentiment['label'],
                        'score': sentiment.get('score', 0)
                    })
        
        # Reddit情绪
        if results.get('reddit'):
            for analysis in results['reddit']:
                sentiment = analysis.get('sentiment', {})
                if sentiment.get('label'):
                    all_sentiments.append({
                        'source': 'reddit',
                        'label': sentiment['label'],
                        'score': sentiment.get('score', 0)
                    })
        
        # RSS情绪
        if results.get('rss'):
            for analysis in results['rss']:
                sentiment = analysis.get('sentiment', {})
                if sentiment.get('label'):
                    # RSS使用不同的标签，需要转换
                    label_map = {
                        'POSITIVE': 'BULLISH',
                        'SLIGHTLY_POSITIVE': 'SLIGHTLY_BULLISH',
                        'NEGATIVE': 'BEARISH',
                        'SLIGHTLY_NEGATIVE': 'SLIGHTLY_BEARISH',
                        'NEUTRAL': 'NEUTRAL'
                    }
                    all_sentiments.append({
                        'source': 'rss',
                        'label': label_map.get(sentiment['label'], 'NEUTRAL'),
                        'score': sentiment.get('score', 0)
                    })
        
        # 计算整体情绪
        if all_sentiments:
            avg_sentiment_score = sum(s['score'] for s in all_sentiments) / len(all_sentiments)
            
            bullish_count = sum(1 for s in all_sentiments if 'BULLISH' in s['label'])
            bearish_count = sum(1 for s in all_sentiments if 'BEARISH' in s['label'])
            neutral_count = len(all_sentiments) - bullish_count - bearish_count
            
            # 整体标签
            if avg_sentiment_score > 0.2:
                overall_sentiment = 'BULLISH'
            elif avg_sentiment_score > 0.05:
                overall_sentiment = 'SLIGHTLY_BULLISH'
            elif avg_sentiment_score < -0.2:
                overall_sentiment = 'BEARISH'
            elif avg_sentiment_score < -0.05:
                overall_sentiment = 'SLIGHTLY_BEARISH'
            else:
                overall_sentiment = 'NEUTRAL'
        else:
            avg_sentiment_score = 0
            bullish_count = 0
            bearish_count = 0
            neutral_count = 0
            overall_sentiment = 'UNKNOWN'
        
        # 重要人物提及汇总
        all_influencer_mentions = {}
        
        for source in ['telegram', 'reddit']:
            if results.get(source):
                for analysis in results[source]:
                    for influencer, count in analysis.get('influencer_mentions', {}).items():
                        if influencer not in all_influencer_mentions:
                            all_influencer_mentions[influencer] = {'total': 0, 'sources': {}}
                        all_influencer_mentions[influencer]['total'] += count
                        all_influencer_mentions[influencer]['sources'][source] = count
        
        # 数据源统计
        sources_active = {
            'telegram': len(results.get('telegram', [])),
            'reddit': len(results.get('reddit', [])),
            'rss': len(results.get('rss', []))
        }
        
        comprehensive = {
            'timestamp': datetime.now().isoformat(),
            'overall_sentiment': {
                'label': overall_sentiment,
                'score': avg_sentiment_score,
                'distribution': {
                    'bullish': bullish_count,
                    'bearish': bearish_count,
                    'neutral': neutral_count
                }
            },
            'influencer_mentions': dict(sorted(
                all_influencer_mentions.items(),
                key=lambda x: x[1]['total'],
                reverse=True
            )),
            'sources_active': sources_active,
            'total_data_points': len(all_sentiments)
        }
        
        logger.info(f"整体情绪: {overall_sentiment} (得分: {avg_sentiment_score:.2f})")
        logger.info(f"数据点: {len(all_sentiments)}个 (看涨{bullish_count}, 看跌{bearish_count}, 中性{neutral_count})")
        
        return comprehensive
    
    def _save_report(self, results: Dict[str, Any]):
        """保存监控报告"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            
            # JSON格式
            json_path = Path(self.reports_dir) / f'social_media_report_{timestamp}.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            # 文本格式
            txt_path = Path(self.reports_dir) / f'social_media_report_{timestamp}.txt'
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(self.get_summary_report(results))
            
            logger.info(f"📄 报告已保存: {txt_path}")
        
        except Exception as e:
            logger.error(f"保存报告失败: {e}")
    
    def get_summary_report(self, results: Dict[str, Any]) -> str:
        """
        生成综合摘要报告
        
        Args:
            results: 监控结果
        
        Returns:
            报告文本
        """
        report = []
        report.append("="*80)
        report.append("🌐 社交媒体综合监控报告")
        report.append("="*80)
        report.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # 综合分析
        comp = results.get('comprehensive_analysis', {})
        if comp:
            overall = comp.get('overall_sentiment', {})
            report.append("【综合情绪分析】")
            report.append(f"  整体情绪: {overall.get('label', 'UNKNOWN')}")
            report.append(f"  情绪得分: {overall.get('score', 0):.2f}")
            
            dist = overall.get('distribution', {})
            report.append(f"  数据分布:")
            report.append(f"    - 看涨: {dist.get('bullish', 0)}个数据点")
            report.append(f"    - 看跌: {dist.get('bearish', 0)}个数据点")
            report.append(f"    - 中性: {dist.get('neutral', 0)}个数据点")
            report.append("")
            
            # 重要人物提及
            influencers = comp.get('influencer_mentions', {})
            if influencers:
                report.append("【重要人物提及Top 5】")
                for i, (name, data) in enumerate(list(influencers.items())[:5], 1):
                    display_name = name.replace('_', ' ').title()
                    report.append(f"  {i}. {display_name}: {data['total']}次")
                    sources = ', '.join([f"{src}({cnt})" for src, cnt in data['sources'].items()])
                    report.append(f"     来源: {sources}")
                report.append("")
            
            # 数据源统计
            sources = comp.get('sources_active', {})
            report.append("【数据源统计】")
            report.append(f"  Telegram频道: {sources.get('telegram', 0)}个")
            report.append(f"  Reddit社区: {sources.get('reddit', 0)}个")
            report.append(f"  RSS订阅源: {sources.get('rss', 0)}个")
            report.append(f"  总数据点: {comp.get('total_data_points', 0)}个")
            report.append("")
        
        # Telegram详情
        if results.get('telegram') and self.telegram_monitor:
            report.append(self.telegram_monitor.get_summary_report(results['telegram']))
        
        # Reddit详情
        if results.get('reddit') and self.reddit_monitor:
            report.append(self.reddit_monitor.get_summary_report(results['reddit']))
        
        # RSS详情
        if results.get('rss') and self.rss_monitor:
            report.append(self.rss_monitor.get_summary_report(results['rss']))
        
        report.append("\n" + "="*80)
        
        return '\n'.join(report)
    
    async def run_monitoring_loop(self, duration_hours: Optional[int] = None):
        """
        运行监控循环
        
        Args:
            duration_hours: 运行时长（小时），None表示无限运行
        """
        logger.info(f"🚀 启动社交媒体监控循环")
        logger.info(f"   监控间隔: {self.check_interval}分钟")
        if duration_hours:
            logger.info(f"   运行时长: {duration_hours}小时")
        else:
            logger.info(f"   运行模式: 持续运行")
        
        start_time = datetime.now()
        check_count = 0
        
        # 连接Telegram（如果配置了）
        if self.telegram_monitor:
            await self.telegram_monitor.connect()
        
        # 连接Reddit（如果配置了）
        if self.reddit_monitor:
            self.reddit_monitor.connect()
        
        try:
            while True:
                check_count += 1
                logger.info(f"\n{'#'*80}")
                logger.info(f"第 {check_count} 次检查")
                logger.info(f"{'#'*80}\n")
                
                # 执行监控
                results = await self.check_all_sources()
                
                # 打印摘要
                print(self.get_summary_report(results))
                
                # 检查是否超过运行时长
                if duration_hours:
                    elapsed_hours = (datetime.now() - start_time).total_seconds() / 3600
                    if elapsed_hours >= duration_hours:
                        logger.info(f"✅ 已运行 {elapsed_hours:.1f} 小时，监控结束")
                        break
                
                # 等待下一次检查
                logger.info(f"⏰ 等待 {self.check_interval} 分钟后进行下一次检查...")
                await asyncio.sleep(self.check_interval * 60)
        
        except KeyboardInterrupt:
            logger.info("\n⚠️  收到中断信号，停止监控")
        
        finally:
            # 断开连接
            if self.telegram_monitor:
                await self.telegram_monitor.disconnect()
            
            logger.info(f"✅ 监控循环结束，共执行 {check_count} 次检查")


# 演示函数
async def demo_social_media_monitor():
    """社交媒体监控演示"""
    print("\n" + "="*80)
    print("🌐 社交媒体综合监控系统演示")
    print("="*80)
    print("\n注意: 需要配置API密钥才能获取真实数据")
    print("当前使用模拟数据进行演示\n")
    
    # 初始化监控器（不提供API密钥，使用模拟数据）
    monitor = SocialMediaMonitor(
        check_interval_minutes=10,
        save_reports=True,
        reports_dir='./reports/social_media'
    )
    
    # 单次检查演示
    print("【演示模式】执行单次监控检查...\n")
    results = await monitor.check_all_sources()
    
    # 打印报告
    print(monitor.get_summary_report(results))
    
    print("\n提示: 要启用真实数据监控，请配置:")
    print("  - Telegram: API ID和API Hash (https://my.telegram.org)")
    print("  - Reddit: Client ID和Client Secret (https://www.reddit.com/prefs/apps)")
    print("  - RSS: 无需配置，自动使用")
    print("\n使用方法:")
    print("  await monitor.run_monitoring_loop(duration_hours=1)  # 运行1小时")
    print("  await monitor.run_monitoring_loop()  # 持续运行")


if __name__ == '__main__':
    asyncio.run(demo_social_media_monitor())
