#!/usr/bin/env python3
"""
快速测试自然语言对话功能
"""
import os
import asyncio
from dotenv import load_dotenv
from openclaw.skills.execution.position_tracker import PositionTracker
from telegram_bot_standalone import OpenClawTelegramBot
from loguru import logger

def main():
    # 加载环境变量
    load_dotenv()
    
    # 从环境变量获取配置
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    AUTHORIZED_USERS = os.getenv('TELEGRAM_AUTHORIZED_USERS', '').split(',')
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ 请在.env文件中设置 TELEGRAM_BOT_TOKEN")
        return
    
    if not TELEGRAM_CHAT_ID:
        logger.error("❌ 请在.env文件中设置 TELEGRAM_CHAT_ID")
        return
    
    # 转换授权用户ID为整数
    try:
        authorized_users = [int(uid.strip()) for uid in AUTHORIZED_USERS if uid.strip()]
    except ValueError:
        logger.error("❌ TELEGRAM_AUTHORIZED_USERS 格式错误，应为逗号分隔的数字")
        return
    
    logger.info("🚀 启动 OpenClaw Telegram Bot (自然语言对话版)")
    logger.info(f"   授权用户: {authorized_users}")
    
    # 初始化持仓跟踪器
    tracker = PositionTracker(initial_capital=0.0)  # 初始资金为0，实际资金通过"调整总资产"命令设置
    
    # 创建并运行bot
    bot = OpenClawTelegramBot(
        token=TELEGRAM_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        tracker=tracker,
        authorized_users=authorized_users
    )
    
    logger.info("✅ Bot已启动，等待消息...")
    logger.info("\n💬 你可以发送以下消息进行测试:")
    logger.info("   • 买入三星电子 10股 价格75000")
    logger.info("   • 给我BTC的建议")
    logger.info("   • 我的持仓")
    logger.info("   • 卖出三星电子 5股 价格77000")
    logger.info("   • 帮我分析一下市场\n")
    
    # 运行bot (异步)
    asyncio.run(bot.run())


if __name__ == '__main__':
    main()
