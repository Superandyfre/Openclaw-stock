#!/usr/bin/env python3
"""
社交媒体监控 API 配置助手

交互式配置向导，帮助你快速设置 Telegram 和 Reddit API
"""
import os
import re
from pathlib import Path


def print_header(text):
    """打印标题"""
    print("\n" + "="*80)
    print(text)
    print("="*80 + "\n")


def print_section(text):
    """打印章节"""
    print("\n" + "-"*60)
    print(text)
    print("-"*60 + "\n")


def validate_phone(phone):
    """验证手机号格式"""
    # 应该是 +国家代码 + 号码
    pattern = r'^\+\d{10,15}$'
    return bool(re.match(pattern, phone))


def configure_telegram():
    """配置 Telegram API"""
    print_section("📱 配置 Telegram 频道监控")
    
    print("要获取 Telegram API 密钥，请按以下步骤操作：")
    print("1. 访问 https://my.telegram.org")
    print("2. 使用你的 Telegram 账号登录")
    print("3. 点击 'API development tools'")
    print("4. 创建应用获取 API ID 和 API Hash")
    print()
    
    configure = input("是否配置 Telegram API？(y/n，默认n): ").strip().lower()
    
    if configure != 'y':
        print("⏭️  跳过 Telegram 配置")
        return None, None, None
    
    # API ID
    while True:
        api_id = input("\n请输入 API ID (纯数字): ").strip()
        if api_id.isdigit():
            break
        print("❌ API ID 必须是数字，请重新输入")
    
    # API Hash
    while True:
        api_hash = input("请输入 API Hash (32位字符): ").strip()
        if len(api_hash) == 32:
            break
        print("❌ API Hash 应该是32位字符，请重新输入")
    
    # 手机号
    while True:
        phone = input("请输入手机号 (格式: +8613800138000): ").strip()
        if validate_phone(phone):
            break
        print("❌ 手机号格式错误，必须包含国际区号，如: +8613800138000")
    
    print("\n✅ Telegram API 配置完成")
    return api_id, api_hash, phone


def configure_reddit():
    """配置 Reddit API"""
    print_section("🗣️  配置 Reddit 社区监控")
    
    print("要获取 Reddit API 密钥，请按以下步骤操作：")
    print("1. 访问 https://www.reddit.com/prefs/apps")
    print("2. 登录你的 Reddit 账号")
    print("3. 点击 'create another app...'")
    print("4. 选择 'script' 类型")
    print("5. 获取 Client ID 和 Client Secret")
    print()
    
    configure = input("是否配置 Reddit API？(y/n，默认n): ").strip().lower()
    
    if configure != 'y':
        print("⏭️  跳过 Reddit 配置")
        return None, None
    
    # Client ID
    client_id = input("\n请输入 Client ID: ").strip()
    if not client_id:
        print("❌ Client ID 不能为空，跳过配置")
        return None, None
    
    # Client Secret
    client_secret = input("请输入 Client Secret: ").strip()
    if not client_secret:
        print("❌ Client Secret 不能为空，跳过配置")
        return None, None
    
    print("\n✅ Reddit API 配置完成")
    return client_id, client_secret


def update_env_file(telegram_config, reddit_config):
    """更新 .env 文件"""
    print_section("💾 保存配置到 .env 文件")
    
    env_path = Path(__file__).parent / '.env'
    
    if not env_path.exists():
        print(f"❌ 找不到 .env 文件: {env_path}")
        return False
    
    # 读取现有内容
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 更新 Telegram 配置
    if telegram_config[0]:
        api_id, api_hash, phone = telegram_config
        content = re.sub(
            r'TELEGRAM_API_ID=.*',
            f'TELEGRAM_API_ID={api_id}',
            content
        )
        content = re.sub(
            r'TELEGRAM_API_HASH=.*',
            f'TELEGRAM_API_HASH={api_hash}',
            content
        )
        content = re.sub(
            r'TELEGRAM_PHONE=.*',
            f'TELEGRAM_PHONE={phone}',
            content
        )
        print("✅ Telegram 配置已保存")
    
    # 更新 Reddit 配置
    if reddit_config[0]:
        client_id, client_secret = reddit_config
        content = re.sub(
            r'REDDIT_CLIENT_ID=.*',
            f'REDDIT_CLIENT_ID={client_id}',
            content
        )
        content = re.sub(
            r'REDDIT_CLIENT_SECRET=.*',
            f'REDDIT_CLIENT_SECRET={client_secret}',
            content
        )
        print("✅ Reddit 配置已保存")
    
    # 保存文件
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n✅ 配置已保存到: {env_path}")
    return True


def test_configuration():
    """测试配置"""
    print_section("🧪 测试配置")
    
    test = input("是否立即测试配置？(y/n，默认n): ").strip().lower()
    
    if test != 'y':
        print("⏭️  跳过测试")
        return
    
    print("\n正在测试配置...")
    print("(如果是首次使用 Telegram，需要输入验证码)\n")
    
    os.system('python demo_social_media_monitor.py')


def main():
    """主函数"""
    print_header("🔑 社交媒体监控 API 配置助手")
    
    print("这个向导将帮助你配置 Telegram 和 Reddit API。")
    print("所有API都是免费的，无需信用卡！")
    print()
    print("如果暂时不想配置，可以直接按回车跳过。")
    print("系统会使用模拟数据进行演示。")
    
    # 配置 Telegram
    telegram_config = configure_telegram()
    
    # 配置 Reddit
    reddit_config = configure_reddit()
    
    # 检查是否有配置
    if not telegram_config[0] and not reddit_config[0]:
        print_section("⚠️  未配置任何API")
        print("系统将使用模拟数据运行。")
        print("要配置真实数据，请重新运行此脚本或手动编辑 .env 文件。")
        return
    
    # 保存配置
    success = update_env_file(telegram_config, reddit_config)
    
    if not success:
        print("\n❌ 保存配置失败")
        return
    
    # 显示配置摘要
    print_section("📊 配置摘要")
    
    if telegram_config[0]:
        print("✅ Telegram 频道监控: 已启用")
        print(f"   API ID: {telegram_config[0]}")
        print(f"   手机号: {telegram_config[2]}")
    else:
        print("⏭️  Telegram 频道监控: 未配置（将使用模拟数据）")
    
    if reddit_config[0]:
        print("✅ Reddit 社区监控: 已启用")
        print(f"   Client ID: {reddit_config[0][:10]}...")
    else:
        print("⏭️  Reddit 社区监控: 未配置（将使用模拟数据）")
    
    print("✅ RSS 订阅监控: 自动启用（无需配置）")
    
    # 测试配置
    test_configuration()
    
    print_header("✅ 配置完成！")
    
    print("现在你可以运行以下命令开始监控：")
    print()
    print("  python demo_social_media_monitor.py")
    print()
    print("系统将每10分钟自动监控一次，生成综合情绪报告。")
    print()
    print("报告位置: ./reports/social_media/")
    print()
    print("详细文档: API_CONFIGURATION_GUIDE.md")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  配置已取消")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        print("请手动编辑 .env 文件或查看文档: API_CONFIGURATION_GUIDE.md")
