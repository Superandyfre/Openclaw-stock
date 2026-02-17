# 🦞 OpenClaw - AI-Driven Automated Trading System

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Security: Updated](https://img.shields.io/badge/security-updated-green.svg)](SECURITY.md)

An advanced AI-powered automated trading system that supports both stocks and cryptocurrencies, featuring a unique architecture combining high-frequency monitoring with intelligent anomaly detection.

## 🎯 Key Features

### Intelligent Architecture
- **High-Frequency Monitoring** (15s intervals): Uses dedicated AI models for fast, efficient market analysis
- **Anomaly-Triggered Deep Analysis**: LLM-based analysis (Phi-3.5 Mini) activated only when anomalies are detected
- **Multi-Asset Support**: Stocks (Yahoo Finance) + Cryptocurrencies (Upbit WebSocket)
- **Zero-Cost Operation**: $0/month using free APIs and open-source models

### AI Models Integration

#### Dedicated Models (High-Frequency, <500ms)
- **FinBERT**: Sentiment analysis for financial news (ProsusAI/finbert)
- **CryptoBERT**: Cryptocurrency market sentiment (ElKulako/cryptobert)
- **Chronos**: Time series price prediction (amazon/chronos-t5-small)
- **Isolation Forest**: Real-time anomaly detection

#### LLM (Anomaly-Triggered, 2-3s)
- **Phi-3.5 Mini**: Deep contextual analysis when anomalies detected
- **Smart Prompt Engineering**: Structured decision-making framework
- **Risk Assessment**: Automated risk scoring and recommendations

### Trading Capabilities
- **Multiple Strategies**: Trend Following, Mean Reversion, Momentum
- **Advanced Risk Management**: Position sizing, stop-loss, take-profit
- **Real-time Execution**: Order management with dry-run mode
- **Portfolio Tracking**: P&L, win rate, Sharpe ratio, max drawdown

### Data Sources
- **Stocks**: Yahoo Finance API (10 symbols, 2000 req/hour)
- **Crypto**: Upbit WebSocket (15 cryptocurrencies, real-time)
- **News**: Naver News API, CryptoPanic (~20 requests/day)
- **Announcements**: DART API (Korean Financial Supervisory Service)

## 📊 Architecture Design

```
┌─────────────────────────────────────────────────────────────┐
│                   OpenClaw Trading Engine                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │   High-Frequency Loop (15s) - Dedicated Models       │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │  1. Market Data Fetch (Stocks + Crypto)              │  │
│  │  2. Technical Indicators (50ms)                      │  │
│  │  3. Anomaly Detection (10ms) ─────┐                  │  │
│  │  4. Trading Signals (100ms)       │                  │  │
│  └───────────────────────────────────┼──────────────────┘  │
│                                      │                      │
│                         ┌────────────▼─────────────┐        │
│                         │   Anomaly Detected?      │        │
│                         └────────────┬─────────────┘        │
│                                      │ YES                  │
│                         ┌────────────▼─────────────┐        │
│                         │  LLM Deep Analysis (3s)  │        │
│                         │  - Context gathering     │        │
│                         │  - Root cause analysis   │        │
│                         │  - Risk assessment       │        │
│                         │  - Action recommendation │        │
│                         └──────────────────────────┘        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │   News Monitoring Loop (1h)                          │  │
│  │   - Aggregate news from multiple sources             │  │
│  │   - Sentiment analysis                               │  │
│  │   - Store for context                                │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- Redis (optional, for caching)
- 8GB RAM minimum
- Internet connection

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/Superandyfre/Openclaw-stock.git
cd Openclaw-stock
```

2. **Install dependencies**
```bash
# Core dependencies
pip install -r requirements.txt

# AI models (optional, for full functionality)
pip install -r requirements-ai.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your API keys (optional for testing)
```

4. **Run the system**
```bash
python main.py
```

## ⚙️ Configuration

### API Configuration (`openclaw/config/api_config.yaml`)

```yaml
yahoo_finance:
  stocks:
    - AAPL    # Apple
    - MSFT    # Microsoft
    - GOOGL   # Google
    # ... more stocks

upbit:
  cryptocurrencies:
    - KRW-BTC    # Bitcoin
    - KRW-ETH    # Ethereum
    # ... more cryptos
```

### Strategy Configuration (`openclaw/config/strategy_config.yaml`)

```yaml
strategies:
  - name: "Trend Following"
    enabled: true
    parameters:
      ma_short: 20
      ma_long: 50
```

### Risk Configuration (`openclaw/config/risk_config.yaml`)

```yaml
risk_management:
  max_position_size: 0.1      # 10% max per position
  max_loss_per_trade: 0.02    # 2% max loss per trade
  max_daily_loss: 0.05        # 5% max daily loss
  max_drawdown: 0.15          # 15% max drawdown
```

## 📈 Performance Metrics

### Resource Usage
- **CPU**: <15% (high-frequency loop)
- **Memory**: <2GB (without AI models), <8GB (with all models)
- **Network**: Minimal (<100KB/s average)

### Processing Speed
- **High-frequency cycle**: <500ms target (includes data fetch + analysis)
- **Anomaly detection**: ~10ms
- **Sentiment analysis**: ~50ms
- **LLM deep analysis**: 2-3s (only on anomalies)

### API Cost Analysis
| Service | Free Tier | Usage | Monthly Cost |
|---------|-----------|-------|--------------|
| Yahoo Finance | 2000 req/hr | ~1440/day | **$0** |
| Upbit WebSocket | Unlimited | Real-time | **$0** |
| Naver News | N/A | ~20/day | **$0** |
| CryptoPanic | Limited | ~20/day | **$0** |
| DART | 240/day | ~24/day | **$0** |
| **Total** | | | **$0/month** |

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest openclaw/tests/

# Run specific test file
pytest openclaw/tests/test_engine.py -v

# Run with coverage
pytest --cov=openclaw openclaw/tests/
```

## 📝 Usage Examples

### Basic Usage

```python
from openclaw.core.engine import OpenClawEngine
from openclaw.utils.logger import setup_logger

async def main():
    logger = setup_logger()
    engine = OpenClawEngine()
    
    await engine.start()
    # Engine will run monitoring loops automatically
```

### Custom Strategy

```python
from openclaw.skills.analysis import StrategyEngine

# Add custom strategy to config/strategy_config.yaml
strategies_config = [
    {
        "name": "My Custom Strategy",
        "enabled": True,
        "parameters": {
            "custom_param": 42
        }
    }
]
```

### Risk Management

```python
from openclaw.skills.analysis import RiskManagement

risk_mgr = RiskManagement(risk_config)

# Calculate position size
position_size = risk_mgr.calculate_position_size(
    portfolio_value=100000,
    entry_price=150.0
)

# Calculate stop loss
stop_loss = risk_mgr.calculate_stop_loss(entry_price=150.0)
```

## 🔒 Security & Safety

### Security Measures

All dependencies are regularly updated to patch known vulnerabilities. See [SECURITY.md](SECURITY.md) for details.

**Recent Security Updates** (2026-02-17):
- ✅ aiohttp 3.9.1 → 3.13.3 (Fixed zip bomb, DoS, directory traversal)
- ✅ torch 2.1.2 → 2.6.0 (Fixed buffer overflow, use-after-free, RCE)
- ✅ transformers 4.36.2 → 4.48.0 (Fixed deserialization attacks)

### Built-in Safety Features
- **Dry Run Mode**: Default mode simulates trading without real execution
- **Risk Limits**: Multiple layers of risk management
- **Position Sizing**: Automatic calculation based on portfolio value
- **Stop Loss**: Configurable stop-loss mechanisms
- **Input Validation**: All external inputs validated
- **Secure Defaults**: No hardcoded secrets, environment-based configuration

### Important Warnings
⚠️ **This system is for educational purposes only**
⚠️ **Always test thoroughly in dry-run mode before live trading**
⚠️ **Never invest more than you can afford to lose**
⚠️ **Past performance does not guarantee future results**
⚠️ **Review [SECURITY.md](SECURITY.md) before deployment**

## 📚 Project Structure

```
openclaw/
├── config/                 # Configuration files
│   ├── api_config.yaml
│   ├── strategy_config.yaml
│   └── risk_config.yaml
├── skills/                 # Modular skills
│   ├── data_collection/   # Market data & news
│   ├── analysis/          # AI models & strategies
│   ├── execution/         # Order & position management
│   └── monitoring/        # System health & alerts
├── core/                  # Core engine
│   ├── engine.py         # Main orchestration
│   ├── scheduler.py      # Task scheduling
│   └── database.py       # Data persistence
├── utils/                 # Utilities
│   ├── logger.py
│   ├── api_client.py
│   └── helpers.py
└── tests/                 # Unit tests
```

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt -r requirements-ai.txt
pip install pytest pytest-asyncio black flake8

# Run code formatting
black openclaw/

# Run linting
flake8 openclaw/

# Run tests
pytest
```

## 🐛 Known Issues & Limitations

- AI models require significant memory (8GB+ recommended)
- Some API keys required for full functionality
- Backtesting framework not yet implemented
- Limited exchange integration (Upbit only for crypto)

## 🗺️ Roadmap

- [ ] Add more exchange integrations (Binance, Coinbase)
- [ ] Implement backtesting framework
- [ ] Add web dashboard for monitoring
- [ ] Enhance LLM prompts for better decision-making
- [ ] Add more technical indicators
- [ ] Implement paper trading mode with realistic slippage
- [ ] Add support for options and futures

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **FinBERT**: ProsusAI for financial sentiment analysis
- **Chronos**: Amazon Science for time series forecasting
- **Transformers**: HuggingFace for the amazing library
- **yfinance**: For easy Yahoo Finance API access
- **Upbit**: For cryptocurrency market data

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Superandyfre/Openclaw-stock/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Superandyfre/Openclaw-stock/discussions)

## ⚖️ Disclaimer

This software is provided "as is", without warranty of any kind. Trading stocks and cryptocurrencies involves substantial risk of loss. The authors and contributors are not responsible for any financial losses incurred through the use of this software.

**USE AT YOUR OWN RISK**

---

Made with ❤️ by the OpenClaw Team | Star ⭐ this repo if you find it useful!