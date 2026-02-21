#!/usr/bin/env python3
"""
AI交易建议 - 快速示例
最简单的使用方法
"""
import asyncio
from openclaw.skills.analysis.ai_trading_advisor import AITradingAdvisor


async def quick_example():
    """5行代码获取AI交易建议"""
    
    print("🤖 AI交易建议 - 5行代码示例\n")
    
    # 1. 创建顾问（无需配置）
    advisor = AITradingAdvisor()
    
    # 2. 生成建议（最简参数）
    advice = await advisor.generate_trading_advice(
        symbol='005930',
        name='삼성전자',
        current_price=75000,
        price_data={'change_pct': 2.5, 'volume_ratio': 2.0},
        technical_indicators={'rsi': 45},
        sentiment={'score': 0.6}
    )
    
    # 3. 显示结果
    print(f"📊 {advice['name']} ({advice['symbol']})")
    print(f"💰 价格: ₩{advice['current_price']:,}")
    print(f"🎯 建议: {advice['action']}")
    print(f"⭐ 置信度: {advice['confidence_level']}")
    print(f"💪 评分: {advice['strength_score']:.1f}/10")
    
    if advice.get('targets'):
        print(f"\n📈 目标:")
        for key, value in advice['targets'].items():
            print(f"   {key}: ₩{value:,.0f}")


async def telegram_example():
    """Telegram格式示例"""
    
    print("\n" + "="*60)
    print("📱 Telegram消息格式示例")
    print("="*60 + "\n")
    
    advisor = AITradingAdvisor()
    
    advice = await advisor.generate_trading_advice(
        symbol='035420',
        name='NAVER',
        current_price=250000,
        price_data={'change_pct': -1.5, 'volume_ratio': 0.8},
        technical_indicators={'rsi': 32},
        sentiment={'score': -0.3}
    )
    
    # 格式化为Telegram消息
    message = advisor.format_advice_for_telegram(advice)
    print(message)


async def batch_example():
    """批量分析示例"""
    
    print("\n" + "="*60)
    print("📊 批量分析示例")
    print("="*60 + "\n")
    
    advisor = AITradingAdvisor()
    
    # 多只股票
    stocks = [
        ('005930', '삼성전자', 75000),
        ('035420', 'NAVER', 250000),
        ('035720', '카카오', 57000)
    ]
    
    for symbol, name, price in stocks:
        advice = await advisor.generate_trading_advice(
            symbol=symbol,
            name=name,
            current_price=price,
            price_data={'change_pct': 0, 'volume_ratio': 1.0},
            technical_indicators={'rsi': 50},
            sentiment={'score': 0}
        )
        
        print(f"{name:10s} → {advice['action']:4s} ({advice['confidence']:>3.0%}) "
              f"评分:{advice['strength_score']:4.1f}/10")


async def main():
    print("\n" + "="*60)
    print("🚀 AI交易建议功能 - 快速示例")
    print("="*60 + "\n")
    
    # 示例1：基础用法
    await quick_example()
    
    # 示例2：Telegram格式
    await telegram_example()
    
    # 示例3：批量分析
    await batch_example()
    
    print("\n" + "="*60)
    print("✅ 示例完成！")
    print("="*60 + "\n")
    
    print("💡 提示:")
    print("  • 设置 GOOGLE_AI_API_KEY 启用AI深度分析")
    print("  • 在Telegram中使用 /analyze 股票代码")
    print("  • 查看 AI_TRADING_ADVICE.md 了解更多")
    print()


if __name__ == '__main__':
    asyncio.run(main())
