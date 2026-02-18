"""
Enhanced Telegram bot for portfolio management and trading
"""
import os
import re
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from loguru import logger

from openclaw.core.portfolio_manager import PortfolioManager
from openclaw.core.database import DatabaseManager
from openclaw.skills.monitoring.asset_name_fetcher import AssetNameFetcher

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Google Generative AI not available")

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI client not available")


class EnhancedTelegramBot:
    """
    Enhanced Telegram bot with real-time asset names and AI recommendations
    
    Features:
    - Portfolio management (stocks & crypto)
    - Real-time asset names via APIs
    - AI recommendations (Gemini Flash / DeepSeek-V3)
    - Natural language support (Korean/English)
    - Trading commands
    """
    
    def __init__(
        self,
        token: str,
        chat_id: str,
        portfolio_manager: PortfolioManager,
        db_manager: Optional[DatabaseManager] = None
    ):
        """
        Initialize enhanced Telegram bot
        
        Args:
            token: Telegram bot token
            chat_id: Telegram chat ID
            portfolio_manager: Portfolio manager instance
            db_manager: Database manager for caching
        """
        self.token = token
        self.chat_id = chat_id
        self.portfolio = portfolio_manager
        self.db = db_manager or DatabaseManager()
        self.app: Optional[Application] = None
        self.asset_fetcher: Optional[AssetNameFetcher] = None
        
        # LLM clients
        self.gemini_client = None
        self.deepseek_client = None
        self._setup_llm_clients()
    
    def _setup_llm_clients(self):
        """Setup LLM clients for AI recommendations"""
        # Setup Gemini Flash (primary)
        if GEMINI_AVAILABLE:
            api_key = os.getenv('GOOGLE_AI_API_KEY')
            if api_key:
                try:
                    genai.configure(api_key=api_key)
                    self.gemini_client = genai.GenerativeModel('gemini-1.5-flash')
                    logger.info("✅ Gemini Flash configured")
                except Exception as e:
                    logger.warning(f"Failed to configure Gemini: {e}")
        
        # Setup DeepSeek-V3 (backup)
        if OPENAI_AVAILABLE:
            api_key = os.getenv('DEEPSEEK_API_KEY')
            if api_key:
                try:
                    self.deepseek_client = AsyncOpenAI(
                        api_key=api_key,
                        base_url="https://api.deepseek.com"
                    )
                    logger.info("✅ DeepSeek-V3 configured as backup")
                except Exception as e:
                    logger.warning(f"Failed to configure DeepSeek: {e}")
    
    async def _get_llm_response(self, prompt: str) -> str:
        """
        Get AI response using Gemini Flash or DeepSeek-V3
        
        Args:
            prompt: Prompt for the LLM
        
        Returns:
            LLM response text
        """
        # Try Gemini Flash first
        if self.gemini_client:
            try:
                response = self.gemini_client.generate_content(prompt)
                return response.text
            except Exception as e:
                logger.warning(f"Gemini failed: {e}, trying DeepSeek...")
        
        # Fallback to DeepSeek-V3
        if self.deepseek_client:
            try:
                response = await self.deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=1000
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"DeepSeek failed: {e}")
        
        return "⚠️ AI recommendations unavailable. Please configure GOOGLE_AI_API_KEY or DEEPSEEK_API_KEY."
    
    async def start(self):
        """Start the Telegram bot"""
        if not self.app:
            # Create application
            self.app = Application.builder().token(self.token).build()
            
            # Initialize asset fetcher
            self.asset_fetcher = AssetNameFetcher(self.db)
            await self.asset_fetcher.__aenter__()
            
            # Register command handlers
            self.app.add_handler(CommandHandler("start", self._cmd_start))
            self.app.add_handler(CommandHandler("stocks", self._cmd_stocks))
            self.app.add_handler(CommandHandler("crypto", self._cmd_crypto))
            self.app.add_handler(CommandHandler("positions", self._cmd_positions))
            self.app.add_handler(CommandHandler("portfolio", self._cmd_portfolio))
            self.app.add_handler(CommandHandler("recommend", self._cmd_recommend))
            self.app.add_handler(CommandHandler("recommend_crypto", self._cmd_recommend_crypto))
            self.app.add_handler(CommandHandler("buy", self._cmd_buy))
            self.app.add_handler(CommandHandler("sell", self._cmd_sell))
            self.app.add_handler(CommandHandler("trades", self._cmd_trades))
            
            # Message handler for natural language
            self.app.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._handle_message
            ))
            
            # Callback query handler for interactive buttons
            self.app.add_handler(CallbackQueryHandler(self._handle_callback))
            
            # Start polling
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            logger.info("🤖 Enhanced Telegram bot started")
    
    async def stop(self):
        """Stop the Telegram bot"""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            
            if self.asset_fetcher:
                await self.asset_fetcher.__aexit__(None, None, None)
            
            logger.info("🤖 Telegram bot stopped")
    
    async def send_message(self, text: str, **kwargs):
        """
        Send message to configured chat
        
        Args:
            text: Message text
            **kwargs: Additional arguments for send_message
        """
        if self.app:
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode='Markdown',
                **kwargs
            )
    
    # Command handlers
    
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_msg = """
🦞 **OpenClaw Trading Bot**

Welcome! I can help you manage your portfolio and get AI-powered trading recommendations.

**Commands:**
📊 `/stocks` - View Korean stocks
🪙 `/crypto` - View cryptocurrencies
📁 `/positions` - View all positions
💼 `/portfolio` - Portfolio breakdown
🤖 `/recommend` - AI stock recommendations
🔮 `/recommend_crypto` - AI crypto recommendations
💰 `/buy <symbol> <qty> <price>` - Record buy
💸 `/sell <symbol> <qty> <price>` - Record sell
📜 `/trades` - View trading history

**Natural Language:**
Just talk to me! Examples:
- "나는 0.5 BTC를 60,000,000원에 샀어"
- "Recommend some stocks"
- "Show my portfolio"

Let's start trading! 🚀
        """
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    async def _cmd_stocks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stocks command"""
        stock_positions = self.portfolio.get_stock_positions()
        
        if not stock_positions:
            await update.message.reply_text("📊 No Korean stocks in portfolio.")
            return
        
        # Get current prices (mock for now - would integrate with real data source)
        current_prices = {symbol: pos['avg_entry_price'] for symbol, pos in stock_positions.items()}
        
        # Fetch asset names
        if self.asset_fetcher:
            names = await self.asset_fetcher.get_multiple_names(list(stock_positions.keys()))
        else:
            names = {symbol: symbol for symbol in stock_positions.keys()}
        
        msg = "📈 **모니터링 중인 한국 주식**\n\n"
        
        for symbol, pos in stock_positions.items():
            name = names.get(symbol, symbol)
            price = current_prices.get(symbol, pos['avg_entry_price'])
            quantity = pos['quantity']
            
            # Calculate P&L
            current_value = quantity * price
            cost = pos['total_cost']
            pnl = current_value - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0
            
            emoji = "🟢" if pnl >= 0 else "🔴"
            
            msg += f"{emoji} **{symbol}** ({name})\n"
            msg += f"   가격: ₩{price:,.0f} ({pnl_pct:+.2f}%)\n"
            msg += f"   수량: {quantity:,}주\n"
            msg += f"   평가액: ₩{current_value:,.0f}\n\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def _cmd_crypto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /crypto command"""
        crypto_positions = self.portfolio.get_crypto_positions()
        
        if not crypto_positions:
            await update.message.reply_text("🪙 No cryptocurrencies in portfolio.")
            return
        
        # Get current prices (mock for now)
        current_prices = {symbol: pos['avg_entry_price'] for symbol, pos in crypto_positions.items()}
        
        # Fetch asset names
        if self.asset_fetcher:
            names = await self.asset_fetcher.get_multiple_names(list(crypto_positions.keys()))
        else:
            names = {symbol: symbol for symbol in crypto_positions.keys()}
        
        msg = "🪙 **모니터링 중인 암호화폐**\n\n"
        
        for symbol, pos in crypto_positions.items():
            name = names.get(symbol, symbol)
            price = current_prices.get(symbol, pos['avg_entry_price'])
            quantity = pos['quantity']
            
            # Calculate P&L
            current_value = quantity * price
            cost = pos['total_cost']
            pnl = current_value - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0
            
            emoji = "🟢" if pnl >= 0 else "🔴"
            
            msg += f"{emoji} **{symbol}** ({name})\n"
            msg += f"   가격: ₩{price:,.0f} ({pnl_pct:+.2f}%)\n"
            msg += f"   수량: {quantity:.4f}\n"
            msg += f"   평가액: ₩{current_value:,.0f}\n\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def _cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /positions command"""
        all_positions = self.portfolio.tracker.positions
        
        if not all_positions:
            await update.message.reply_text("📁 No positions in portfolio.")
            return
        
        # Get current prices
        current_prices = {symbol: pos['avg_entry_price'] for symbol, pos in all_positions.items()}
        
        # Fetch asset names
        if self.asset_fetcher:
            names = await self.asset_fetcher.get_multiple_names(list(all_positions.keys()))
        else:
            names = {symbol: symbol for symbol in all_positions.keys()}
        
        msg = "📁 **전체 포지션**\n\n"
        
        for symbol, pos in all_positions.items():
            name = names.get(symbol, symbol)
            price = current_prices.get(symbol, pos['avg_entry_price'])
            quantity = pos['quantity']
            
            # Calculate P&L
            current_value = quantity * price
            cost = pos['total_cost']
            pnl = current_value - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0
            
            emoji = "🟢" if pnl >= 0 else "🔴"
            
            msg += f"{emoji} **{symbol}** ({name})\n"
            msg += f"   진입가: ₩{pos['avg_entry_price']:,.2f}\n"
            msg += f"   현재가: ₩{price:,.2f}\n"
            msg += f"   수익률: {pnl_pct:+.2f}%\n"
            msg += f"   평가손익: ₩{pnl:,.0f}\n\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def _cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /portfolio command"""
        # Get current prices
        all_positions = self.portfolio.tracker.positions
        current_prices = {symbol: pos['avg_entry_price'] for symbol, pos in all_positions.items()}
        
        # Get portfolio breakdown
        breakdown = self.portfolio.get_portfolio_by_type(current_prices)
        
        msg = "💼 **포트폴리오 현황**\n\n"
        
        # Stocks section
        stocks = breakdown['stocks']
        msg += f"📈 **한국 주식** ({stocks['count']}개)\n"
        msg += f"   평가액: ₩{stocks['total_value']:,.0f}\n"
        msg += f"   투자금: ₩{stocks['total_cost']:,.0f}\n"
        msg += f"   수익률: {stocks['unrealized_pnl_pct']:+.2f}%\n\n"
        
        # Crypto section
        crypto = breakdown['crypto']
        msg += f"🪙 **암호화폐** ({crypto['count']}개)\n"
        msg += f"   평가액: ₩{crypto['total_value']:,.0f}\n"
        msg += f"   투자금: ₩{crypto['total_cost']:,.0f}\n"
        msg += f"   수익률: {crypto['unrealized_pnl_pct']:+.2f}%\n\n"
        
        # Total section
        total = breakdown['total']
        msg += f"💰 **전체 포트폴리오**\n"
        msg += f"   총 평가액: ₩{total['portfolio_value']:,.0f}\n"
        msg += f"   보유 현금: ₩{total['cash']:,.0f}\n"
        msg += f"   총 투자금: ₩{total['total_invested']:,.0f}\n"
        msg += f"   총 수익률: {total['total_pnl_pct']:+.2f}%\n"
        msg += f"   총 손익: ₩{total['total_pnl']:,.0f}\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def _cmd_recommend(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /recommend command for stock recommendations"""
        await update.message.reply_text("🤖 AI가 종목을 분석중입니다...")
        
        # Get current stock positions
        stock_positions = self.portfolio.get_stock_positions()
        
        prompt = f"""
You are a professional Korean stock market analyst. Analyze the current market and provide 3 stock recommendations.

Current portfolio: {list(stock_positions.keys()) if stock_positions else "Empty"}

Provide recommendations in Korean with:
1. Stock code and name
2. Entry price range
3. Target price
4. Stop loss
5. Brief analysis (2-3 sentences)

Format as a clear, readable message for Telegram.
        """
        
        response = await self._get_llm_response(prompt)
        
        msg = "🤖 **AI 종목 추천**\n\n" + response
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def _cmd_recommend_crypto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /recommend_crypto command for cryptocurrency recommendations"""
        await update.message.reply_text("🔮 AI가 암호화폐를 분석중입니다...")
        
        # Get current crypto positions
        crypto_positions = self.portfolio.get_crypto_positions()
        
        prompt = f"""
