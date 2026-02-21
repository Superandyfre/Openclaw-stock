# 免费数据源使用指南

## 📊 已集成的免费API

所有API均**完全免费**使用（排除社媒和杠杆相关）

---

## 1. Binance Spot API ✅ (无需Key)

### 功能
- 实时订单簿（5/10/20/50/100档）
- K线数据（1m, 5m, 15m, 1h, 4h, 1d, 1w）
- 24小时行情统计

### 使用示例
```python
from openclaw.skills.data_collection.free_data_sources import FreeDataSourceConnector

connector = FreeDataSourceConnector()

# 获取订单簿
orderbook = connector.get_binance_orderbook('BTCUSDT', limit=20)
print(f"最优买价: {orderbook['bids'][0][0]}")
print(f"最优卖价: {orderbook['asks'][0][0]}")

# 获取K线
klines = connector.get_binance_klines('BTCUSDT', interval='1h', limit=100)
print(f"最新收盘价: {klines[-1]['close']}")

# 获取24小时统计
ticker = connector.get_binance_ticker_24h('BTCUSDT')
print(f"24h涨跌: {ticker['price_change_pct']:.2f}%")
```

### 速率限制
- 10次/秒（无需认证）

---

## 2. Alternative.me (恐慌贪婪指数) ✅

### 功能
- 加密货币恐慌贪婪指数（0-100）
- 历史数据（7天/30天/90天）

### 使用示例
```python
# 获取当前指数
fg_index = connector.get_fear_greed_index(limit=7)

print(f"当前指数: {fg_index['value']}/100")
print(f"分类: {fg_index['classification']}")
# 输出: 当前指数: 9/100
#      分类: EXTREME_FEAR (极度恐慌)

# 反向指标：极度恐慌时可能是买入机会
if fg_index['classification'] == 'EXTREME_FEAR':
    print("💡 市场极度恐慌，考虑逢低买入")
```

### 分类标准
- 0-24: EXTREME_FEAR (极度恐慌) → 买入信号
- 25-44: FEAR (恐慌)
- 45-55: NEUTRAL (中性)
- 56-74: GREED (贪婪)
- 75-100: EXTREME_GREED (极度贪婪) → 卖出信号

---

## 3. CoinGecko API ✅ (无需Key)

### 功能
- 实时价格、市值、成交量
- 历史图表数据（7天/30天/90天/1年）
- 币种信息

### 使用示例
```python
# 获取价格
btc_price = connector.get_coingecko_price('bitcoin')
print(f"价格: ${btc_price['price']:,.0f}")
print(f"市值: ${btc_price['market_cap']:,.0f}")
print(f"24h涨跌: {btc_price['change_24h']:+.2f}%")

# 获取历史数据
chart = connector.get_coingecko_market_chart('bitcoin', days=7)
prices = chart['prices']
print(f"7天前: ${prices[0]['price']:,.0f}")
print(f"当前: ${prices[-1]['price']:,.0f}")
```

### 常用币种ID
- `bitcoin` - BTC
- `ethereum` - ETH
- `cardano` - ADA
- `solana` - SOL
- `ripple` - XRP

### 速率限制
- 免费: 50次/分钟

---

## 4. FRED API (美联储数据) ⚠️ 需Key

### 申请API Key
**完全免费**，3步申请：
1. 访问: https://fred.stlouisfed.org/docs/api/api_key.html
2. 创建账户（免费）
3. 获取API Key

### 功能
- 联邦基金利率
- CPI通胀数据
- GDP增长率
- 失业率

### 使用示例
```python
# 在.env文件添加
# FRED_API_KEY=你的API密钥

api_key = os.getenv('FRED_API_KEY')

# 获取联邦基金利率
ffr = connector.get_fred_series('DFF', api_key=api_key, limit=30)
print(f"当前利率: {ffr[0]['value']:.2f}%")

# 获取CPI通胀
cpi = connector.get_fred_series('CPIAUCSL', api_key=api_key, limit=12)
print(f"最新CPI: {cpi[0]['value']}")
```

