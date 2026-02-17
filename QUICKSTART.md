# OpenClaw - Quick Start Guide

Get started with OpenClaw in 5 minutes!

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- 2GB+ RAM (8GB+ recommended for AI models)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Superandyfre/Openclaw-stock.git
cd Openclaw-stock
```

### 2. Install Core Dependencies

```bash
pip install -r requirements.txt
```

### 3. (Optional) Install AI Models

For full AI functionality (FinBERT, Chronos, etc.):

```bash
pip install -r requirements-ai.txt
```

**Note**: AI models require 8GB+ RAM and will download ~2GB of model files.

### 4. Validate Installation

```bash
python validate.py
```

You should see:
```
✅ All validation tests passed!
```

## Configuration (Optional)

### Basic Configuration

The system works out-of-the-box with mock data. For real market data:

1. Copy environment template:
```bash
cp .env.example .env
```

2. Edit `.env` with your API keys (all optional):

```bash
# Stock market data
YAHOO_FINANCE_API_KEY=your_key_here

# News sources
NAVER_CLIENT_ID=your_id_here
NAVER_CLIENT_SECRET=your_secret_here
CRYPTOPANIC_API_KEY=your_key_here

# Korean financial data
DART_API_KEY=your_key_here

# Telegram alerts (optional)
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### Advanced Configuration

Edit configuration files in `openclaw/config/`:

#### api_config.yaml
```yaml
yahoo_finance:
  stocks:
    - AAPL  # Add your stocks here
    - MSFT
    - GOOGL
```

#### strategy_config.yaml
```yaml
strategies:
  - name: "Trend Following"
    enabled: true
    parameters:
      ma_short: 20
      ma_long: 50
```

#### risk_config.yaml
```yaml
risk_management:
  max_position_size: 0.1      # 10% max per position
  max_loss_per_trade: 0.02    # 2% max loss per trade
```

## Running the System

### Start OpenClaw

```bash
python main.py
```

You'll see output like:
```
🦞 Starting OpenClaw Auto Trading System
✅ All monitoring loops started
🔄 High-frequency cycle #1
```

### Stop the System

Press `Ctrl+C` to gracefully shutdown:
```
⏹️  Shutting down gracefully...
✅ OpenClaw Engine stopped gracefully
```

## Understanding the Output

### Normal Operation

```
🔄 High-frequency cycle #1
✅ High-frequency cycle completed in 234ms
📰 Fetching news updates
```

### Anomaly Detection

```
🚨 Anomaly detected for AAPL: {'severity': 'high', 'score': -0.45}
🤖 Starting deep LLM analysis for AAPL
✅ LLM analysis complete for AAPL: HOLD
```

### Trading Signals

```
📊 Signals for AAPL: 2
💼 Executing signal for AAPL: BUY
Order created: ORD-20260217-000001
```

## Monitoring

### Check Logs

Logs are saved to `logs/openclaw.log`:

```bash
tail -f logs/openclaw.log
```

### Performance Metrics

The system automatically tracks:
- High-frequency cycle time (target: <500ms)
- API response times
- Anomaly detection rates
- Signal generation frequency

## Safety Features

### Dry Run Mode (Default)

By default, all trading is simulated. To enable real trading:

1. Edit `.env`:
```bash
AUTO_TRADING_ENABLED=true
DRY_RUN=false
```

⚠️ **WARNING**: Only enable real trading after thorough testing!

### Risk Limits

Built-in protections:
- Maximum position size: 10% of portfolio
- Maximum loss per trade: 2%
- Maximum daily loss: 5%
- Maximum drawdown: 15%

## Troubleshooting

### Import Errors

If you see import errors:
```bash
pip install -r requirements.txt --force-reinstall
```

### Module Not Found

Ensure you're in the project directory:
```bash
cd Openclaw-stock
python main.py
```

### AI Model Warnings

```
WARNING: Transformers not available, sentiment analysis will be limited
```

This is normal if you haven't installed AI dependencies. The system will use fallback methods.

To enable AI models:
```bash
pip install -r requirements-ai.txt
```

### Redis Connection Failed

```
WARNING: Failed to connect to Redis: ... Using in-memory cache.
```

This is normal if Redis isn't installed. The system will use in-memory caching instead.

To install Redis (optional):
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis
```

## Testing

### Run Unit Tests

```bash
pytest openclaw/tests/ -v
```

### Test Specific Component

```bash
# Test technical analysis
python -c "from openclaw.skills.analysis.technical_analysis import TechnicalAnalysis; ta = TechnicalAnalysis(); print('OK')"

# Test database
python -c "from openclaw.core.database import DatabaseManager; db = DatabaseManager(); db.set('test', 1); assert db.get('test') == 1; print('OK')"
```

## Performance Optimization

### Reduce Resource Usage

Edit `openclaw/config/api_config.yaml` to monitor fewer assets:

```yaml
yahoo_finance:
  stocks:
    - AAPL  # Monitor only 1-2 stocks initially
    
upbit:
  cryptocurrencies:
    - KRW-BTC  # Monitor only 1-2 cryptos initially
```

### Increase Monitoring Interval

In `openclaw/core/engine.py`, change the interval:

```python
# Change from 15 seconds to 60 seconds
await self.scheduler.schedule_periodic(
    "high_frequency_monitor",
    self._high_frequency_monitor_loop,
    60  # Changed from 15
)
```

## Next Steps

1. **Read the full README**: See `README.md` for detailed documentation
2. **Customize strategies**: Edit `openclaw/config/strategy_config.yaml`
3. **Add custom indicators**: Modify `openclaw/skills/analysis/technical_analysis.py`
4. **Integrate more exchanges**: Add to `openclaw/skills/data_collection/`
5. **Build a dashboard**: Create a web UI for monitoring

## Getting Help

- **Issues**: https://github.com/Superandyfre/Openclaw-stock/issues
- **Discussions**: https://github.com/Superandyfre/Openclaw-stock/discussions

## License

MIT License - See LICENSE file for details.

---

**Happy Trading! 🦞📈**

*Remember: This is for educational purposes. Always test thoroughly before risking real money.*
