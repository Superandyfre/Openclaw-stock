# 🤖 AI 交易建议功能使用指南

## 📋 功能概述

AI交易建议系统整合了技术分析、情绪分析和大语言模型(LLM)深度分析，为你的股票交易提供智能建议。

### 核心特性

✅ **多层分析架构**
- 📊 基础技术分析（RSI、MACD、趋势判断）
- 💭 情绪分析（新闻、市场情绪）
- 🤖 Gemini AI深度分析（可选）
- 🎯 多策略信号聚合

✅ **智能建议生成**
- BUY / SELL / HOLD 三种明确建议
- 1-10分置信度评分
- 目标价位计算（入场、止盈、止损）
- 关键理由和风险提示

✅ **Telegram集成**
- `/analyze 股票代码` - 分析特定股票
- `/advice` - 分析当前持仓
- 精美的消息格式化

---

## 🚀 快速开始

### 1. 基础模式（无需API密钥）

基础模式使用技术指标和规则引擎，不需要任何API密钥：

```python
from openclaw.skills.analysis.ai_trading_advisor import AITradingAdvisor

advisor = AITradingAdvisor()

advice = await advisor.generate_trading_advice(
    symbol='005930',
    name='삼성전자',
    current_price=75000,
    price_data={'change_pct': 2.5, 'volume_ratio': 3.0},
    technical_indicators={'rsi': 45, 'macd': {'macd': 100}},
    sentiment={'overall_sentiment': 'positive', 'score': 0.6}
)

print(f"建议: {advice['action']}")
print(f"置信度: {advice['confidence']}")
```

### 2. AI模式（推荐，需要API密钥）

启用Gemini AI深度分析：

**步骤1：获取API密钥**
1. 访问 https://aistudio.google.com/apikey
2. 登录Google账号
3. 创建API密钥（免费，每月5000次请求）

**步骤2：配置环境变量**

编辑 `.env` 文件：
```bash
GOOGLE_AI_API_KEY=你的API密钥
```

**步骤3：使用AI建议**
```python
advisor = AITradingAdvisor(api_key="你的API密钥")

advice = await advisor.generate_trading_advice(
    symbol='035420',
    name='NAVER',
    current_price=250000,
    price_data={...},
    technical_indicators={...},
    sentiment={...},
    news=[{'title': '相关新闻'}]  # AI会分析新闻
)
```

---

## 📱 Telegram Bot 使用

### 命令1: `/analyze 股票代码`

分析特定股票并获取交易建议：

```
/analyze 005930
```

**Bot回复示例：**
```
🤖 AI 交易建议

📊 삼성전자 (005930)
💰 当前价格: ₩75,000

🎯 建议: 🟢 买入
⭐ 置信度: 高 (⭐⭐⭐⭐) (70%)
💪 强度评分: 7.5/10
🔍 分析来源: AI (Gemini)

📈 目标价位:
  入场: ₩75,000
  止盈1: ₩76,500 (+2%)
  止盈2: ₩78,750 (+5%)
  止损: ₩73,500

💡 关键要点:
  1. 价格突破关键阻力位，上涨动能强劲
  2. 成交量放大3倍，确认突破有效性
  3. RSI处于健康区间，未进入超买
  4. 市场情绪积极，新闻面利好
  5. 建议分批建仓，设置止损保护

⏰ 2026-02-19 14:30:25
```

### 命令2: `/advice`

分析你当前的所有持仓（最多3个）：

```
/advice
```

Bot会依次分析每个持仓，给出独立建议。

---

## 🎯 建议详解

### 动作类型

| 建议 | 含义 | 置信度要求 |
|------|------|-----------|
| 🟢 BUY | 买入信号 | >60% |
| 🔴 SELL | 卖出信号 | >60% |
| 🟡 HOLD | 观望/持有 | <60%或信号冲突 |

### 置信度等级

- ⭐⭐⭐⭐⭐ 极高 (80%+) - 强烈建议
- ⭐⭐⭐⭐ 高 (60-80%) - 可以考虑
- ⭐⭐⭐ 中等 (40-60%) - 谨慎观察
- ⭐⭐ 低 (20-40%) - 不建议
- ⭐ 极低 (<20%) - 避免操作

### 强度评分

0-10分综合评分，考虑以下因素：
- 价格趋势（上涨/下跌）
- RSI动量（超买/超卖）
- 成交量确认
- 市场情绪
- 策略信号一致性

---

## 🔧 高级配置

### 自定义分析参数