You are a professional cryptocurrency analyst. Analyze the current crypto market and provide 3 cryptocurrency recommendations.

Current portfolio: {list(crypto_positions.keys()) if crypto_positions else "Empty"}

Provide recommendations in Korean with:
1. Cryptocurrency name and symbol
2. Entry price range
3. Target price
4. Stop loss
5. Brief analysis (2-3 sentences)

Format as a clear, readable message for Telegram.
        """
        
        response = await self._get_llm_response(prompt)
        
        msg = "🔮 **AI 암호화폐 추천**\n\n" + response
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def _cmd_buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /buy command"""
        if len(context.args) < 3:
            await update.message.reply_text(
                "Usage: `/buy <symbol> <quantity> <price>`\n"
                "Example: `/buy 005930.KS 10 73500`",
                parse_mode='Markdown'
            )
            return
        
        symbol = context.args[0]
        try:
            quantity = float(context.args[1])
            price = float(context.args[2])
        except ValueError:
            await update.message.reply_text("❌ Invalid quantity or price")
            return
        
        # Record the trade
        result = self.portfolio.tracker.open_position(symbol, quantity, price)
        
        if result.get('success'):
            # Get asset name
            if self.asset_fetcher:
                name = await self.asset_fetcher.get_asset_name(symbol)
            else:
                name = symbol
            
            msg = f"✅ **매수 완료**\n\n"
            msg += f"종목: {symbol} ({name})\n"
            msg += f"수량: {quantity}\n"
            msg += f"가격: ₩{price:,.2f}\n"
            msg += f"총액: ₩{quantity * price:,.0f}"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ 매수 실패: {result.get('reason')}")
    
    async def _cmd_sell(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sell command"""
        if len(context.args) < 3:
            await update.message.reply_text(
                "Usage: `/sell <symbol> <quantity> <price>`\n"
                "Example: `/sell 005930.KS 10 75000`",
                parse_mode='Markdown'
            )
            return
        
        symbol = context.args[0]
        try:
            quantity = float(context.args[1])
            price = float(context.args[2])
        except ValueError:
            await update.message.reply_text("❌ Invalid quantity or price")
            return
        
        # Record the trade
        result = self.portfolio.tracker.close_position(symbol, quantity, price)
        
        if result.get('success'):
            # Get asset name
            if self.asset_fetcher:
                name = await self.asset_fetcher.get_asset_name(symbol)
            else:
                name = symbol
            
            closed = result['closed_position']
            emoji = "🟢" if closed['pnl'] >= 0 else "🔴"
            
            msg = f"✅ **매도 완료** {emoji}\n\n"
            msg += f"종목: {symbol} ({name})\n"
            msg += f"수량: {quantity}\n"
            msg += f"진입가: ₩{closed['entry_price']:,.2f}\n"
            msg += f"매도가: ₩{price:,.2f}\n"
            msg += f"수익률: {closed['pnl_pct']:+.2f}%\n"
            msg += f"손익: ₩{closed['pnl']:,.0f}"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ 매도 실패: {result.get('reason')}")
    
    async def _cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trades command"""
        trades = self.portfolio.tracker.trade_history[-10:]  # Last 10 trades
        
        if not trades:
            await update.message.reply_text("📜 No trading history.")
            return
        
        msg = "📜 **거래 내역** (최근 10건)\n\n"
        
        for trade in reversed(trades):
            symbol = trade['symbol']
            action = trade['action']
            
            # Get asset name
            if self.asset_fetcher:
                name = await self.asset_fetcher.get_asset_name(symbol)
            else:
                name = symbol
            
            timestamp = trade['timestamp'][:19]  # Remove microseconds
            
            if action == 'OPEN':
                msg += f"✅ **매수** - {symbol} ({name})\n"
                msg += f"   수량: {trade['quantity']}, 가격: ₩{trade['price']:,.2f}\n"
                msg += f"   시간: {timestamp}\n\n"
            else:
                pnl = trade.get('pnl', 0)
                emoji = "🟢" if pnl >= 0 else "🔴"
                msg += f"💰 **매도** {emoji} - {symbol} ({name})\n"
                msg += f"   수량: {trade['quantity']}, 가격: ₩{trade['price']:,.2f}\n"
                msg += f"   손익: ₩{pnl:,.0f}\n"
                msg += f"   시간: {timestamp}\n\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language messages"""
        text = update.message.text.lower()
        
        # Check for common patterns
        if any(word in text for word in ['추천', 'recommend', '종목']):
            if any(word in text for word in ['암호화폐', 'crypto', 'coin']):
                await self._cmd_recommend_crypto(update, context)
            else:
                await self._cmd_recommend(update, context)
        elif any(word in text for word in ['포트폴리오', 'portfolio', '현황']):
            await self._cmd_portfolio(update, context)
        elif any(word in text for word in ['주식', 'stock', 'stocks']):
            await self._cmd_stocks(update, context)
        elif any(word in text for word in ['암호화폐', 'crypto', 'coin']):
            await self._cmd_crypto(update, context)
        elif any(word in text for word in ['샀', 'bought', 'buy']):
            # Try to parse natural language buy command
            await self._parse_trade_message(update, 'buy')
        elif any(word in text for word in ['팔', 'sold', 'sell']):
            # Try to parse natural language sell command
            await self._parse_trade_message(update, 'sell')
        else:
            await update.message.reply_text(
                "죄송합니다. 무엇을 도와드릴까요?\n"
                "/start 를 입력하여 사용 가능한 명령어를 확인하세요."
            )
    
    async def _parse_trade_message(self, update: Update, action: str):
        """Parse natural language trade message"""
        text = update.message.text
        
        # Try to extract: symbol, quantity, price
        # Example: "나는 0.5 BTC를 60,000,000원에 샀어"
        # Pattern: number + symbol + number + price indicator
        
        # This is a simplified parser - would need more robust NLP
        numbers = re.findall(r'[\d,]+\.?\d*', text.replace(',', ''))
        
        if len(numbers) >= 2:
            # Try to find crypto/stock symbol
            symbols = re.findall(r'\b([A-Z]{2,4}|KRW-[A-Z]+|\d{6}\.[A-Z]{2})\b', text.upper())
            
            if symbols:
                symbol = symbols[0]
                quantity = float(numbers[0])
                price = float(numbers[1])
                
                # Create a simple context object with args attribute
                class SimpleContext:
                    def __init__(self, args):
                        self.args = args
                
                context = SimpleContext([symbol, str(quantity), str(price)])
                
                if action == 'buy':
                    update.message.text = f"/buy {symbol} {quantity} {price}"
                    await self._cmd_buy(update, context)
                else:
                    update.message.text = f"/sell {symbol} {quantity} {price}"
                    await self._cmd_sell(update, context)
                return
        
        await update.message.reply_text(
            "거래 정보를 파싱할 수 없습니다. 다음 형식을 사용해주세요:\n"
            f"`/{action} <symbol> <quantity> <price>`"
        )
    
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline buttons"""
        query = update.callback_query
        await query.answer()
        
        # Handle different callback actions
        data = query.data
        
        if data.startswith('execute_'):
            # Execute a trading signal
            await query.edit_message_text("⚙️ Executing trade...")
            # Would integrate with actual trading logic
        elif data.startswith('ignore_'):
            # Ignore a trading signal
            await query.edit_message_text("❌ Signal ignored")
    
    async def send_trade_signal(
        self,
        symbol: str,
        action: str,
        price: float,
        reason: str
    ):
        """
        Send interactive trade signal
        
        Args:
            symbol: Asset symbol
            action: 'BUY' or 'SELL'
            price: Suggested price
            reason: Analysis/reason for signal
        """
        # Get asset name
        if self.asset_fetcher:
            name = await self.asset_fetcher.get_asset_name(symbol)
        else:
            name = symbol
        
        emoji = "🟢" if action == "BUY" else "🔴"
        
        msg = f"{emoji} **거래 시그널**\n\n"
        msg += f"종목: {symbol} ({name})\n"
        msg += f"액션: {action}\n"
        msg += f"가격: ₩{price:,.2f}\n\n"
        msg += f"분석:\n{reason}"
        
        # Add interactive buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ 즉시 체결", callback_data=f"execute_{symbol}_{action}"),
                InlineKeyboardButton("❌ 무시", callback_data=f"ignore_{symbol}_{action}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.send_message(msg, reply_markup=reply_markup)
