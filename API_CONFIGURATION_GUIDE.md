# 🔑 社交媒体监控 API 配置指南

## 📋 概览

社交媒体监控系统需要配置以下API（**全部免费**）：

| 数据源 | 是否必需 | 费用 | 配置时间 |
|--------|---------|------|---------|
| **Telegram 频道** | 可选 | 免费 | ~5分钟 |
| **Reddit 社区** | 可选 | 免费 | ~3分钟 |
| **RSS 订阅** | 自动 | 免费 | 无需配置 |

**提示**: 如果不配置API，系统将使用模拟数据演示功能。建议至少配置一个真实数据源。

---

## 🔧 配置步骤

### 方案1: Telegram 频道监控（推荐）

#### 📱 获取 Telegram API 密钥

**第一步：访问 Telegram API 开发平台**

1. 打开浏览器，访问 https://my.telegram.org
2. 使用你的 **Telegram 手机号** 登录（会收到验证码）

**第二步：创建应用**

3. 登录后，点击 **"API development tools"**
4. 填写应用信息：
   ```
   App title: OpenClaw Monitor
   Short name: openclaw
   Platform: Desktop
   Description: Cryptocurrency social media monitoring
   ```
5. 点击 **"Create application"**

**第三步：获取密钥**

6. 创建成功后，你会看到：
   ```
   App api_id: 12345678
   App api_hash: abcdef1234567890abcdef1234567890
   ```
   
**第四步：配置到 .env 文件**

7. 打开 `/home/andy/projects/Openclaw-stock/.env` 文件
8. 找到 `# ----- Telegram 频道监控 API (可选) -----` 部分
9. 填写你的信息：
   ```bash
   TELEGRAM_API_ID=12345678
   TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
   TELEGRAM_PHONE=+8613800138000
   ```

**⚠️ 手机号格式**：
- 必须包含国际区号
- 中国大陆：`+86` 开头
- 示例：`+8613800138000`（+86 + 手机号）

#### ✅ 测试配置

```bash
cd /home/andy/projects/Openclaw-stock
source venv/bin/activate

# 测试 Telegram 监控
python -c "
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from openclaw.skills.data_collection.telegram_channel_monitor import TelegramChannelMonitor

async def test():
    monitor = TelegramChannelMonitor(
        api_id=int(os.getenv('TELEGRAM_API_ID')),
        api_hash=os.getenv('TELEGRAM_API_HASH'),
        phone=os.getenv('TELEGRAM_PHONE')
    )
    
    # 连接
    connected = await monitor.connect()
    if connected:
        print('✅ Telegram API 配置成功！')
        
        # 获取一个频道的消息测试
        messages = await monitor.fetch_channel_messages('whale_alert', limit=5)
        print(f'✅ 成功获取 {len(messages)} 条消息')
        
        await monitor.disconnect()
    else:
        print('❌ 配置失败，请检查 API 密钥')

asyncio.run(test())
"
```

**首次运行提示**：
- 第一次连接时，Telegram 会发送验证码到你的手机
- 输入验证码后，会生成 session 文件
- 之后无需再次输入验证码

---

### 方案2: Reddit 社区监控

#### 🗣️ 获取 Reddit API 密钥

**第一步：访问 Reddit 应用管理页面**

1. 打开浏览器，访问 https://www.reddit.com/prefs/apps
2. 使用你的 **Reddit 账号** 登录（如果没有账号，先注册一个）

**第二步：创建应用**

3. 滚动到页面底部，点击 **"create another app..."** 按钮
4. 填写应用信息：
   ```
   name: OpenClaw Monitor
   选择类型: script
   description: Cryptocurrency sentiment monitoring
   about url: (留空)
   redirect uri: http://localhost:8080
   ```
5. 点击 **"create app"**

**第三步：获取密钥**

6. 创建成功后，你会看到：
   ```
   personal use script
   ABCdefGHIjkl          ← 这是你的 Client ID
   
   secret
   xyz123abc456def789ghi  ← 这是你的 Client Secret
   ```

**第四步：配置到 .env 文件**

7. 打开 `/home/andy/projects/Openclaw-stock/.env` 文件
8. 找到 `# ----- Reddit 社区监控 API (可选) -----` 部分
9. 填写你的信息：
   ```bash
   REDDIT_CLIENT_ID=ABCdefGHIjkl
   REDDIT_CLIENT_SECRET=xyz123abc456def789ghi
   ```

#### ✅ 测试配置

```bash
cd /home/andy/projects/Openclaw-stock
source venv/bin/activate

# 测试 Reddit 监控
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

from openclaw.skills.data_collection.reddit_community_monitor import RedditCommunityMonitor

monitor = RedditCommunityMonitor(
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET')
)

# 连接
connected = monitor.connect()
if connected:
    print('✅ Reddit API 配置成功！')
    
    # 获取一个社区的帖子测试
    posts = monitor.fetch_hot_posts('CryptoCurrency', limit=5)
    print(f'✅ 成功获取 {len(posts)} 个帖子')
else:
    print('❌ 配置失败，请检查 API 密钥')
"
```

---

### 方案3: RSS 订阅（无需配置）

RSS 订阅**完全免费**，**无需任何配置**，自动监控以下来源：

