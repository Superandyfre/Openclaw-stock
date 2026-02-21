# 社交媒体监控系统使用指南

## 📋 概述

社交媒体综合监控系统整合了三大免费数据源：
- **A: Telegram公开频道** - 实时监控加密货币相关频道
- **B: Reddit社区** - 追踪热门讨论和散户情绪
- **C: 重要人物RSS订阅** - 订阅行业领袖的博客文章

系统每10分钟自动运行一次，生成综合情绪分析报告。

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd /home/andy/projects/Openclaw-stock
source venv/bin/activate
pip install telethon praw feedparser
```

### 2. 运行演示（使用模拟数据）

```bash
python demo_social_media_monitor.py
```

演示模式无需API密钥，使用模拟数据展示功能。

---

## 🔑 配置真实数据源

### A. Telegram频道监控（可选）

1. **获取API密钥**：
   - 访问 https://my.telegram.org
   - 登录你的Telegram账号
   - 进入 "API development tools"
   - 创建应用获取 **API ID** 和 **API Hash**

2. **设置环境变量**：
   ```bash
   export TELEGRAM_API_ID=你的API_ID
   export TELEGRAM_API_HASH=你的API_Hash
   export TELEGRAM_PHONE=你的手机号（国际格式，如+8613800138000）
   ```

3. **监控的频道**：
   - @whale_alert - 巨鲸转账告警
   - @cointelegraph - CoinTelegraph新闻
   - @coindesk - CoinDesk新闻
   - @binance_announcements - Binance公告
   - @crypto_news_official - 加密新闻聚合

### B. Reddit社区监控（可选）

1. **获取API密钥**：
   - 访问 https://www.reddit.com/prefs/apps
   - 点击 "create another app"
   - 选择 "script"，填写名称和描述
   - 获取 **Client ID**（app下方的字符串）和 **Client Secret**

2. **设置环境变量**：
   ```bash
   export REDDIT_CLIENT_ID=你的Client_ID
   export REDDIT_CLIENT_SECRET=你的Client_Secret
   ```

3. **监控的社区**：
   - r/CryptoCurrency - 最大的加密货币社区（7.5M成员）
   - r/Bitcoin - 比特币官方社区（6M成员）
   - r/ethtrader - 以太坊交易讨论
   - r/wallstreetbets - 散户情绪风向标（16M成员）
   - r/CryptoMarkets - 加密货币市场分析
   - r/btc - 比特币技术讨论

### C. RSS订阅监控（无需配置）

RSS订阅完全免费，无需API密钥，自动监控：

**重要人物**：
- Vitalik Buterin（Ethereum创始人）- https://vitalik.eth.limo
- Michael Saylor（MicroStrategy CEO）
- Cathie Wood（ARK Invest）

**媒体机构**：
- CoinDesk
- Cointelegraph
- Bitcoin Magazine
- Ethereum Foundation
- a16z Crypto

---

## 📊 使用方法

### 方法1: 单次检查

```python
import asyncio
from openclaw.skills.monitoring.social_media_monitor import SocialMediaMonitor

async def single_check():
    monitor = SocialMediaMonitor(
        check_interval_minutes=10,
        save_reports=True
    )
    
    results = await monitor.check_all_sources()
    print(monitor.get_summary_report(results))

asyncio.run(single_check())
```

### 方法2: 持续监控（每10分钟）

```python
async def continuous_monitoring():
    monitor = SocialMediaMonitor(
        check_interval_minutes=10,  # 每10分钟检查一次
        save_reports=True
    )
    
    # 运行1小时
    await monitor.run_monitoring_loop(duration_hours=1)
    
    # 或持续运行（直到手动停止）
    # await monitor.run_monitoring_loop()

asyncio.run(continuous_monitoring())
```

### 方法3: 带API密钥的真实数据监控

```python
import os

async def real_data_monitoring():
    monitor = SocialMediaMonitor(
        # Telegram配置
        telegram_api_id=int(os.getenv('TELEGRAM_API_ID')),
        telegram_api_hash=os.getenv('TELEGRAM_API_HASH'),
        telegram_phone=os.getenv('TELEGRAM_PHONE'),
        
        # Reddit配置
        reddit_client_id=os.getenv('REDDIT_CLIENT_ID'),
        reddit_client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        
        # 监控配置
        check_interval_minutes=10,
        save_reports=True,
        reports_dir='./reports/social_media'
    )
    
    await monitor.run_monitoring_loop(duration_hours=24)  # 运行24小时

