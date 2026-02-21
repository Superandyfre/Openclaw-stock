# 🤖 自然语言对话功能 - 完整集成指南

## 📋 概述

OpenClaw Telegram Bot 现已支持完整的自然语言对话功能！你可以像和朋友聊天一样与bot交互，执行交易、查询持仓、请求AI建议等操作。

## ✅ 已集成的功能

### 1. **自然语言理解 (ConversationHandler)**
- 📝 意图识别：自动识别8种对话意图
  - BUY_STOCK/BUY_CRYPTO - 买入股票/加密货币
  - SELL_STOCK/SELL_CRYPTO - 卖出股票/加密货币
  - ASK_ADVICE - 请求AI交易建议
  - CHECK_POSITION - 查询持仓
  - PORTFOLIO_ADJUSTMENT - 投资组合调整
  - MARKET_ANALYSIS - 市场分析

- 🧠 混合识别策略：
  - 规则匹配（快速）：关键词、正则表达式
  - AI理解（智能）：Gemini AI 深度理解

### 2. **AI交易顾问 (AITradingAdvisor)**
- 📊 多层分析：
  - 技术分析（RSI, MACD, 趋势, 成交量）
  - 情感分析（新闻、社交媒体）
  - LLM深度分析（Gemini 2.0 Flash）
  
- 💰 智能建议：
  - 买入/卖出/持有信号
  - 入场价、止损价、止盈价
  - 理由解释和风险提示

### 3. **加密货币数据支持 (CryptoDataFetcher)**
- 🏦 支持交易所：
  - Upbit (업비트) - 韩国最大加密货币交易所
  - Bithumb (비썸) - 韩国第二大交易所
  
- 💹 实时数据：
  - 当前价格
  - 24小时涨跌幅
  - 成交量
  - 历史OHLCV数据

### 4. **持仓管理 (PositionTracker)**
- 📈 自动记录：
  - 买入/卖出操作
  - 持仓数量和成本
  - 盈亏计算
  - 交易历史

### 5. **用户认证 (User Whitelist)**
- 🔒 安全保护：
  - 用户白名单验证
  - 拒绝未授权访问
  - 记录访问日志

## 🚀 快速开始

### 1. 安装依赖

```bash
# 基础依赖
pip install python-telegram-bot python-dotenv loguru

# 韩国股票数据
pip install pykrx

# 加密货币数据
pip install pyupbit pybithumb

# AI模型
pip install google-generativeai transformers torch
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# Telegram Bot配置
TELEGRAM_BOT_TOKEN=你的Bot Token
TELEGRAM_CHAT_ID=你的Chat ID
TELEGRAM_AUTHORIZED_USERS=123456789,987654321  # 授权用户ID（逗号分隔）

# Google AI配置
GOOGLE_AI_API_KEY=你的Google AI API Key
```

### 3. 启动Bot

```bash
# 方式1: 使用快速启动脚本
python3 start_conversation_bot.py

# 方式2: 使用原始脚本
python3 telegram_bot_standalone.py
```

### 4. 开始对话

在Telegram中找到你的bot，发送消息：

```
买入三星电子 10股 价格75000
```

Bot会回复：
```
✅ 已开仓 삼성전자 (005930)
   数量: 10股
   价格: ₩75,000
   总金额: ₩750,000
   时间: 2024-01-20 14:30:00
```

## 📚 详细文档

### 文档索引

1. **[CONVERSATION_EXAMPLES.md](CONVERSATION_EXAMPLES.md)** - 对话示例大全
   - 8种对话类型的详细示例
   - 实战场景演示
   - 技术细节说明

2. **[AI_TRADING_ADVICE.md](AI_TRADING_ADVICE.md)** - AI交易建议指南
   - AI分析系统架构
   - 多层分析流程
   - 信号解读指南

3. **[AI_ADVICE_QUICK_REF.md](AI_ADVICE_QUICK_REF.md)** - 快速参考卡
   - 快速查询表格
   - 关键指标说明
   - 常见问题解答

