# Telegram Bot 用户验证配置指南

## 🔒 为什么需要用户验证？

默认情况下，任何人只要知道你的Telegram bot用户名，都可以与它对话并查看你的投资组合信息。**启用用户白名单验证**后，只有你授权的用户才能使用bot。

## 📝 配置步骤

### 第1步：获取你的Telegram用户ID

有三种方法获取你的Telegram用户ID：

#### 方法1：使用 @userinfobot（推荐）
1. 在Telegram中搜索 `@userinfobot`
2. 点击开始对话
3. bot会自动回复你的用户ID
4. 记下你的ID（例如：`123456789`）

#### 方法2：使用 @get_id_bot
1. 在Telegram中搜索 `@get_id_bot`
2. 发送任意消息
3. bot会回复你的详细信息，包括ID

#### 方法3：从bot日志中获取（需要先运行一次bot）
1. 暂时不启用验证，运行bot
2. 向bot发送任意消息
3. 查看bot日志，会显示：`❌ 未授权用户尝试访问: YourUsername (ID: 123456789)`
4. 记下ID号码

### 第2步：配置环境变量

编辑 `.env` 文件，添加你的用户ID：

```bash
# Telegram Bot 配置
TELEGRAM_BOT_TOKEN=你的bot_token
TELEGRAM_CHAT_ID=你的chat_id

# 用户白名单（只允许这些用户ID使用bot）
# 多个用户用逗号分隔，例如：123456789,987654321
TELEGRAM_AUTHORIZED_USERS=你的用户ID
```

**示例：**
```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
TELEGRAM_AUTHORIZED_USERS=123456789
```

### 第3步：修改代码以读取白名单配置

在 `korean_stock_monitor.py` 或其他启动bot的文件中，添加以下代码：

```python
# 读取授权用户列表
authorized_users_str = os.getenv('TELEGRAM_AUTHORIZED_USERS', '')
authorized_users = [int(uid.strip()) for uid in authorized_users_str.split(',') if uid.strip()]

# 创建bot时传入授权用户
telegram_bot = OpenClawTelegramBot(
    token=TELEGRAM_BOT_TOKEN,
    chat_id=TELEGRAM_CHAT_ID,
    tracker=tracker,
    authorized_users=authorized_users  # ← 传入白名单
)
```

### 第4步：测试验证功能

1. 启动bot
2. 使用你的账号发送 `/start`
   - ✅ 应该能正常使用
3. 让朋友或使用另一个账号尝试访问
   - ❌ 应该收到"您没有权限使用此bot"的提示

## 👥 添加多个授权用户

如果你想让多人使用bot（例如家人或团队成员），可以在 `.env` 中添加多个用户ID：

```bash
# 逗号分隔多个用户ID
TELEGRAM_AUTHORIZED_USERS=123456789,987654321,456789123
```

## 🚨 安全提示

### ✅ 推荐做法
- 始终启用用户验证
- 只授权你信任的用户
- 定期检查日志，查看是否有未授权访问尝试
- 不要在公开场所分享你的bot用户名
- 定期更换bot token（如果怀疑泄露）

### ❌ 不推荐做法
- 不要将bot token提交到公开的Git仓库
- 不要在未验证的情况下运行bot
- 不要将你的用户ID告诉陌生人

## 📊 查看访问日志

启用验证后，bot会记录所有访问尝试：

**授权用户访问：**
```
✅ 授权用户访问: YourUsername (ID: 123456789)
```

**未授权用户访问：**
```
❌ 未授权用户尝试访问: UnknownUser (ID: 987654321)
```

## 🔧 故障排除

### 问题1：我自己也无法使用bot
- 检查 `TELEGRAM_AUTHORIZED_USERS` 是否包含你的用户ID
- 确保用户ID是纯数字，没有空格或其他字符
- 重启bot使配置生效

### 问题2：如何临时禁用验证（测试用）
在代码中传入 `authorized_users=None`：
```python
bot = OpenClawTelegramBot(
    token=token,
    chat_id=chat_id,
    tracker=tracker,
    authorized_users=None  # 禁用验证，允许所有用户
)
```

### 问题3：bot说我没有权限，但我在白名单中
- 检查 `.env` 文件是否正确加载（使用 `python-dotenv`）
- 确认用户ID拼写正确
- 查看bot启动日志，确认白名单已加载
- 尝试重启bot

## 📱 示例：完整的bot启动代码

```python
#!/usr/bin/env python3
import os
import asyncio
from dotenv import load_dotenv
from telegram_bot_standalone import OpenClawTelegramBot
from openclaw.skills.execution.position_tracker import PositionTracker

# 加载环境变量
load_dotenv()

# 读取配置
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 读取授权用户列表
authorized_users_str = os.getenv('TELEGRAM_AUTHORIZED_USERS', '')
if authorized_users_str:
    authorized_users = [int(uid.strip()) for uid in authorized_users_str.split(',') if uid.strip()]
    print(f"✅ 已启用用户验证，授权用户数: {len(authorized_users)}")
else:
    authorized_users = None
    print("⚠️ 警告：未启用用户验证，任何人都可以使用bot！")

# 创建tracker（示例）
tracker = PositionTracker(initial_capital=10_000_000)

# 创建bot（带用户验证）
bot = OpenClawTelegramBot(
    token=TELEGRAM_BOT_TOKEN,
    chat_id=TELEGRAM_CHAT_ID,
    tracker=tracker,
    authorized_users=authorized_users  # 传入白名单
)

# 启动bot
asyncio.run(bot.run())
```

## 🎯 验证成功示例

当配置正确后，你会看到：

**启动日志：**
```
✅ Telegram Bot 初始化成功（已启用用户白名单，授权用户数: 1）
🚀 启动 Telegram Bot...
✅ Telegram Bot 运行中
```

**你发送 /start：**
```
✅ 授权用户访问: YourUsername (ID: 123456789)
🦞 欢迎使用 OpenClaw 韩股交易系统！
...
```

**陌生人发送 /start：**
```
❌ 未授权用户尝试访问: Stranger (ID: 987654321)
```

对方收到的消息：
```
❌ 抱歉，您没有权限使用此bot。

您的用户ID: 987654321

如需访问权限，请联系bot管理员。
```

---

**配置完成！** 现在你的Telegram bot只会响应你授权的用户。🔒