**重要人物**：
- ✅ Vitalik Buterin（Ethereum 创始人）
- ✅ Michael Saylor（MicroStrategy CEO）  
- ✅ Cathie Wood（ARK Invest）

**媒体机构**：
- ✅ CoinDesk
- ✅ Cointelegraph
- ✅ Bitcoin Magazine
- ✅ Ethereum Foundation
- ✅ a16z Crypto

---

## 🚀 完整配置示例

如果你配置了**全部数据源**，你的 `.env` 文件应该类似：

```bash
# ==========================================
# 社交媒体监控 API 配置（免费）
# ==========================================

# ----- Telegram 频道监控 API (可选) -----
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_PHONE=+8613800138000

# ----- Reddit 社区监控 API (可选) -----
REDDIT_CLIENT_ID=ABCdefGHIjkl
REDDIT_CLIENT_SECRET=xyz123abc456def789ghi
```

---

## 🎯 运行完整监控系统

### 方式1: 使用配置文件

```bash
cd /home/andy/projects/Openclaw-stock
source venv/bin/activate

# 自动从 .env 加载配置
python -c "
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from openclaw.skills.monitoring.social_media_monitor import SocialMediaMonitor

async def run():
    monitor = SocialMediaMonitor(
        telegram_api_id=int(os.getenv('TELEGRAM_API_ID')) if os.getenv('TELEGRAM_API_ID') else None,
        telegram_api_hash=os.getenv('TELEGRAM_API_HASH'),
        telegram_phone=os.getenv('TELEGRAM_PHONE'),
        reddit_client_id=os.getenv('REDDIT_CLIENT_ID'),
        reddit_client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        check_interval_minutes=10,
        save_reports=True,
        reports_dir='./reports/social_media'
    )
    
    # 单次检查
    results = await monitor.check_all_sources()
    print(monitor.get_summary_report(results))
    
    # 或持续监控（每10分钟一次）
    # await monitor.run_monitoring_loop(duration_hours=24)

asyncio.run(run())
"
```

### 方式2: 使用演示脚本

我可以为你创建一个更方便的启动脚本：

```bash
python demo_social_media_monitor.py
```

这个脚本会：
1. 自动从 `.env` 加载配置
2. 如果有真实API密钥，使用真实数据
3. 如果没有配置，使用模拟数据演示

---

## 📊 监控内容

配置完成后，系统将监控：

### Telegram（5个重要频道）
- @whale_alert - 巨鲸转账告警
- @cointelegraph - CoinTelegraph 新闻
- @coindesk - CoinDesk 新闻
- @binance_announcements - Binance 公告
- @crypto_news_official - 加密新闻聚合

### Reddit（6个热门社区）
- r/CryptoCurrency（7.5M 成员）
- r/Bitcoin（6M 成员）
- r/ethtrader（1.5M 成员）
- r/wallstreetbets（16M 成员）
- r/CryptoMarkets（2.5M 成员）
- r/btc（400K 成员）

### RSS（8个订阅源）
- 自动抓取，无需配置

---

## 🔒 安全提示

1. **保护你的 API 密钥**：
   - ✅ 不要分享给他人
   - ✅ 不要提交到 Git 仓库
   - ✅ 定期检查 `.gitignore` 包含 `.env`

2. **API 权限说明**：
   - Telegram: 只能读取公开频道，无法读取私聊或群组
   - Reddit: 只能读取公开帖子和评论
   - RSS: 只能读取公开博客文章

3. **速率限制**：
   - Telegram: 无明确限制，建议间隔 2 秒
   - Reddit: 60 次请求/分钟
   - RSS: 无限制

---

## ⚠️ 常见问题

### Q1: Telegram 验证码一直收不到
**A**: 确保手机号格式正确（`+86` + 手机号），检查 Telegram 是否被屏蔽

### Q2: Reddit API 返回 401 错误
**A**: 检查 Client ID 和 Secret 是否正确，确保应用类型选择的是 "script"

### Q3: 可以只配置一个数据源吗？
**A**: 可以！系统会自动检测可用的数据源。建议至少配置一个。

### Q4: 需要付费吗？
**A**: 完全免费！所有 API 都不需要付费。

### Q5: 配置后多久生效？
**A**: 立即生效，重新运行脚本即可使用真实数据。

---

## 📞 技术支持

如果遇到问题：

1. **检查配置**：确保 `.env` 文件中的密钥格式正确
2. **查看日志**：运行时会显示详细的错误信息
3. **重新生成密钥**：如果密钥失效，重新创建应用获取新密钥
4. **使用模拟数据**：如果配置有问题，系统会自动降级到模拟模式

---

## ✅ 配置检查清单

- [ ] 已访问 Telegram API 开发平台并创建应用
- [ ] 已获取 Telegram API ID 和 Hash
- [ ] 已在 `.env` 中填写 Telegram 配置
- [ ] 已访问 Reddit 应用管理页面并创建应用
- [ ] 已获取 Reddit Client ID 和 Secret
- [ ] 已在 `.env` 中填写 Reddit 配置
- [ ] 已测试配置是否正常工作
- [ ] 已运行完整监控系统

---

**🎉 配置完成后，你就可以每10分钟自动监控Telegram、Reddit、RSS三大社交媒体平台，实时追踪加密货币市场情绪和重要人物动态了！**