### 常用数据序列
- `DFF` - 联邦基金利率
- `CPIAUCSL` - CPI通胀
- `UNRATE` - 失业率
- `GDP` - GDP

---

## 5. Yahoo Finance API ✅ (通过yfinance)

### 功能
- 股票指数数据
- 黄金、原油等商品
- 美元指数

### 使用示例
```python
# 获取标普500
sp500 = connector.get_yahoo_finance_data('^GSPC', period='1mo')
print(f"标普500: {sp500['current_price']:.2f}")
print(f"月涨跌: {sp500['price_change_pct']:+.2f}%")

# 获取黄金
gold = connector.get_yahoo_finance_data('GC=F', period='1mo')
print(f"黄金: ${gold['current_price']:,.2f}/oz")

# 获取美元指数
dxy = connector.get_yahoo_finance_data('DX-Y.NYB', period='5d')
```

### 常用代码
- `^GSPC` - 标普500
- `^IXIC` - 纳斯达克
- `GC=F` - 黄金期货
- `CL=F` - 原油期货
- `DX-Y.NYB` - 美元指数

### 注意
- 速率限制较严格，连续请求可能被限制
- 建议间隔1-2秒

---

## 6. DeFiLlama API ✅ (无需Key)

### 功能
- DeFi协议TVL（总锁仓量）
- 协议收入、用户数
- 链上数据聚合

### 使用示例
```python
# 获取总TVL
tvl = connector.get_defillama_tvl()
print(f"DeFi总TVL: ${tvl['total_tvl']:,.0f}")

# 获取Uniswap数据
uniswap = connector.get_defillama_tvl('uniswap')
print(f"Uniswap TVL: ${uniswap['tvl']:,.0f}")
print(f"1day变化: {uniswap['change_1d']:+.2f}%")
```

### 常用协议
- `uniswap` - Uniswap DEX
- `aave` - Aave借贷
- `makerdao` - MakerDAO
- `compound` - Compound
- `curve` - Curve Finance

---

## 7. GitHub API ✅ (无需Token)

### 功能
- 仓库统计（Stars, Forks）
- 最近提交
- 开发活跃度

### 使用示例
```python
# 获取Bitcoin仓库统计
repo = connector.get_github_repo_stats('bitcoin', 'bitcoin')
print(f"Stars: {repo['stars']:,}")
print(f"Forks: {repo['forks']:,}")
print(f"最近更新: {repo['pushed_at']}")

# 查看最近提交
for commit in repo['recent_commits']:
    print(f"- {commit['message']}")
```

### 常用仓库
- `bitcoin/bitcoin` - Bitcoin Core
- `ethereum/go-ethereum` - Geth
- `solana-labs/solana` - Solana
- `cardano-foundation/cardano-node` - Cardano

### 速率限制
- 未认证: 60次/小时
- 认证: 5000次/小时（添加GitHub Token）

---

## 🚀 完整使用示例

