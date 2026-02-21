# 🤖 AI交易建议 - 快速参考

## ✅ 功能已实现

AI交易建议系统已完全集成，支持：
- ✅ 技术分析（RSI、MACD、趋势）
- ✅ 情绪分析（新闻、市场情绪）
- ✅ Gemini AI深度分析（可选）
- ✅ 多策略信号聚合
- ✅ Telegram Bot集成

---

## 🚀 快速使用（3种方式）

### 方式1：Telegram Bot（推荐）

```
/analyze 005930        # 分析三星电子
/advice               # 分析当前持仓
```

### 方式2：Python代码

```python
from openclaw.skills.analysis.ai_trading_advisor import AITradingAdvisor

advisor = AITradingAdvisor()

advice = await advisor.generate_trading_advice(
    symbol='005930',
    name='삼성전자',
    current_price=75000,
    price_data={'change_pct': 2.5, 'volume_ratio': 2.0},
    technical_indicators={'rsi': 45},
    sentiment={'score': 0.6}
)

print(f"建议: {advice['action']} (置信度: {advice['confidence']:.0%})")
```

### 方式3：测试脚本

```bash
python test_ai_trading_advisor.py    # 完整测试
python example_ai_advice.py          # 快速示例
```

---

## 📊 建议格式

```
🤖 AI 交易建议

📊 삼성전자 (005930)
💰 当前价格: ₩75,000

🎯 建议: 🟢 买入
⭐ 置信度: 高 (⭐⭐⭐⭐) (75%)
💪 强度评分: 7.5/10
🔍 分析来源: AI (Gemini)

📈 目标价位:
  入场: ₩75,000
  止盈1: ₩76,500 (+2%)
  止盈2: ₩78,750 (+5%)
  止损: ₩73,500

💡 关键要点:
  1. 价格突破阻力位，动能强劲
  2. 成交量放大确认突破有效
  3. RSI健康，未进入超买
  4. 市场情绪积极
```

---

## 🎯 建议类型

| 建议 | 含义 | 置信度 |
|------|------|--------|
| 🟢 BUY | 买入信号 | >60% |
| 🔴 SELL | 卖出信号 | >60% |
| 🟡 HOLD | 观望持有 | <60% |

**置信度等级：**
- ⭐⭐⭐⭐⭐ 极高 (80%+) 
- ⭐⭐⭐⭐ 高 (60-80%)
- ⭐⭐⭐ 中等 (40-60%)
- ⭐⭐ 低 (20-40%)
- ⭐ 极低 (<20%)

---

## 🔧 配置（可选）

### 启用AI深度分析

编辑 `.env` 文件：
```bash
GOOGLE_AI_API_KEY=你的API密钥
```

获取免费API密钥：https://aistudio.google.com/apikey

---

## 📁 相关文件

**核心代码：**
- `openclaw/skills/analysis/ai_trading_advisor.py` - AI建议引擎
- `telegram_bot_standalone.py` - Telegram集成

**测试与示例：**
- `test_ai_trading_advisor.py` - 完整功能测试
- `example_ai_advice.py` - 快速示例代码

**文档：**
- `AI_TRADING_ADVICE.md` - 完整使用文档
- `TELEGRAM_BOT_SECURITY.md` - Bot安全配置

---

## ⚡ 快速测试

```bash
# 1. 测试基础功能（无需API密钥）
python example_ai_advice.py

# 2. 测试完整功能（包括AI分析）
python test_ai_trading_advisor.py

# 3. 启动Telegram Bot
python telegram_bot_standalone.py
```

---

## ⚠️ 重要提示

**免责声明：**
- 🚨 AI建议仅供参考，不构成投资建议
- ⚠️ 市场有风险，投资需谨慎
- 💰 请勿盲目跟随AI建议
- 📊 建议综合多方面因素决策

**最佳实践：**
1. ✅ 只在高置信度(>80%)时操作
2. ✅ 严格遵守止损价位
3. ✅ 分批建仓，不要全仓
4. ✅ 验证多个信号一致性
5. ✅ 记录每次交易决策

---

## 🆘 故障排除

### AI分析不工作
- 检查 `GOOGLE_AI_API_KEY` 是否设置
- 确认网络可访问Google AI

### 分析失败
- 检查股票代码是否正确  
- 确保 `pykrx` 已安装

### 置信度总是很低
- 等待更明确的市场信号
- 补充更多数据源

---

## 📚 完整文档

查看 [AI_TRADING_ADVICE.md](AI_TRADING_ADVICE.md) 获取：
- 详细API参考
- 高级配置选项
- 故障排除指南
- 最佳实践建议

---

**开始使用AI交易建议，让数据驱动你的决策！** 🚀📈