asyncio.run(real_data_monitoring())
```

---

## 📄 报告输出

每次监控会生成两个文件：

1. **JSON格式** - `social_media_report_YYYYMMDD_HHMM.json`
   - 完整的结构化数据
   - 便于程序读取和分析

2. **文本格式** - `social_media_report_YYYYMMDD_HHMM.txt`
   - 人类可读的摘要报告
   - 包含综合情绪分析和详细数据

报告内容包括：
- ✅ 整体情绪（BULLISH/BEARISH/NEUTRAL）
- ✅ 情绪得分（-1到+1）
- ✅ 重要人物提及次数（Elon Musk, Vitalik等）
- ✅ 各平台详细分析
- ✅ 热门话题和关键词

---

## 🔔 告警功能

系统自动检测以下情况：

1. **极端情绪**：
   - 整体情绪得分 > 0.5 → 强烈看涨告警
   - 整体情绪得分 < -0.5 → 强烈看跌告警

2. **重要人物提及**：
   - 某人物被提及超过10次 → 热度告警

3. **突发事件**：
   - 特定关键词激增（如"regulation", "hack", "adoption"）

---

## 💡 数据源说明

### 完全免费
所有三个数据源都是**完全免费**的：
- ✅ Telegram API - 免费（需注册Telegram账号）
- ✅ Reddit API - 免费（速率限制：60次/分钟）
- ✅ RSS订阅 - 完全免费，无限制

### 数据更新频率
- **Telegram**: 实时（获取最近10分钟的消息）
- **Reddit**: 准实时（获取24小时内的热门帖子）
- **RSS**: 根据订阅源更新（通常每小时或每天）

### 监控范围
- **Telegram**: 5个重要频道
- **Reddit**: 6个热门社区
- **RSS**: 8个重要订阅源

---

## 🛠️ 自定义配置

### 修改监控频率

```python
monitor = SocialMediaMonitor(
    check_interval_minutes=5  # 改为每5分钟
)
```

### 添加自定义频道

编辑 `telegram_channel_monitor.py`：
```python
IMPORTANT_CHANNELS = {
    'your_channel': {
        'username': 'your_channel_username',
        'name': '你的频道名称',
        'description': '频道描述',
        'keywords': ['关键词1', '关键词2']
    }
}
```

### 添加自定义subreddit

编辑 `reddit_community_monitor.py`：
```python
IMPORTANT_SUBREDDITS = {
    'your_subreddit': {
        'name': '你的社区名称',
        'members': '成员数',
        'description': '社区描述',
        'keywords': ['关键词1', '关键词2']
    }
}
```

### 添加自定义RSS源

编辑 `influencer_rss_monitor.py`：
```python
IMPORTANT_FEEDS = {
    'your_feed': {
        'name': '订阅源名称',
        'role': '角色',
        'rss_url': 'https://example.com/feed.xml',
        'keywords': ['关键词1', '关键词2'],
        'importance': 'HIGH'
    }
}
```

---

## 📈 监控指标

系统追踪以下指标：

### Telegram
- 消息数量
- 关键词提及
- 互动数（浏览量、转发数）
- 情绪得分
- 重要人物提及

### Reddit
- 帖子数量
- 讨论热度（分数、评论数）
- 支持率（upvote ratio）
- 情绪趋势
- 热门话题

### RSS
- 文章数量
- 主题分类
- 情绪倾向
- 重要性评分

---

## ⚠️ 注意事项

1. **首次使用Telegram**：
   - 第一次运行需要手机验证码登录
   - 登录后会保存session文件，后续无需再次登录

2. **速率限制**：
   - Reddit: 60次请求/分钟
   - Telegram: 无明确限制，建议间隔2秒
   - RSS: 无限制，但建议间隔1秒

3. **数据隐私**：
   - 只监控公开频道/社区
   - 不收集个人信息
   - 报告仅保存在本地

4. **API密钥安全**：
   - 不要将API密钥提交到Git
   - 使用环境变量或.env文件
   - 定期轮换密钥

---

## 🐛 故障排除

### 问题1: Telegram登录失败
```
解决：确保手机号格式正确（+国家代码+手机号）
示例：+8613800138000
```

### 问题2: Reddit连接失败
```
解决：检查Client ID和Secret是否正确
确认应用类型为"script"而非"web app"
```

### 问题3: RSS获取失败
```
解决：某些RSS源可能需要翻墙或暂时不可用
系统会自动使用模拟数据继续运行
```

### 问题4: 模块导入错误
```
解决：确保已安装所有依赖
pip install telethon praw feedparser
```

---

## 📞 支持

如有问题，请检查：
1. 依赖是否安装完整
2. API密钥是否配置正确
3. 网络连接是否正常
4. 查看日志文件获取详细错误信息

---

## 🎯 最佳实践

1. **开始测试**：先用演示模式验证功能
2. **逐步配置**：先配置一个数据源，测试成功后再添加其他
3. **定时运行**：使用cron或systemd设置定时任务
4. **监控告警**：结合Telegram Bot或邮件发送告警通知
5. **数据分析**：定期分析历史报告，发现市场趋势

---

## 🔗 相关链接

- Telegram API文档: https://core.telegram.org/api
- Reddit API文档: https://www.reddit.com/dev/api
- RSS 2.0规范: https://www.rssboard.org/rss-specification
- Telethon文档: https://docs.telethon.dev
- PRAW文档: https://praw.readthedocs.io
- Feedparser文档: https://feedparser.readthedocs.io
