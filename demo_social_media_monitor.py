"""
社交媒体监控演示

展示如何使用社交媒体综合监控系统
每10分钟自动监控Telegram, Reddit, RSS三大数据源
"""
import asyncio
import os
from loguru import logger
from dotenv import load_dotenv

# 加载 .env 配置
load_dotenv()

from openclaw.skills.monitoring.social_media_monitor import SocialMediaMonitor


async def demo_single_check():
    """演示：单次检查"""
    print("\n" + "="*80)
    print("📊 演示1: 单次社交媒体监控检查")
    print("="*80 + "\n")
    
    # 从环境变量读取配置
    telegram_api_id = os.getenv('TELEGRAM_API_ID')
    telegram_api_hash = os.getenv('TELEGRAM_API_HASH')
    telegram_phone = os.getenv('TELEGRAM_PHONE')
    reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
    reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
    
    # 检查是否配置了真实API
    has_telegram = telegram_api_id and telegram_api_hash and telegram_phone
    has_reddit = reddit_client_id and reddit_client_secret
    
    if has_telegram or has_reddit:
        print("🔑 检测到真实API配置:")
        if has_telegram:
            print("  ✅ Telegram API - 已配置")
        if has_reddit:
            print("  ✅ Reddit API - 已配置")
        print("  ✅ RSS - 自动启用（无需配置）")
        print()
    else:
        print("⚠️  未检测到API配置，使用模拟数据演示")
        print("   要使用真实数据，请参考: API_CONFIGURATION_GUIDE.md")
        print()
    
    monitor = SocialMediaMonitor(
        telegram_api_id=int(telegram_api_id) if telegram_api_id else None,
        telegram_api_hash=telegram_api_hash,
        telegram_phone=telegram_phone,
        reddit_client_id=reddit_client_id,
        reddit_client_secret=reddit_client_secret,
        check_interval_minutes=10,
        save_reports=True,
        reports_dir='./reports/social_media'
    )
    
    results = await monitor.check_all_sources()
    print(monitor.get_summary_report(results))


async def demo_continuous_monitoring():
    """演示：持续监控（每10分钟一次）"""
    print("\n" + "="*80)
    print("🔄 演示2: 持续社交媒体监控（每10分钟）")
    print("="*80 + "\n")
    
    # 从环境变量读取配置
    telegram_api_id = os.getenv('TELEGRAM_API_ID')
    telegram_api_hash = os.getenv('TELEGRAM_API_HASH')
    telegram_phone = os.getenv('TELEGRAM_PHONE')
    reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
    reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
    
    monitor = SocialMediaMonitor(
        telegram_api_id=int(telegram_api_id) if telegram_api_id else None,
        telegram_api_hash=telegram_api_hash,
        telegram_phone=telegram_phone,
        reddit_client_id=reddit_client_id,
        reddit_client_secret=reddit_client_secret,
        check_interval_minutes=10,
        save_reports=True,
        reports_dir='./reports/social_media'
    )
    
    # 运行1小时（便于演示，实际可以设为None持续运行）
    await monitor.run_monitoring_loop(duration_hours=1)


async def demo_with_alerts():
    """演示：带告警的监控"""
    print("\n" + "="*80)
    print("⚠️  演示3: 带情绪告警的社交媒体监控")
    print("="*80 + "\n")
    
    # 从环境变量读取配置
    telegram_api_id = os.getenv('TELEGRAM_API_ID')
    telegram_api_hash = os.getenv('TELEGRAM_API_HASH')
    telegram_phone = os.getenv('TELEGRAM_PHONE')
    reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
    reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
    
    monitor = SocialMediaMonitor(
        telegram_api_id=int(telegram_api_id) if telegram_api_id else None,
        telegram_api_hash=telegram_api_hash,
        telegram_phone=telegram_phone,
        reddit_client_id=reddit_client_id,
        reddit_client_secret=reddit_client_secret,
        check_interval_minutes=10,
        save_reports=True,
        reports_dir='./reports/social_media'
    )
    
    # 自定义告警逻辑
    async def check_with_alerts():
        results = await monitor.check_all_sources()
        
        # 检查综合情绪
        comp = results.get('comprehensive_analysis', {})
        overall = comp.get('overall_sentiment', {})
        
        sentiment_label = overall.get('label', 'UNKNOWN')
        sentiment_score = overall.get('score', 0)
        
        # 告警条件
        if sentiment_label == 'BULLISH' and sentiment_score > 0.5:
            logger.warning("🚀 强烈看涨信号！社交媒体情绪极度乐观")
        elif sentiment_label == 'BEARISH' and sentiment_score < -0.5:
            logger.warning("⚠️ 强烈看跌信号！社交媒体情绪极度悲观")
        
        # 检查重要人物提及
        influencers = comp.get('influencer_mentions', {})
        for name, data in influencers.items():
            if data['total'] >= 10:  # 提及超过10次
                display_name = name.replace('_', ' ').title()
                logger.warning(f"🔥 {display_name} 被频繁提及 ({data['total']}次)！")
        
        return results
    
    results = await check_with_alerts()
    print(monitor.get_summary_report(results))


async def main():
    """主函数"""
    print("\n" + "="*80)
    print("🌐 社交媒体综合监控系统演示")
    print("="*80)
    print("\n选择演示模式：")
    print("  1. 单次检查（快速演示）")
    print("  2. 持续监控（每10分钟一次，运行1小时）")
    print("  3. 带告警的监控（单次检查 + 情绪告警）")
    print("\n如果不输入，默认执行演示1\n")
    
    try:
        choice = input("请输入选项 (1-3): ").strip()
    except EOFError:
        choice = "1"
    
    if choice == "2":
        await demo_continuous_monitoring()
    elif choice == "3":
        await demo_with_alerts()
    else:
        await demo_single_check()
    
    print("\n" + "="*80)
    print("✅ 演示完成！")
    print("="*80)
    print("\n📝 使用真实数据配置：")
    print("\n系统会自动从 .env 文件读取API配置。")
    print("\n要启用真实数据监控，请按以下步骤操作：")
    print("\n1. 编辑 .env 文件：")
    print("   nano /home/andy/projects/Openclaw-stock/.env")
    print("\n2. 找到 '社交媒体监控 API 配置' 部分")
    print("\n3. 填写你的API密钥（参考配置指南）：")
    print("   详细步骤见: API_CONFIGURATION_GUIDE.md")
    print("\n4. 重新运行脚本即可使用真实数据")
    print("\n📚 快速配置链接：")
    print("   • Telegram: https://my.telegram.org")
    print("   • Reddit: https://www.reddit.com/prefs/apps")
    print("   • RSS: 无需配置")
    print("\n💡 提示：所有API都是免费的，无需信用卡！")
    print("\n如果不配置API密钥，系统将继续使用模拟数据演示。")


if __name__ == '__main__':
    asyncio.run(main())