### 综合市场分析
```python
from openclaw.skills.data_collection.free_data_sources import FreeDataSourceConnector

def analyze_market(symbol='BTCUSDT', coin_id='bitcoin'):
    connector = FreeDataSourceConnector()
    
    print("=== 综合市场分析 ===\n")
    
    # 1. Binance价格
    ticker = connector.get_binance_ticker_24h(symbol)
    print(f"【Binance】")
    print(f"价格: ${ticker['last_price']:,.2f}")
    print(f"24h涨跌: {ticker['price_change_pct']:+.2f}%")
    print(f"成交额: ${ticker['quote_volume']:,.0f}\n")
    
    # 2. 恐慌贪婪指数
    fg = connector.get_fear_greed_index()
    print(f"【市场情绪】")
    print(f"恐慌贪婪指数: {fg['value']}/100 ({fg['classification']})")
    
    if fg['classification'] in ['EXTREME_FEAR', 'FEAR']:
        print("💡 建议: 市场恐慌，可能存在买入机会\n")
    elif fg['classification'] in ['EXTREME_GREED', 'GREED']:
        print("⚠️  建议: 市场贪婪，注意风险\n")
    
    # 3. CoinGecko市值数据
    cg = connector.get_coingecko_price(coin_id)
    print(f"【CoinGecko】")
    print(f"市值: ${cg['market_cap']:,.0f}")
    print(f"24h成交量: ${cg['volume_24h']:,.0f}\n")
    
    # 4. 宏观环境（标普500）
    sp500 = connector.get_yahoo_finance_data('^GSPC', period='5d')
    if sp500:
        print(f"【宏观市场】")
        print(f"标普500: {sp500['current_price']:.2f} ({sp500['price_change_pct']:+.2f}%)\n")
    
    # 5. DeFi TVL
    tvl = connector.get_defillama_tvl()
    if tvl:
        print(f"【DeFi生态】")
        print(f"总TVL: ${tvl['total_tvl']:,.0f}\n")

# 运行分析
analyze_market()
```

---

## 💰 成本分析

| API | 费用 | 速率限制 | 是否需要Key |
|-----|------|---------|------------|
| Binance | 免费 | 10次/秒 | ❌ 否 |
| Alternative.me | 免费 | ~100次/天 | ❌ 否 |
| CoinGecko | 免费 | 50次/分钟 | ❌ 否 |
| FRED | 免费 | 无限制 | ✅ 免费Key |
| Yahoo Finance | 免费 | 2000次/小时 | ❌ 否 |
| DeFiLlama | 免费 | 300次/分钟 | ❌ 否 |
| GitHub | 免费 | 60次/小时 | ❌ 否 |

**总成本: $0/月** 🎉

---

## ⚠️ 已排除的数据源

以下数据源已按要求排除：

### 杠杆/衍生品相关
- ❌ 资金费率API
- ❌ 未平仓量
- ❌ 多空比
- ❌ 清算数据
- ❌ 期权数据
- ❌ 借贷利率

### 社交媒体
- ❌ Twitter API
- ❌ Reddit API
- ❌ LunarCrush
- ❌ Telegram Bot API

---

## 🔧 故障排除

### Yahoo Finance速率限制
```python
# 添加延迟
import time
time.sleep(2)  # 请求间隔2秒
```

### CoinGecko速率限制
```python
# 使用缓存
from functools import lru_cache

@lru_cache(maxsize=128)
def get_cached_price(coin_id):
    return connector.get_coingecko_price(coin_id)
```

### GitHub速率限制
```python
# 添加GitHub Token (免费，5000次/小时)
# 在.env添加: GITHUB_TOKEN=你的token

token = os.getenv('GITHUB_TOKEN')
repo = connector.get_github_repo_stats('bitcoin', 'bitcoin', token=token)
```

---

## 📝 下一步集成

将这些数据源整合到智能信号聚合系统：

```python
from openclaw.skills.analysis.smart_signal_aggregator import SmartSignalAggregator
from openclaw.skills.data_collection.free_data_sources import FreeDataSourceConnector

aggregator = SmartSignalAggregator()
connector = FreeDataSourceConnector()

# 获取实时数据
orderbook = connector.get_binance_orderbook('BTCUSDT', limit=20)
klines = connector.get_binance_klines('BTCUSDT', interval='1h', limit=200)
fg_index = connector.get_fear_greed_index()

# 分析并生成信号
# ... (待实现)
```

---

## 📚 参考文档

- [Binance API文档](https://binance-docs.github.io/apidocs/spot/en/)
- [CoinGecko API文档](https://www.coingecko.com/en/api/documentation)
- [FRED API文档](https://fred.stlouisfed.org/docs/api/)
- [DeFiLlama API文档](https://defillama.com/docs/api)
- [GitHub API文档](https://docs.github.com/en/rest)