4. **[TELEGRAM_BOT_SECURITY.md](TELEGRAM_BOT_SECURITY.md)** - 安全配置指南
   - 用户认证机制
   - 白名单配置
   - 安全最佳实践

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot Interface                    │
│  (telegram_bot_standalone.py)                               │
└────┬─────────────────────────────────────────────────────┬──┘
     │                                                       │
     ▼                                                       ▼
┌────────────────────────┐                        ┌─────────────────┐
│  ConversationHandler   │                        │ Command Handlers│
│  (自然语言处理)        │                        │ (/analyze, etc) │
└────┬──────────────┬────┘                        └─────────────────┘
     │              │
     │              └──────────────┐
     ▼                             ▼
┌──────────────────┐    ┌──────────────────────┐
│ AITradingAdvisor │    │  CryptoDataFetcher   │
│ (AI交易建议)     │    │  (加密货币数据)       │
└────┬─────────────┘    └──────────────────────┘
     │
     │  ┌─────────────────────────────────────────┐
     │  │ - 技术分析 (RSI, MACD, Trend, Volume)  │
     ├──┤ - 情感分析 (News, Social Media)        │
     │  │ - LLM深度分析 (Gemini 2.0 Flash)       │
     │  └─────────────────────────────────────────┘
     │
     ▼
┌────────────────────┐
│  PositionTracker   │
│  (持仓管理)        │
│  - 股票持仓        │
│  - 加密货币持仓    │
│  - 盈亏计算        │
└────────────────────┘
```

## 🔧 技术实现

### 意图识别流程

```python
用户消息 → ConversationHandler.process_message()
    ↓
规则匹配 (关键词 + 正则)
    ↓
确定性高？ → 是 → 执行相应处理器
    ↓ 否
AI理解 (Gemini)
    ↓
分类为8种意图之一
    ↓
执行相应处理器
    ↓
返回结果给用户
```

### 交易执行流程

```python
"买入三星电子 10股 价格75000"
    ↓
提取信息:
  - 动作: BUY_STOCK
  - 股票: 三星电子 → 005930
  - 数量: 10
  - 价格: 75000
    ↓
验证信息完整性
    ↓
调用 PositionTracker.open_position()
    ↓
记录交易并返回确认消息
```

### AI建议生成流程

```python
"给我三星电子的建议"
    ↓
AITradingAdvisor.generate_trading_advice()
    ↓
第1层: 基础分析
  - 获取pykrx数据
  - 计算技术指标
  - 评分 0-10
    ↓
第2层: 情感分析
  - 新闻聚合
  - 社交媒体分析
  - 评分 0-10
    ↓
第3层: LLM深度分析
  - 构建提示词
  - 调用Gemini API
  - 生成详细建议
    ↓
格式化输出 (Telegram Markdown)
    ↓
返回完整建议
```

## 📊 核心类和方法

### ConversationHandler

**文件**: `openclaw/skills/analysis/conversation_handler.py`

**关键方法**:
```python
# 主入口
async def process_message(user_message: str, user_id: int) -> str

# 意图识别
def _detect_intent(message: str) -> str
def _rule_based_intent_detection(message: str) -> Optional[str]
async def _ai_intent_detection(message: str) -> str

# 信息提取
def _extract_symbols(message: str) -> List[str]
def _extract_trade_details(message: str) -> Dict

# 处理器
async def _handle_buy(intent: str, symbols: List[str], details: Dict) -> str
async def _handle_sell(intent: str, symbols: List[str], details: Dict) -> str
async def _handle_ask_advice(symbols: List[str]) -> str
async def _handle_check_position(symbols: List[str]) -> str
async def _handle_portfolio_adjustment() -> str
async def _handle_market_analysis() -> str
async def _handle_chat(message: str) -> str
```

### AITradingAdvisor

**文件**: `openclaw/skills/analysis/ai_trading_advisor.py`

**关键方法**:
```python
# 主分析
async def generate_trading_advice(symbol: str, asset_type: str) -> Dict

# 分层分析
async def _basic_analysis(symbol: str, asset_type: str) -> Dict
async def _llm_deep_analysis(symbol: str, asset_type: str, basic_data: Dict) -> str

# 信号计算
def _calculate_targets(current_price: float, trend: str, volatility: float) -> Dict
def _aggregate_signals(basic_score: float, sentiment_score: float) -> tuple