```python
advisor = AITradingAdvisor()

# 传入更详细的数据
advice = await advisor.generate_trading_advice(
    symbol='005930',
    name='삼성전자',
    current_price=75000,
    
    # 价格数据
    price_data={
        'change_pct': 2.5,      # 涨跌幅
        'volume_ratio': 3.0,    # 成交量比率
        'high': 76000,          # 最高价
        'low': 74000            # 最低价
    },
    
    # 技术指标
    technical_indicators={
        'rsi': 45,              # RSI指标
        'macd': {
            'macd': 100,
            'signal': 90,
            'histogram': 10
        }
    },
    
    # 情绪分析
    sentiment={
        'overall_sentiment': 'positive',
        'score': 0.6,           # -1到1
        'article_count': 5      # 新闻数量
    },
    
    # 新闻（AI会分析）
    news=[
        {'title': '삼성전자 실적 호조'},
        {'title': '반도체 업황 개선'}
    ],
    
    # 策略信号
    strategy_signals=[
        {'action': 'BUY', 'weight': 0.3},
        {'action': 'BUY', 'weight': 0.25}
    ]
)
```

### 历史记录查询

```python
# 获取所有建议历史（最近24小时）
history = advisor.get_advice_history()

# 获取特定股票的历史
samsung_history = advisor.get_advice_history(symbol='005930', hours=24)

for record in samsung_history:
    print(f"{record['timestamp']}: {record['advice']['action']}")
```

---

## 📊 API参考

### AITradingAdvisor类

#### 初始化
```python
AITradingAdvisor(api_key: Optional[str] = None)
```

参数：
- `api_key`: Google AI API密钥（可选，从环境变量读取）

#### 主要方法

**generate_trading_advice**
```python
await advisor.generate_trading_advice(
    symbol: str,                      # 股票代码
    name: str,                        # 股票名称
    current_price: float,             # 当前价格
    price_data: Dict[str, Any],       # 价格数据
    technical_indicators: Dict,       # 技术指标
    sentiment: Dict,                  # 情绪分析
    news: List[Dict] = None,          # 新闻列表
    strategy_signals: List[Dict] = None  # 策略信号
) -> Dict[str, Any]
```

返回：
```python
{
    'symbol': '005930',
    'name': '삼성전자',
    'action': 'BUY',              # BUY/SELL/HOLD
    'confidence': 0.75,           # 0-1
    'confidence_level': '高 (⭐⭐⭐⭐)',
    'strength_score': 7.5,        # 0-10
    'targets': {                  # 目标价位
        'entry': 75000,
        'take_profit_1': 76500,
        'stop_loss': 73500
    },
    'key_points': [...],          # 关键要点列表
    'reasoning': '...',           # 推理说明
    'source': 'AI (Gemini)'       # 数据来源
}
```

**format_advice_for_telegram**
```python
message = advisor.format_advice_for_telegram(advice)
# 返回格式化的Telegram消息字符串
```

**get_advice_history**
```python
history = advisor.get_advice_history(
    symbol: Optional[str] = None,  # 特定股票（可选）
    hours: int = 24                # 时间范围（小时）
)
```

---

## 🧪 测试

运行测试脚本：

```bash
python test_ai_trading_advisor.py
```

测试包括：
1. ✅ 基础分析测试（无需API密钥）
2. 🤖 AI深度分析测试（需要API密钥）
3. 📊 批量分析测试

---

## ⚠️ 重要提示

### 免责声明

🚨 **AI交易建议仅供参考，不构成投资建议！**

- ✅ 建议基于技术分析和历史数据
- ⚠️ 市场有风险，投资需谨慎
- 📊 建议综合考虑多方面因素再做决策
- 💰 请勿盲目跟随AI建议进行大额交易
- 🎓 建议作为学习和辅助工具使用

### 最佳实践

1. **谨慎使用置信度**
   - 高置信度(>80%)才考虑操作
   - 低置信度建议仅供参考

2. **设置止损**
   - 严格遵守建议的止损价位
   - 亏损超过2%及时止损

3. **分批操作**
   - 不要一次性全仓买入
   - 建议分2-3批建仓

4. **验证信号**
   - 结合多个策略信号
   - 查看相关新闻确认

5. **记录追踪**
   - 记录每次交易决策
   - 定期回顾建议质量

---

## 🛠️ 故障排除

### 问题1: AI分析不可用

**现象：** `source: 'Technical Analysis'` 而非 `AI (Gemini)`

**解决：**
1. 检查 `GOOGLE_AI_API_KEY` 是否设置
2. 验证API密钥有效性
3. 确保网络可以访问Google AI

### 问题2: 分析失败

**现象：** `❌ 分析失败`

**解决：**
1. 检查股票代码是否正确
2. 确保pykrx已安装
3. 查看日志了解详细错误

### 问题3: 置信度总是很低

**可能原因：**
- 市场信号不明确
- 技术指标相互矛盾
- 缺少新闻或情绪数据

**建议：**
- 等待更明确的信号
- 补充更多数据源
- 暂时观望

---

## 📚 相关文档

- [Telegram Bot Security](TELEGRAM_BOT_SECURITY.md) - Bot安全配置
- [README.md](README.md) - 项目总览
- [QUICKSTART.md](QUICKSTART.md) - 快速开始指南

---

**祝交易顺利！** 📈🚀