# 格式化
def format_advice_for_telegram(advice: Dict) -> str
```

### CryptoDataFetcher

**文件**: `crypto_fetcher.py`

**关键方法**:
```python
# Upbit
async def get_upbit_markets() -> List[str]
async def get_upbit_price(symbol: str) -> Optional[Dict]
async def get_upbit_all_prices() -> Dict[str, Dict]

# Bithumb
async def get_bithumb_markets() -> List[str]
async def get_bithumb_price(symbol: str) -> Optional[Dict]
async def get_bithumb_all_prices() -> Dict[str, Dict]
```

### PositionTracker

**文件**: `openclaw/skills/execution/position_tracker.py`

**关键方法**:
```python
# 仓位操作
def open_position(symbol: str, quantity: float, entry_price: float, 
                  position_type: str, asset_type: str) -> Dict

def close_position(symbol: str, quantity: float, exit_price: float) -> Dict

# 查询
def get_position(symbol: str) -> Optional[Dict]
def get_all_positions() -> Dict
def get_pnl(symbol: str) -> Dict
```

## 🧪 测试脚本

### 测试AI建议功能

**文件**: `test_ai_trading_advisor.py`

```bash
python3 test_ai_trading_advisor.py
```

### 测试对话示例

**文件**: `example_ai_advice.py`

```bash
python3 example_ai_advice.py
```

## 📝 环境变量详解

```env
# ==========================================
# Telegram Bot配置
# ==========================================

# Bot Token（必填）
# 从 @BotFather 获取
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Chat ID（必填）
# 从 @userinfobot 获取，或使用群组/频道ID
TELEGRAM_CHAT_ID=123456789

# 授权用户（推荐）
# 逗号分隔的用户ID列表，只有这些用户可以使用bot
# 为空则允许所有用户（不推荐）
TELEGRAM_AUTHORIZED_USERS=123456789,987654321

# ==========================================
# Google AI配置
# ==========================================

# Google AI API Key（必填，用于AI建议）
# 从 Google AI Studio 获取
GOOGLE_AI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXX

# ==========================================
# 数据源配置（可选）
# ==========================================

# Finnhub API Key（备用数据源）
FINNHUB_API_KEY=your_finnhub_api_key

# ==========================================
# 系统配置（可选）
# ==========================================

# 日志级别
LOG_LEVEL=INFO

# Redis配置（如果使用缓存）
REDIS_HOST=localhost
REDIS_PORT=6379
```

## 🔍 常见问题

### Q1: Bot无法响应消息

**检查清单**:
1. ✅ TELEGRAM_BOT_TOKEN 是否正确
2. ✅ 你的用户ID是否在授权列表中
3. ✅ Bot是否正常运行（查看日志）
4. ✅ 网络连接是否正常

### Q2: AI建议返回错误

**检查清单**:
1. ✅ GOOGLE_AI_API_KEY 是否设置
2. ✅ API配额是否充足
3. ✅ 股票代码是否正确
4. ✅ pykrx是否能正常获取数据

### Q3: 加密货币数据获取失败

**检查清单**:
1. ✅ pyupbit 和 pybithumb 是否安装
2. ✅ 网络能否访问交易所API
3. ✅ 符号格式是否正确（BTC, ETH, XRP等）

### Q4: 持仓记录不更新

**检查清单**:
1. ✅ PositionTracker 是否正确初始化
2. ✅ 交易消息格式是否正确
3. ✅ 查看日志中的错误信息

## 🎯 下一步计划

- [ ] 价格提醒功能
- [ ] 自动交易执行（连接交易所API）
- [ ] 更多技术指标（布林带、KDJ等）
- [ ] 多语言支持（英语、日语等）
- [ ] 语音消息支持
- [ ] 图表生成（K线图、持仓饼图等）
- [ ] 回测功能集成
- [ ] 风险管理优化

## 📞 获取帮助

- 📖 查看文档: [CONVERSATION_EXAMPLES.md](CONVERSATION_EXAMPLES.md)
- 🔧 技术问题: 查看日志文件 `logs/`
- 💡 功能建议: 欢迎提Issue

---

🦞 **OpenClaw** - 让交易更智能！
