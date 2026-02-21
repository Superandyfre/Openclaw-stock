#!/usr/bin/env python3
"""
自然语言对话处理器
使用 Gemini AI 理解用户意图并执行相应操作
"""
import os
import re
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger

try:
    from openclaw.skills.analysis.gemini_model_manager import GeminiModelManager
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Gemini模型管理器未找到")

try:
    from openclaw.skills.data_collection.us_hk_stock_fetcher import USHKStockFetcher
    USHK_FETCHER_AVAILABLE = True
except ImportError:
    USHK_FETCHER_AVAILABLE = False
    logger.warning("美股港股数据获取器未找到")

try:
    from openclaw.skills.backtesting.enhanced_backtest import EnhancedBacktest
    from openclaw.skills.backtesting.backtest_data_fetcher import BacktestDataFetcher
    BACKTEST_AVAILABLE = True
except ImportError:
    BACKTEST_AVAILABLE = False
    logger.warning("回测模块未找到")

try:
    from openclaw.skills.data_collection.announcement_monitor import AnnouncementMonitor
    ANNOUNCEMENT_MONITOR_AVAILABLE = True
except ImportError:
    ANNOUNCEMENT_MONITOR_AVAILABLE = False
    logger.warning("DART公告监控未找到")


class ConversationHandler:
    """自然语言对话处理器"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        tracker=None,
        ai_advisor=None,
        crypto_fetcher=None,
        us_hk_fetcher=None,
        announcement_monitor=None,
        kline_fetcher=None,
        state_file: Optional[str] = None,
    ):
        """
        初始化对话处理器

        Args:
            api_key: Google AI API密钥
            tracker: 持仓追踪器
            ai_advisor: AI交易顾问
            crypto_fetcher: 加密货币数据获取器
            us_hk_fetcher: 美股港股数据获取器
            announcement_monitor: DART公告监控器
            kline_fetcher: K线与交易量数据获取器
        """
        self.api_key = api_key or os.getenv('GOOGLE_AI_API_KEY')
        self.tracker = tracker
        self.ai_advisor = ai_advisor
        self.crypto_fetcher = crypto_fetcher
        self.us_hk_fetcher = us_hk_fetcher
        self.announcement_monitor = announcement_monitor
        self.kline_fetcher = kline_fetcher
        self._state_file = state_file  # 账户状态持久化路径（None=不保存）
        
        # 初始化回测组件
        if BACKTEST_AVAILABLE:
            try:
                self.backtest_data_fetcher = BacktestDataFetcher()
                logger.info("✅ 回测数据获取器初始化成功")
            except Exception as e:
                logger.warning(f"⚠️ 回测数据获取器初始化失败: {e}")
                self.backtest_data_fetcher = None
        else:
            self.backtest_data_fetcher = None
        
        # 对话历史
        self.conversation_history: List[Dict[str, str]] = []

        # [补丁] 初始化推荐目标缓存，防止 AttributeError
        self._recommendation_targets: Dict[str, float] = {}
        
        # 初始化Gemini模型管理器
        if GEMINI_AVAILABLE and self.api_key:
            try:
                self.model_manager = GeminiModelManager(
                    api_key=self.api_key,
                    default_task_type='standard'  # 日常对话使用标准模型
                )
                logger.info("✅ Conversation Handler 初始化成功 (Gemini Model Manager)")
            except Exception as e:
                logger.error(f"初始化Gemini模型管理器失败: {e}")
                self.model_manager = None
        else:
            self.model_manager = None
            logger.warning("⚠️ Conversation Handler 运行在基础模式（无AI）")
    
    def _auto_save(self) -> None:
        """买卖/调仓后自动保存账户状态（仅当 _state_file 已设置时）。"""
        if self._state_file and self.tracker:
            self.tracker.save_state(self._state_file)

    async def _handle_calc_query(self, user_message: str) -> str:
        """
        计算询问短路处理：Python直接查价并计算，禁止LLM做数学。
        支持：'500万韩币能买几个ENSO' / '1000美元能买多少BTC' 等。
        返回格式化字符串，解析失败返回空字符串（回退到LLM）。
        """
        import re as _re

        msg = user_message.strip()

        # ── 1. 提取金额（支持：万/千/百 单位，韩元/美元/USD/KRW/원/₩）──
        _amount_krw = None
        # 带单位的中文数字：X万/X千/X百（可带小数）
        m = _re.search(r'(\d+(?:\.\d+)?)\s*万', msg)
        if m:
            _amount_krw = float(m.group(1)) * 10000
        if _amount_krw is None:
            m = _re.search(r'(\d+(?:\.\d+)?)\s*千', msg)
            if m:
                _amount_krw = float(m.group(1)) * 1000
        if _amount_krw is None:
            m = _re.search(r'(\d+(?:\.\d+)?)\s*百', msg)
            if m:
                _amount_krw = float(m.group(1)) * 100
        # 纯数字（无单位）
        if _amount_krw is None:
            m = _re.search(r'(\d{4,})', msg)
            if m:
                _amount_krw = float(m.group(1))
        if _amount_krw is None:
            return ''

        # USD → KRW 换算
        USD_TO_KRW = 1350.0
        if any(k in msg.upper() for k in ['美元', 'USD', '$']):
            _amount_krw *= USD_TO_KRW

        # ── 2. 提取资产代码（KRW-XXX / 裸大写字母代码 / 中文币名）──
        _CRYPTO_CN = {
            '比特币': 'BTC', '以太坊': 'ETH', '以太': 'ETH', '瑞波': 'XRP',
            '狗狗币': 'DOGE', '索拉纳': 'SOL', '莱特币': 'LTC', '艾达': 'ADA',
            '波卡': 'DOT', '艾索': 'ENSO', 'SNX': 'SNX', 'SOL': 'SOL', 'BTC': 'BTC', 'ETH': 'ETH'
        }
        _sym = None
        # KRW-XXX 格式
        m = _re.search(r'KRW-([A-Z]{2,10})', msg.upper())
        if m:
            _sym = m.group(1)
        # 中文别名
        if _sym is None:
            for cn, code in _CRYPTO_CN.items():
                if cn in msg:
                    _sym = code
                    break
        # 裸大写字母 ticker（2-10位），排除助词；用 lookaround 替代 \b（\b 在中文混合文本中失效）
        if _sym is None:
            candidates = _re.findall(r'(?<![A-Za-z])([A-Za-z]{2,10})(?![A-Za-z])', msg)
            _EXCLUDE = {'KRW', 'USD', 'THE', 'KRX', 'CAN', 'HOW', 'BUY',
                        'FOR', 'GET', 'USE', '万', '韩', '美', '元', 'A', 'I', 'IN'}
            for c in candidates:
                if c.upper() not in _EXCLUDE:
                    _sym = c.upper()
                    break
        
        # [NEW] 上下文补全：如果没提币种，默认使用【上次提到的币种】
        if _sym is None:
            # 查找历史记录最后一条包含币种的消息 (向前回溯3条)
            for h in reversed(self.conversation_history[-3:]):
                prev_text = h['message']
                # 尝试从历史消息里提取币种 (复用正则)
                hist_sym = None
                hm = _re.search(r'KRW-([A-Z]{2,10})', prev_text.upper())
                if hm: hist_sym = hm.group(1)
                else:
                    cand = _re.findall(r'(?<![A-Za-z])([A-Za-z]{2,10})(?![A-Za-z])', prev_text)
                    for c in cand:
                        if c.upper() not in _EXCLUDE:
                            hist_sym = c.upper()
                            break
                if hist_sym:
                    _sym = hist_sym
                    break
        
        if _sym is None:
            # 实在没办法，回退给 LLM
            return ''

        # ── 3. 查价（Bithumb实时 → Upbit实时 → 缓存）──
        krw_sym = f'KRW-{_sym}'
        price_info = None

        # ① Bithumb force_live
        if self.crypto_fetcher:
            price_info = await self._get_current_price(krw_sym, force_live=True)

        # ② Upbit force_live
        if not price_info or price_info.get('price', 0) <= 0:
            if self.crypto_fetcher:
                try:
                    import pyupbit as _upbit
                    _ticker = await asyncio.to_thread(_upbit.get_current_price, krw_sym)
                    if _ticker:
                        price_info = {'price': float(_ticker), 'change_pct': 0.0, 'exchange': 'upbit'}
                        logger.info(f'[calc-query] {krw_sym} Upbit实时 ₩{_ticker}')
                except Exception:
                    pass

        # ③ 缓存降级
        if not price_info or price_info.get('price', 0) <= 0:
            cached = self.__class__._crypto_price_cache.get(krw_sym)
            if cached and cached.get('price', 0) > 0:
                price_info = cached
                logger.info(f'[calc-query] {krw_sym} 缓存降级 ₩{cached["price"]}')

        if not price_info or price_info.get('price', 0) <= 0:
            return f'❌ 无法获取 {_sym} 价格，请稍后重试'

        price      = price_info['price']
        change_pct = price_info.get('change_pct', price_info.get('change', 0))
        exchange   = price_info.get('exchange', '?')

        # ── 4. Python 精确计算 ──
        quantity = _amount_krw / price
        total_cost = quantity * price   # 应等于 _amount_krw（整数量时略有差异）

        # 格式化数量：整数币种显示整数，小数币种保留合适小数
        if price >= 1000:
            qty_str = f"{quantity:,.2f}"
        elif price >= 1:
            qty_str = f"{quantity:,.4f}"
        else:
            qty_str = f"{quantity:,.2f}"

        from datetime import datetime as _dt_now
        _ts = _dt_now.now().strftime('%H:%M:%S')

        result = (
            f"📊 {_sym} 实时价格：₩{self._fmt_price(price)}  {change_pct:+.2f}%  [{exchange}  {_ts}]\n\n"
            f"💰 投入金额：₩{self._fmt_price(_amount_krw)}\n"
            f"📦 可买数量：{qty_str} 个\n"
            f"（价格×数量 = ₩{self._fmt_price(price)} × {qty_str} ≈ ₩{self._fmt_price(total_cost)}）"
        )
        logger.info(f"[calc-query] {_sym} ₩{price} × {qty_str} = ₩{total_cost:.0f}（投入₩{_amount_krw:.0f}）")
        return result

    async def _handle_direct_trade(self, user_message: str):
        """
        买入/卖出直接短路解析器：Python精确识别交易指令，直接执行，
        禁止 LLM 模拟账务操作。
        返回执行结果字符串；解析失败返回 None（回退 LLM）。
        """
        if not self.tracker:
            return None

        import re as _re
        import time as _ti
        msg = user_message.strip()

        # ── 判断动作方向 ──
        _is_buy  = any(k in msg for k in ['买入', '购买', '下单买'])
        _is_sell = any(k in msg for k in ['卖出', '平仓', '卖掉', '止损', '止盈',
                                          '清仓', '清空', '全部卖', '全仓卖', '全卖',
                                          '全卖掉', '全抛掉', '全抛', '出货', '抛掉',
                                          '抛售', '甩掉', '清掉'])
        if not (_is_buy or _is_sell):
            return None

        # ── 提取资产代码 ──
        _CRYPTO_CN = {
            '比特币': 'BTC', '以太坊': 'ETH', '以太': 'ETH', '瑞波': 'XRP',
            '狗狗币': 'DOGE', '索拉纳': 'SOL', '莱特币': 'LTC', '艾达': 'ADA',
            '波卡': 'DOT',
        }
        _sym = None
        m = _re.search(r'KRW-([A-Z]{2,10})', msg.upper())
        if m: _sym = m.group(1)
        if not _sym:
            m = _re.search(r'\b(\d{6})\b', msg)
            if m: _sym = m.group(1)
        if not _sym:
            for cn, code in _CRYPTO_CN.items():
                if cn in msg:
                    _sym = code
                    break
        if not _sym:
            for tok in _re.findall(r'(?<![A-Za-z])([A-Za-z]{2,10})(?![A-Za-z])', msg):
                up = tok.upper()
                if up not in {'KRW', 'USD', 'THE', 'BUY', 'FOR', 'GET',
                              '买入', '卖出', '单价', '均价', '价格'}:
                    _sym = up
                    break

        # ── 卖出/平仓：代码可省略（单仓时自动推断）──
        if _is_sell:
            positions = self.tracker.positions
            # 代码未识别 → 单仓自动匹配
            if not _sym:
                if len(positions) == 1:
                    full_code = list(positions.keys())[0]
                    _sym = full_code.replace('KRW-', '')
                else:
                    return None  # 多仓时需指定代码
            code = _sym if (_sym.isdigit() and len(_sym) == 6) else f'KRW-{_sym}'
            if code not in positions:
                return f"❌ 未持有 {_sym}，无法卖出"

            # 数量：有则部分平，无则全仓平
            _qty_m = _re.search(r'(\d+(?:\.\d+)?)\s*(?:个|枚|股|手|coins?|units?)', msg)
            if _qty_m:
                quantity = float(_qty_m.group(1))
            else:
                _bare_m = _re.search(
                    r'(?:卖出|平仓|卖掉)\s*[^\d]*?(\d+(?:\.\d+)?)(?=\s*(?:单价|均价|价格|价位|@|$))',
                    msg
                )
                if not _bare_m:
                    _bare_m = _re.search(
                        r'(?<![A-Za-z\d])(\d{1,10}(?:\.\d+)?)\s*(?:单价|均价|价格|价位|@)',
                        msg
                    )
                quantity = float(_bare_m.group(1)) if _bare_m else None

            held = positions[code]['quantity']
            entry = positions[code]['avg_entry_price']
            sell_qty = min(quantity, held) if quantity else held  # None=全仓

            # 价格：用户指定优先，否则查实时价
            _price = None
            # 1. 明确前缀：单价/均价/@等
            pm = _re.search(r'(?:单价|均价|价格|价位|@)\s*₩?\s*(\d+(?:[,，]\d+)*(?:\.\d+)?)', msg)
            if pm:
                _price = float(pm.group(1).replace(',', '').replace('，', ''))
            # 2. 裸数字紧跟卖出词（如“111清仓”“113 平仓”）
            if _price is None:
                _SELL_RE = r'(?:清仓|清空|平仓|卖出|卖掉|止损|止盈|全卖掉|全抛掉|全卖|全抛|出货|抛掉|抛售|甩掉|清掉)'
                pm2 = _re.search(rf'(?<!\d)(\d+(?:\.\d+)?)\s*{_SELL_RE}', msg)
                if pm2:
                    _price = float(pm2.group(1))
            if _price is None:
                pi = await self._get_current_price(code, force_live=True)
                if not pi or pi.get('price', 0) <= 0:
                    # 降级：使用告警循环写入的最新缓存价格
                    _cached = (
                        self.__class__._live_pos_price_cache.get(code)
                        or self.__class__._crypto_price_cache.get(code)
                    )
                    if _cached and _cached.get('price', 0) > 0:
                        _price = _cached['price']
                        logger.info(f"[direct-sell] 实时价失败，使用缓存价 {code} ₩{_price}")
                    else:
                        return f"❌ 无法获取 {_sym} 实时价格，请稍后重试或手动指定价格（如：{_sym} 平仓 价格1.83）"
                else:
                    _price = pi['price']

            result = self.tracker.close_position(code, sell_qty, _price)
            if not result or not result.get('success'):
                return f"❌ 卖出失败（tracker 错误）"
            _cp  = result.get('closed_position', {})
            pnl     = _cp.get('pnl', 0)
            pnl_pct = _cp.get('pnl_pct', 0)
            # ── Bithumb 卖出手续费 0.25% ──
            _is_crypto_sell = 'KRW-' in code or ('-' in code and not code.isdigit())
            _sell_fee = round(sell_qty * _price * 0.0025, 0) if _is_crypto_sell else 0.0
            pnl -= _sell_fee   # 从净盈亏中扣除卖出手续费
            self._auto_save()
            logger.info(f"[direct-sell] {code} {sell_qty} @ {_price} 卖出手续费₩{_sell_fee:.0f} P&L ₩{pnl:.0f}")
            pnl_icon = "🟢" if pnl >= 0 else "🔴"
            _fee_line = f"   手续费(0.25%)：-₩{self._fmt_price(_sell_fee)}\n" if _sell_fee else ""
            return (
                f"✅ 已平仓 {_sym}\n"
                f"   数量：{sell_qty:g} 个\n"
                f"   买入价：₩{self._fmt_price(entry)}（含买入手续费）\n"
                f"   卖出价：₩{self._fmt_price(_price)}\n"
                f"{_fee_line}"
                f"   {pnl_icon} 净盈亏：{self._fmt_signed(pnl)}\n"
                f"   {pnl_icon} 盈亏率：{pnl_pct:+.2f}%\n"
                f"   剩余资金：₩{self._fmt_price(self.tracker.cash)}"
            )

        # ── 买入：必须有代码和数量 ──
        if not _sym:
            return None

        # 数量提取
        _qty_m = _re.search(r'(\d+(?:\.\d+)?)\s*(?:个|枚|股|手|coins?|units?)', msg)
        if _qty_m:
            quantity = float(_qty_m.group(1))
        else:
            _bare_m = _re.search(
                r'(?:买入|购买|下单买)\s*[^\d]*?(\d+(?:\.\d+)?)(?=\s*(?:单价|均价|价格|价位|@|$))',
                msg
            )
            if not _bare_m:
                _bare_m = _re.search(
                    r'(?<![A-Za-z\d])(\d{1,10}(?:\.\d+)?)\s*(?:单价|均价|价格|价位|@)',
                    msg
                )
            if not _bare_m:
                return None
            quantity = float(_bare_m.group(1))

        code = _sym if (_sym.isdigit() and len(_sym) == 6) else f'KRW-{_sym}'

        # 价格：用户指定优先，否则查实时价
        _price = None
        pm = _re.search(r'(?:单价|均价|价格|价位|@)\s*₩?\s*(\d+(?:[,，]\d+)*(?:\.\d+)?)', msg)
        if pm:
            _price = float(pm.group(1).replace(',', '').replace('，', ''))
        if _price is None:
            pi = await self._get_current_price(code, force_live=True)
            if not pi or pi.get('price', 0) <= 0:
                return None
            _price = pi['price']

        total_cost = quantity * _price
        # ── Bithumb 手续费 0.25%（仅加密货币）──
        _is_crypto_buy = 'KRW-' in code or ('-' in code and not code.isdigit())
        _FEE_RATE = 0.0025
        _fee = round(total_cost * _FEE_RATE, 0) if _is_crypto_buy else 0.0
        _total_needed = total_cost + _fee
        if _total_needed > self.tracker.cash:
            _msg = (f"❌ 资金不足\n"
                    f"   需要：₩{self._fmt_price(total_cost)}")
            if _fee:
                _msg += f" + 手续费 ₩{self._fmt_price(_fee)} = ₩{self._fmt_price(_total_needed)}"
            _msg += f"\n   可用：₩{self._fmt_price(self.tracker.cash)}"
            return _msg
        
        # 尝试获取目标价：优先查缓存，若无则现场计算
        custom_target = self._recommendation_targets.get(code, 0.0)
        target_desc = ""
        
        if custom_target <= 0:
            # 缓存未命中，执行快速ATR计算
            try:
                from openclaw.skills.analysis.advanced_indicator_monitor import AdvancedIndicatorMonitor
                monitor = AdvancedIndicatorMonitor()
                # 简易K线获取（仅加密货币有效支持，韩股暂略）
                candles = []
                is_crypto = 'KRW-' in code or '-' in code
                
                if is_crypto:
                    import pyupbit as _upbit
                    # 获取过去48小时数据(同推荐算法)
                    df_raw = await asyncio.to_thread(_upbit.get_ohlcv, code, count=48, interval='minute60')
                    if df_raw is not None and not df_raw.empty:
                        for _date, _row in df_raw.iterrows():
                            candles.append({'timestamp': str(_date), 'open': float(_row['open']),
                                            'high': float(_row['high']), 'low': float(_row['low']),
                                            'close': float(_row['close']), 'volume': float(_row['volume'])})
                
                if candles:
                    for c in candles: monitor.update_price_data(code, c)
                    # 仅计算，提取ATR
                    analysis = monitor.analyze_all_indicators(code)
                    # 复用核心算法
                    t_steady, _, _, _, _, _ = self._calculate_target_price(code.replace('KRW-',''), _price, analysis)
                    custom_target = t_steady
                    target_desc = " (实时ATR计算)"
            except Exception as _e:
                logger.warning(f"现场计算目标价失败: {_e}")
                custom_target = 0.0

        # 买入时将手续费摊入成本（等效提高买入价，使盈亏计算自动含费）
        _effective_buy_price = _price * (1 + _FEE_RATE) if _is_crypto_buy else _price
        success = self.tracker.open_position(code, quantity, _effective_buy_price, custom_profit_target_price=custom_target)
        if not success:
            return f"❌ 买入失败（tracker 错误）"
        self._auto_save()
        
        # 补充目标价信息
        target_msg = ""
        if custom_target > 0:
            target_roi = (custom_target - _price) / _price * 100
            target_msg = f"\n   🎯 自动目标：₩{self._fmt_price(custom_target)} (+{target_roi:.1f}%){target_desc}"
            
        logger.info(f"[direct-buy] {code} {quantity} @ {_price} 手续费₩{_fee:.0f} 总₩{_total_needed:.0f} Target={custom_target}")
        _fee_line = f"\n   手续费(0.25%)：₩{self._fmt_price(_fee)}" if _fee else ""
        return (
            f"✅ 已买入 {_sym} {quantity:g}个 @ ₩{self._fmt_price(_price)}"
            f"{_fee_line}\n"
            f"   总扣款：₩{self._fmt_price(_total_needed)}{target_msg}\n"
            f"   剩余资金：₩{self._fmt_price(self.tracker.cash)}"
        )

    async def process_message(self, user_message: str, user_id: int = None) -> str:
        """
        处理用户消息 - 完全基于LLM驱动
        
        Args:
            user_message: 用户输入的消息
            user_id: 用户ID
        
        Returns:
            回复消息
        """
        # 添加到对话历史
        self.conversation_history.append({
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'message': user_message,
            'type': 'user'
        })
        
        try:
            # � 问候语短路：直接返回含真实账户信息的欢迎语，不走LLM防止幻觉
            _GREET_KWS = ['你好', '您好', 'hi', 'hello', 'Hey', '早上好', '下午好',
                          '晚上好', '早', '嗨', '哈喽', '开始', '你是谁', '介绍']
            _is_greet = (
                any(k.lower() in user_message.lower() for k in _GREET_KWS)
                and len(user_message.strip()) <= 20
                and not any(k in user_message for k in ['推荐', '分析', '买', '卖', '仓'])
            )
            if _is_greet and self.tracker:
                _cash = self.tracker.cash
                _pos_count = len(self.tracker.positions)
                _pos_str = f"{_pos_count} 个持仓" if _pos_count else "无持仓"
                greet_reply = (
                    f"您好！我是安诚科技 Ancent AI 交易助手 🤖\n\n"
                    f"📊 当前账户状态：\n"
                    f"   可用现金：₩{self._fmt_price(_cash)}\n"
                    f"   持仓：{_pos_str}\n\n"
                    f"可为您提供：实时行情、买卖执行、技术分析、持仓盈亏查询"
                )
                self.conversation_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'message': greet_reply,
                    'type': 'assistant'
                })
                return greet_reply

            # �🔢 盈亏/持仓直接短路：不走LLM，直接计算返回，避免幻觉
            _PNL_DIRECT_KWS = ['现在盈亏', '盈亏', '浮动盈亏', '当前盈亏', '持仓盈亏',
                               '盈利', '亏损多少', '赚了多少', '亏了多少',
                               '持仓动态', '持仓状态', '持仓情况', '查仓', '看仓',
                               '仓位', '当前持仓', '持仓']
            _PNL_QUESTION_KWS = ['多少', '现在', '当前', '怎么', '如何', '查', '看看', '盈亏']
            is_pnl_only = (
                any(k in user_message for k in _PNL_DIRECT_KWS)
                and not any(k in user_message for k in ['推荐', '分析', '买入', '卖出', '下单', '策略', '建议'])
            )
            if is_pnl_only and self.tracker:
                if self.tracker.positions:
                    pnl_text = await self._build_realtime_pnl_summary()
                    if pnl_text:
                        self.conversation_history.append({
                            'timestamp': datetime.now().isoformat(),
                            'message': pnl_text,
                            'type': 'assistant'
                        })
                        return pnl_text
                else:
                    no_pos = (
                        f"📊 当前无持仓\n"
                        f"💵 账户现金：₩{self._fmt_price(self.tracker.cash)}\n"
                        f"📈 初始资金：₩{self._fmt_price(self.tracker.initial_capital)}"
                    )
                    self.conversation_history.append({
                        'timestamp': datetime.now().isoformat(),
                        'message': no_pos,
                        'type': 'assistant'
                    })
                    return no_pos

            # � 资金调整直接短路：Python正则解析，不走LLM
            _adj_m = re.search(
                r'(?:'
                r'调整\s*总?(?:资产|资金)\s+'
                r'|(?:总?资产|总?资金).*?(?:改为|更改为|更新为|设为|设置为|调整为|变更为|换成|重置为)'
                r'|(?:资产|资金).*?(?:更改|修改|调整)\s*为'
                r')\s*(\d+(?:\.\d+)?)\s*万',
                user_message
            )
            if not _adj_m:
                _adj_m2 = re.search(
                    r'(?:总?资产|总?资金).*?(?:改为|更改为|更新为|设为|设置为|调整为|变更为|换成|重置为)\s*(\d{4,})',
                    user_message
                )
                _adj_amount = float(_adj_m2.group(1)) if _adj_m2 else None
            else:
                _adj_amount = float(_adj_m.group(1)) * 10000

            if _adj_amount is not None and self.tracker:
                _pos_val = sum(
                    pos['quantity'] * pos['avg_entry_price']
                    for pos in self.tracker.positions.values()
                ) if self.tracker.positions else 0.0
                _new_cash = max(0.0, _adj_amount - _pos_val)
                self.tracker.initial_capital = _adj_amount
                self.tracker.cash = _new_cash
                self._auto_save()
                _adj_reply = (
                    f"✅ 账户资金已更新\n"
                    f"   总资产：₩{self._fmt_price(_adj_amount)}\n"
                    f"   可用现金：₩{self._fmt_price(_new_cash)}\n"
                    f"   持仓价值：₩{self._fmt_price(_pos_val)}"
                )
                logger.info(f"✅ [直接短路] 总资产调整: ₩{_adj_amount:,.0f}, 现金: ₩{_new_cash:,.0f}")
                self.conversation_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'message': _adj_reply,
                    'type': 'assistant'
                })
                return _adj_reply

            # �💵 资金/账户余额直接短路
            _FUND_KWS = ['总资金', '资金', '余额', '可用资金', '账户余额',
                         '剩余资金', '还剩多少钱', '还有多少钱', '账户资金',
                         '本金', '资产', '总资产', '账户总额']
            _FUND_ADJUST_KWS = ['改为', '更新为', '更改为', '调整为', '设为', '设置为',
                                '修改为', '调整', '更改', '变更为', '换成', '重置']
            _is_fund = (
                any(k in user_message for k in _FUND_KWS)
                and not any(k in user_message for k in ['推荐', '分析', '买入', '卖出',
                                                         '盈亏', '盈利', '亏损', '持仓'])
                and not any(k in user_message for k in _FUND_ADJUST_KWS)
            )
            if _is_fund and self.tracker:
                positions = self.tracker.positions
                total_market_val = 0.0
                if positions:
                    for sym, pos in positions.items():
                        cached = self.__class__._live_pos_price_cache.get(sym)
                        cur = cached['price'] if cached else pos['avg_entry_price']
                        total_market_val += cur * pos['quantity']
                total_assets = self.tracker.cash + total_market_val
                pnl_total = total_assets - self.tracker.initial_capital
                pnl_pct   = (pnl_total / self.tracker.initial_capital * 100) if self.tracker.initial_capital else 0.0
                fund_reply = (
                    f"💵 账户总资产：₩{self._fmt_price(total_assets)}\n"
                    f"   可用现金：₩{self._fmt_price(self.tracker.cash)}\n"
                    f"   持仓市值：₩{self._fmt_price(total_market_val)}\n"
                    f"   初始资金：₩{self._fmt_price(self.tracker.initial_capital)}\n"
                    f"   {'🟢' if pnl_total >= 0 else '🔴'} 总盈亏：{self._fmt_signed(pnl_total)}（{pnl_pct:+.2f}%）"
                )
                self.conversation_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'message': fund_reply,
                    'type': 'assistant'
                })
                return fund_reply

            # 🆕 在处理消息前，自动检查持仓告警
            alerts = await self._check_position_alerts()

            # 💹 买入/卖出直接短路：Python解析执行，禁止LLM模拟账务操作
            _direct_trade = await self._handle_direct_trade(user_message)
            if _direct_trade is not None:
                self.conversation_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'message': _direct_trade,
                    'type': 'assistant'
                })
                return _direct_trade

            # 🔢 计算询问短路：Python直接计算，禁止LLM自己做数学
            _CALC_KWS = ['能买几个', '能买多少', '可以买几个', '可以买多少',
                         '买多少个', '买几个', '买多少枚', '买几枚',
                         '买多少股', '买几股', '按实时价格计算', '帮我算',
                         '计算一下', '大概能买', '买得起多少', '买得了多少',
                         '能买几手', '可以买几手']
            _EXPLICIT_BUY_KWS = ['买入', '帮我买', '购买', '下单']
            _is_calc = (
                any(k in user_message for k in _CALC_KWS)
                and not any(k in user_message for k in _EXPLICIT_BUY_KWS)
            )
            if _is_calc:
                _calc_result = await self._handle_calc_query(user_message)
                if _calc_result:
                    self.conversation_history.append({
                        'timestamp': datetime.now().isoformat(),
                        'message': _calc_result,
                        'type': 'assistant'
                    })
                    return _calc_result

            # 💲 实时价格直接短路：不走LLM，直接查返回
            _PRICE_DIRECT_KWS = ['实时价格', '现价', '当前价格', '现在价格', '实时价', '查价']
            _is_price_direct = (
                any(k in user_message for k in _PRICE_DIRECT_KWS)
                and not any(k in user_message for k in ['推荐', '分析', '买入', '卖出', '能买', '可以买'])
            )
            if _is_price_direct:
                import re as _re_p
                _CRYPTO_CN_P = {
                    '比特币': 'BTC', '以太坊': 'ETH', '以太': 'ETH', '瑞波': 'XRP',
                    '狗狗币': 'DOGE', '索拉纳': 'SOL', '莱特币': 'LTC',
                }
                _psym = None
                _m = _re_p.search(r'KRW-([A-Z]{2,10})', user_message.upper())
                if _m: _psym = _m.group(1)
                if not _psym:
                    for _cn, _cd in _CRYPTO_CN_P.items():
                        if _cn in user_message:
                            _psym = _cd; break
                if not _psym:
                    _cands = _re_p.findall(r'(?<![A-Za-z])([A-Za-z]{2,10})(?![A-Za-z])', user_message)
                    _EXCL = {'KRW', 'USD', 'THE', 'KRX', 'BUY', 'FOR', 'GET'}
                    for _c in _cands:
                        if _c.upper() not in _EXCL:
                            _psym = _c.upper(); break
                if _psym:
                    _pkrw = f'KRW-{_psym}'
                    _pinfo = await self._get_current_price(_pkrw, force_live=True)
                    if _pinfo and _pinfo.get('price', 0) > 0:
                        from datetime import datetime as _dtp
                        _pts = _dtp.now().strftime('%H:%M')
                        _pchg = _pinfo.get('change_pct', _pinfo.get('change', 0))
                        _pexch = _pinfo.get('exchange', '?')
                        _price_reply = (
                            f"✅ {_psym} 实时价格：₩{self._fmt_price(_pinfo['price'])} "
                            f"{_pchg:+.2f}%\n基于 {_pts} [{_pexch}] 实时报价"
                        )
                        self.conversation_history.append({
                            'timestamp': datetime.now().isoformat(),
                            'message': _price_reply,
                            'type': 'assistant'
                        })
                        return _price_reply
            
            # 使用LLM处理所有消息
            response = await self._process_with_llm(user_message)
            
            # 🆕 如果有告警，追加到回复中
            if alerts:
                alert_summary = "\n\n📢 持仓告警提示：\n"
                for alert in alerts:
                    severity_icon = {
                        "CRITICAL": "🔴",
                        "HIGH": "⚠️",
                        "SUCCESS": "✅",
                        "GOOD_NEWS": "📈"
                    }.get(alert['severity'], "ℹ️")
                    alert_summary += f"{severity_icon} {alert['message']}\n"
                response += alert_summary
            
            # 添加回复到历史
            self.conversation_history.append({
                'timestamp': datetime.now().isoformat(),
                'message': response,
                'type': 'assistant'
            })
            
            return response
            
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            import traceback
            traceback.print_exc()
            return f"❌ 抱歉，处理您的请求时出错了: {str(e)}"
    
    async def _check_position_alerts(self) -> List[Dict[str, Any]]:
        """自动检查持仓告警"""
        if not self.tracker or not self.tracker.positions:
            return []
        
        try:
            # 获取所有持仓的当前价格
            current_prices = {}
            for symbol in self.tracker.positions.keys():
                price_info = await self._get_current_price(symbol)
                if price_info:
                    current_prices[symbol] = price_info['price']
                else:
                    # 如果无法获取价格，使用买入价
                    current_prices[symbol] = self.tracker.positions[symbol]['avg_entry_price']
            
            # 检查告警
            alerts = self.tracker.check_position_alerts(current_prices)
            
            if alerts:
                logger.info(f"🔔 检测到 {len(alerts)} 条持仓告警")
            
            return alerts
            
        except Exception as e:
            logger.error(f"检查持仓告警失败: {e}")
            return []
    
    
    async def _fetch_all_crypto_prices(self) -> dict:
        """
        从 Upbit + Bithumb 批量获取全量价格，合并后返回。
        Upbit:   pyupbit.get_current_price(markets_list) — 1次调用，238+币
        Bithumb: pybithumb.get_current_price('ALL')      — 1次调用，448+币
        结果缓存 5 小时（同一进程内复用）。
        返回: {symbol(KRW-XXX): {price, change_pct, volume, exchange}}
        """
        import time as _time
        cls = self.__class__
        now = _time.time()
        if cls._crypto_price_cache and (now - cls._crypto_price_cache_ts) < cls._MARKET_CACHE_TTL:
            age_min = int((now - cls._crypto_price_cache_ts) / 60)
            logger.info(f'加密货币行情缓存命中（{age_min}分钟前拉取，剩余有效期约{cls._MARKET_CACHE_TTL//60 - age_min}分钟）')
            return cls._crypto_price_cache

        combined: dict = {}

        async def _fetch_upbit():
            try:
                import pyupbit as _upbit
                markets = await asyncio.to_thread(_upbit.get_tickers, fiat='KRW')
                if not markets:
                    return {}
                raw = await asyncio.to_thread(_upbit.get_current_price, markets)
                if not raw:
                    return {}
                result = {}
                for sym, price in raw.items():
                    if price is None:
                        continue
                    result[sym] = {
                        'price': float(price),
                        'change_pct': 0.0,   # 批量接口不含涨跌幅，后续可补
                        'volume': 0,
                        'exchange': 'upbit',
                    }
                logger.info(f'Upbit 批量价格: {len(result)} 个')
                return result
            except Exception as e:
                logger.warning(f'Upbit 批量获取失败: {e}')
                return {}

        async def _fetch_bithumb():
            try:
                import pybithumb as _bithumb
                raw = await asyncio.to_thread(_bithumb.get_current_price, 'ALL')
                if not isinstance(raw, dict):
                    return {}
                result = {}
                for coin, data in raw.items():
                    if coin == 'date':
                        continue
                    try:
                        price = float(data.get('closing_price', 0))
                        prev  = float(data.get('prev_closing_price', price) or price)
                        chg   = ((price - prev) / prev * 100) if prev else 0.0
                        vol   = float(data.get('acc_trade_value_24H', 0) or 0)
                        sym   = f'KRW-{coin}'
                        result[sym] = {
                            'price': price,
                            'change_pct': round(chg, 2),
                            'volume': vol,   # 24H 거래대금 (KRW)
                            'exchange': 'bithumb',
                        }
                    except Exception:
                        continue
                logger.info(f'Bithumb 批量价格: {len(result)} 个')
                return result
            except Exception as e:
                logger.warning(f'Bithumb 批量获取失败: {e}')
                return {}

        # 两个交易所并发
        upbit_data, bithumb_data = await asyncio.gather(
            _fetch_upbit(), _fetch_bithumb(), return_exceptions=False
        )

        # 合并：Bithumb 优先级最高（含成交量+涨跌幅），Upbit 仅补充 Bithumb 没有的币种
        combined.update(upbit_data)   # 先放 Upbit（低优先级底层）
        for sym, info in bithumb_data.items():
            if sym in combined:
                # Bithumb 覆盖价格、涨跌幅、成交量（Bithumb 数据更完整）
                combined[sym].update({
                    'price':      info['price'],
                    'change_pct': info['change_pct'],
                    'volume':     info['volume'],
                    'exchange':   'bithumb',
                })
            else:
                combined[sym] = info

        logger.info(f'全交易所合并: {len(combined)} 个币种')
        # 写入缓存
        cls._crypto_price_cache = combined
        cls._crypto_price_cache_ts = _time.time()
        return combined

    async def _resolve_query_price_tags(self, llm_response: str) -> tuple[str, dict]:
        """
        提取 LLM 回复中所有 [QUERY_PRICE|X] 标签，并发查询所有价格。
        返回: (标签集合对应的价格文本dict {symbol: price_line}, 实际 price_info dict)
        """
        import re as _re
        tags = _re.findall(r'\[QUERY_PRICE\|([^\]]+)\]', llm_response)
        if not tags:
            return {}, {}

        symbols = list(dict.fromkeys(t.strip() for t in tags))  # 去重保序

        # 并发查所有（force_live=True：绕过缓存，直接从交易所获取实时价格）
        results = await asyncio.gather(
            *[self._get_current_price(s, force_live=True) for s in symbols],
            return_exceptions=True
        )

        price_lines = {}   # symbol → 格式化文本
        price_infos = {}   # symbol → raw info dict
        for sym, result in zip(symbols, results):
            if result and not isinstance(result, Exception):
                # 按交易所原始精度显示，不做额外四舍五入
                price_lines[sym] = (
                    f"{sym}: ₩{self._fmt_price(result['price'])}"
                    f" ({result.get('change_pct', 0):+.2f}%)"
                    f" [{result.get('exchange', '?')}实时]"
                )
                price_infos[sym] = result
            else:
                price_lines[sym] = f"{sym}: 无法获取实时价格"

        return price_lines, price_infos

    async def _compute_technical_context(self, symbols: list) -> str:
        """
        对指定股票/加密货币代码列表，拉取历史K线并运行 AdvancedIndicatorMonitor
        计算全量技术指标（RSI/MACD/布林带/MFI/OBV/CMF/ATR/ADX/EMA排列/成交量异常/市场状态），
        返回格式化的技术分析上下文字符串，供 LLM 进行深度推荐研判。
        """
        if not symbols:
            return ""

        try:
            from openclaw.skills.analysis.advanced_indicator_monitor import AdvancedIndicatorMonitor
            import pandas as _pd
        except ImportError:
            logger.warning("AdvancedIndicatorMonitor 不可用，跳过技术指标计算")
            return ""

        monitor = AdvancedIndicatorMonitor()
        results = []

        async def _analyze_one(sym: str) -> str:
            try:
                # 1. 根据品种类型获取 OHLCV 数据
                candles = []

                if sym.isdigit() and len(sym) == 6:
                    # 韩股 → pykrx
                    from pykrx import stock as _krx
                    from datetime import datetime as _dt2, timedelta as _td2
                    start = (_dt2.now() - _td2(days=60)).strftime('%Y%m%d')
                    end   = _dt2.now().strftime('%Y%m%d')
                    df_raw = await asyncio.to_thread(
                        _krx.get_market_ohlcv_by_date, start, end, sym
                    )
                    if df_raw is not None and not df_raw.empty:
                        for _date, _row in df_raw.iterrows():
                            candles.append({
                                'timestamp': str(_date),
                                'open':   float(_row.get('시가', 0)),
                                'high':   float(_row.get('고가', 0)),
                                'low':    float(_row.get('저가', 0)),
                                'close':  float(_row.get('종가', 0)),
                                'volume': float(_row.get('거래량', 0)),
                            })

                elif sym.startswith('KRW-') or sym.startswith('USDT-'):
                    # 加密货币 → pyupbit 日线K线
                    try:
                        import pyupbit as _upbit
                        # 用户要求参考最近8小时波动率，改用小时线 (minute60)
                        # 获取过去48小时数据，足以计算 ATR(14) 或观察8小时趋势
                        df_raw = await asyncio.to_thread(
                            _upbit.get_ohlcv, sym, count=48, interval='minute60'
                        )
                        if df_raw is not None and not df_raw.empty:
                            for _date, _row in df_raw.iterrows():
                                candles.append({
                                    'timestamp': str(_date),
                                    'open':   float(_row.get('open', 0)),
                                    'high':   float(_row.get('high', 0)),
                                    'low':    float(_row.get('low', 0)),
                                    'close':  float(_row.get('close', 0)),
                                    'volume': float(_row.get('volume', 0)),
                                })
                    except Exception as _ce:
                        logger.debug(f"加密货币K线获取失败 {sym}: {_ce}")

                elif sym.isalpha() and len(sym) <= 5:
                    # 美股 → yfinance
                    try:
                        import yfinance as _yf
                        ticker_obj = _yf.Ticker(sym)
                        df_raw = await asyncio.to_thread(
                            ticker_obj.history, period='3mo', interval='1d'
                        )
                        if df_raw is not None and not df_raw.empty:
                            for _date, _row in df_raw.iterrows():
                                candles.append({
                                    'timestamp': str(_date),
                                    'open':   float(_row.get('Open', 0)),
                                    'high':   float(_row.get('High', 0)),
                                    'low':    float(_row.get('Low', 0)),
                                    'close':  float(_row.get('Close', 0)),
                                    'volume': float(_row.get('Volume', 0)),
                                })
                    except Exception as _ue:
                        logger.debug(f"美股K线获取失败 {sym}: {_ue}")

                if len(candles) < 20:
                    return f"[{sym}] K线数据不足（仅{len(candles)}根），跳过指标计算\n"

                # 2. 喂入 AdvancedIndicatorMonitor
                for c in candles:
                    monitor.update_price_data(sym, c)
                analysis = monitor.analyze_all_indicators(sym)

                if 'error' in analysis:
                    return f"[{sym}] 指标计算错误: {analysis['error']}\n"

                # 3. 格式化结果
                sig    = analysis.get('signals', {})
                mom    = analysis.get('momentum', {})
                trend  = analysis.get('trend', {})
                vol_i  = analysis.get('volume', {})
                mflow  = analysis.get('money_flow', {})
                volat  = analysis.get('volatility', {})
                mstate = analysis.get('market_state', {})

                rsi   = mom.get('rsi', 0)
                macd  = mom.get('macd', {})
                emas  = trend.get('emas', {})
                adx   = trend.get('adx', 0)

                # RSI 状态
                if rsi >= 70:
                    rsi_note = '超买'
                elif rsi <= 30:
                    rsi_note = '超卖'
                else:
                    rsi_note = '中性'

                # MACD
                macd_signal = macd.get('signal', 'NEUTRAL')
                macd_note   = {'BULLISH_CROSS':'金叉','BEARISH_CROSS':'死叉',
                               'BULLISH':'看涨','BEARISH':'看跌'}.get(macd_signal, '中性')

                # EMA 排列
                ema_align = trend.get('ema_alignment', 'UNKNOWN')
                ema_note  = {'BULLISH':'多头排列','BEARISH':'空头排列','MIXED':'混合'}.get(ema_align, '未知')

                # 成交量
                vol_ratio   = vol_i.get('volume_ratio', 1.0)
                vol_anomaly = vol_i.get('is_anomaly', False)
                vol_note    = f"{'⚡异常放量' if vol_anomaly else '正常'}({vol_ratio:.1f}x均量)"

                # 资金流
                mfi       = mflow.get('mfi', 50)
                cmf       = mflow.get('cmf', 0)
                flow_note = mflow.get('overall_flow', 'MIXED')
                flow_cn   = {'POSITIVE':'🟢资金净流入','NEGATIVE':'🔴资金净流出','MIXED':'⚪混合'}.get(flow_note, flow_note)

                # 布林带压缩
                bb_squeeze = volat.get('bollinger_squeeze', {})
                bb_note = ''
                if bb_squeeze.get('is_squeezed'):
                    bb_dir = bb_squeeze.get('breakout_direction', 'PENDING')
                    bb_note = f"布林带收窄蓄力({'突破向上' if bb_dir=='BULLISH' else '突破向下' if bb_dir=='BEARISH' else '待突破'})"

                # ATR 波动率
                atr_pct  = volat.get('atr_percent', 0)
                hist_vol = volat.get('historical_volatility', 0)

                # 市场状态
                market_state_note = {
                    'TRENDING': '趋势行情', 'RANGING': '震荡行情',
                    'VOLATILE': '高波动', 'BREAKOUT': '突破行情', 'UNCERTAIN': '不确定'
                }.get(mstate.get('primary_state', ''), mstate.get('primary_state', ''))

                # 综合信号结论
                action     = sig.get('action', 'HOLD')
                confidence = sig.get('confidence', 0)
                buy_sigs   = sig.get('buy_signals', [])
                sell_sigs  = sig.get('sell_signals', [])
                action_cn  = {'BUY':'📈建议买入','SELL':'📉建议卖出','HOLD':'⏸持有观望'}.get(action, action)

                lines = [
                    f"\n📐 {sym} 技术指标综合分析",
                    f"  市场状态: {market_state_note}  |  ADX趋势强度: {adx:.1f}",
                    f"  RSI(14): {rsi:.1f} ({rsi_note})  |  ATR波动率: {atr_pct:.2f}%  |  年化波动率: {hist_vol:.1f}%",
                    f"  MACD: {macd_note}  |  EMA排列: {ema_note}",
                    f"  成交量: {vol_note}  |  MFI资金强度: {mfi:.1f}  |  CMF: {cmf:.3f}",
                    f"  资金流向: {flow_cn}",
                ]
                if bb_note:
                    lines.append(f"  {bb_note}")
                if buy_sigs:
                    lines.append(f"  看涨信号: {', '.join(buy_sigs)}")
                if sell_sigs:
                    lines.append(f"  看跌信号: {', '.join(sell_sigs)}")
                lines.append(f"  ➡ 系统综合判断: {action_cn}（置信度{confidence:.0%}）")

                return '\n'.join(lines)

            except Exception as _ex:
                logger.warning(f"技术指标计算失败 {sym}: {_ex}")
                return ""

        # 并发分析所有 symbols（最多5个，避免超时）
        symbols_to_analyze = symbols[:5]
        parts = await asyncio.gather(*[_analyze_one(s) for s in symbols_to_analyze])
        valid_parts = [p for p in parts if p.strip()]
        if not valid_parts:
            return ""

        header = "\n\n【技术指标深度分析（AdvancedIndicatorMonitor 实时计算）】"
        footer = "\n（以上指标基于60日日线K线计算：RSI/MACD/布林带/MFI/OBV/CMF/ATR/ADX/EMA排列/成交量异常/市场状态）"
        return header + ''.join(valid_parts) + footer

    def _calculate_target_price(self, sym, price, analysis_data):
        """
        [ATR动态目标算法] 计算稳健/进取目标价和止损位
        供 _score_and_rank_candidates 和 _handle_direct_trade 共用
        """
        try:
            if not analysis_data:
                # 若无分析数据，默认低波动
                raw_atr = 1.0 
            else:
                raw_atr = analysis_data.get('volatility', {}).get('atr_percent', 0.0)
        except:
            raw_atr = 0.0

        # [ATR动态目标算法] 优化版
        # 区分处理：股票(日线ATR) vs 加密(小时线ATR)
        is_crypto = '-' in sym
        if is_crypto:
            # 针对 USDT/USDC 稳定币特殊处理
            if 'USDT' in sym or 'USDC' in sym:
                atr_pct = 0.2
            else:
                # 小时线 ATR，放大系数 1.5倍 (代表8小时级别趋势)
                atr_reference = raw_atr * 1.5
                # 设定最小波动率基准 max(x, 0.8)
                atr_pct = max(atr_reference, 0.8)
        else:
            # 日线 (股票)
            atr_pct = max(raw_atr, 1.5)

        # 权重系数：稳健=2.5倍ATR，进取=4.0倍ATR
        w_steady = 2.5
        w_aggr   = 4.0
        
        t_steady_pct = atr_pct * w_steady
        t_aggr_pct   = atr_pct * w_aggr
        
        # 保底逻辑 (Floor)
        min_target = 0.5 if ('USDT' in sym or 'USDC' in sym) else (2.0 if is_crypto else 2.5)
        if t_steady_pct < min_target:
             t_steady_pct = min_target
             t_aggr_pct = min_target * 1.5

        # 封顶逻辑 (Cap)
        t_steady_pct = min(t_steady_pct, 15.0)
        t_aggr_pct   = min(t_aggr_pct, 25.0)

        target_steady = price * (1 + t_steady_pct / 100.0)
        target_aggr   = price * (1 + t_aggr_pct / 100.0)
        
        # 止损：硬性 -10% 或 ATR*2.0
        stop_base = 2.0
        stop_pct = min(10.0, max(5.0, atr_pct * stop_base))
        stop_loss = price * (1 - stop_pct / 100.0)
        
        return target_steady, target_aggr, t_steady_pct, t_aggr_pct, stop_loss, stop_pct

    async def _score_and_rank_candidates(
        self,
        candidates: dict,          # {symbol: {price, change_pct, volume, ...}}
        top_n: int = 20,           # 参与技术分析的候选数量（按成交量预筛）
        is_crypto: bool = True,
    ) -> str:
        """
        多维度量化打分引擎：
          1. 价格动量分（涨跌幅）
          2. 成交量分（流动性）
          3. 技术指标分（RSI/MACD/MFI/ADX/EMA排列/布林带/OBV）
          4. 综合评分后返回 Markdown 格式的打分报告，供 LLM 使用。
        """
        if not candidates:
            return ""

        try:
            from openclaw.skills.analysis.advanced_indicator_monitor import AdvancedIndicatorMonitor
        except ImportError:
            return ""

        # ── 步骤1：按成交量预筛 top_n 候选 ──
        sorted_cands = sorted(
            candidates.items(),
            key=lambda x: x[1].get('volume', 0),
            reverse=True
        )[:top_n]

        # ── 步骤2：并发拉取 K 线并运行 AdvancedIndicatorMonitor ──
        async def _fetch_candles_and_score(sym: str, info: dict):
            """拉取近8小时K线数据：加密货币支持 Upbit/Bithumb，根据 info['exchange'] 自动选择"""
            candles = []
            try:
                # ── Bithumb K线获取 (如果来源是 Bithumb) ──
                if info.get('exchange') == 'bithumb':
                    try:
                        import pybithumb as _bithumb
                        # Bithumb 代码格式：KRW-BTC -> BTC
                        code = sym.replace('KRW-', '')
                        # Bithumb 5分钟线 (interval='minute5' 是 pyupbit 风格，pybithumb 可能不同，但经测试部分版本兼容或自动识别)
                        # 标准 pybithumb 可能不支持 interval 参数，直接 get_ohlcv 默认日线。
                        # 若需分钟线，需确认库支持。假设已安装支持版本，或尝试 '3M', '5M' 等。
                        # 保守起见，优先尝试 'minute5'。如果失败则回退 pyupbit。
                        df_raw = await asyncio.to_thread(
                            _bithumb.get_ohlcv, code, interval='minute5' 
                        )
                        # Bithumb 可能返回全部历史，需截取最后96根
                        if df_raw is not None and not df_raw.empty:
                            df_raw = df_raw.tail(96)
                            for _ts, row in df_raw.iterrows():
                                candles.append({
                                    'timestamp': str(_ts),
                                    'open': float(row.get('open', 0)),
                                    'high': float(row.get('high', 0)),
                                    'low':  float(row.get('low', 0)),
                                    'close': float(row.get('close', 0)),
                                    'volume': float(row.get('volume', 0)),
                                })
                    except Exception as e_bithumb:
                        logger.warning(f"Bithumb K线获取失败 {sym}, 尝试 Upbit: {e_bithumb}")
                        # Fallthrough to Upbit logic below

                # ── Upbit K线获取 (默认或 Bithumb 失败回退) ──
                if not candles and (sym.startswith('KRW-') or sym.startswith('USDT-')):
                    # 5分钟线 × 96根 = 近8小时（加密货币24H交易，始终有数据）
                    import pyupbit as _upbit
                    df_raw = await asyncio.to_thread(
                        _upbit.get_ohlcv, sym, count=96, interval='minute5'
                    )
                    if df_raw is not None and not df_raw.empty:
                        for _, row in df_raw.iterrows():
                            candles.append({
                                'timestamp': str(_),
                                'open': float(row.get('open', 0)),
                                'high': float(row.get('high', 0)),
                                'low':  float(row.get('low', 0)),
                                'close': float(row.get('close', 0)),
                                'volume': float(row.get('volume', 0)),
                            })
                elif sym.isdigit() and len(sym) == 6:
                    from pykrx import stock as _krx
                    from datetime import datetime as _dt2, timedelta as _td2
                    # 优先：当天分钟线（近5小时）
                    try:
                        today_str = _dt2.now().strftime('%Y%m%d')
                        df_raw = await asyncio.to_thread(
                            _krx.get_market_ohlcv_by_minute, today_str, sym
                        )
                        if df_raw is not None and not df_raw.empty:
                            # 只取最近8小时（最后480根，每根1分钟）
                            df_raw = df_raw.tail(480)  # 480分钟=8小时
                            for _ts, _row in df_raw.iterrows():
                                candles.append({
                                    'timestamp': str(_ts),
                                    'open':   float(_row.get('시가', 0)),
                                    'high':   float(_row.get('고가', 0)),
                                    'low':    float(_row.get('저가', 0)),
                                    'close':  float(_row.get('종가', 0)),
                                    'volume': float(_row.get('거래량', 0)),
                                })
                    except Exception:
                        pass
                    # 回退：近5个交易日日线
                    if len(candles) < 10:
                        candles = []
                        start = (_dt2.now() - _td2(days=7)).strftime('%Y%m%d')
                        end   = _dt2.now().strftime('%Y%m%d')
                        df_raw = await asyncio.to_thread(
                            _krx.get_market_ohlcv_by_date, start, end, sym
                        )
                        if df_raw is not None and not df_raw.empty:
                            for _date, _row in df_raw.iterrows():
                                candles.append({
                                    'timestamp': str(_date),
                                    'open':   float(_row.get('시가', 0)),
                                    'high':   float(_row.get('고가', 0)),
                                    'low':    float(_row.get('저가', 0)),
                                    'close':  float(_row.get('종가', 0)),
                                    'volume': float(_row.get('거래량', 0)),
                                })
            except Exception as e:
                logger.debug(f"K线获取失败 {sym}: {e}")

            if len(candles) < 10:
                return sym, info, None

            monitor = AdvancedIndicatorMonitor()
            for c in candles:
                monitor.update_price_data(sym, c)
            try:
                analysis = monitor.analyze_all_indicators(sym)
            except Exception:
                analysis = None
            return sym, info, analysis

        tasks = [_fetch_candles_and_score(sym, info) for sym, info in sorted_cands]

        # ── 步骤2b：并发拉取新闻头条（与K线并行） ──
        raw_results, news_headlines = await asyncio.gather(
            asyncio.gather(*tasks, return_exceptions=True),
            self._fetch_recent_news_headlines(),
        )

        # 为每个候选品种计算新闻情绪分
        # 关键词映射：代码 → 搜索关键词列表
        _CRYPTO_KW = {
            'BTC': ['bitcoin', 'btc', '비트코인', '比特币'],
            'ETH': ['ethereum', 'eth', '이더리움', '以太坊'],
            'XRP': ['ripple', 'xrp', '리플', '瑞波'],
            'SOL': ['solana', 'sol', '솔라나'],
            'DOGE': ['dogecoin', 'doge', '도지'],
            'ADA': ['cardano', 'ada', '카르다노'],
            'AVAX': ['avalanche', 'avax'],
            'DOT': ['polkadot', 'dot', '폴카닷'],
            'LINK': ['chainlink', 'link'],
            'MATIC': ['polygon', 'matic'],
            'TRX': ['tron', 'trx'],
            'LTC': ['litecoin', 'ltc', '라이트코인'],
            'SHIB': ['shiba', 'shib'],
            'ATOM': ['cosmos', 'atom'],
            'UNI': ['uniswap', 'uni'],
        }
        _POS_WORDS = [
            # 金融/市场 (韩中英)
            '급등', '상승', '호재', '강세', '돌파', '신고가', '매수', '상장',
            '上涨', '利好', '暴涨', '突破', '涨停',
            'surge', 'rally', 'bullish', 'gain', 'rise', 'jump', 'soar',
            'buy', 'upgrade', 'outperform', 'breakout', 'record high', 'all-time high',
            'adoption', 'partnership', 'launch', 'approved', 'etf approved',
            'profit', 'beat expectations', 'strong earnings', 'dividend',
            # 政治/宏观
            'deal', 'agreement', 'ceasefire', 'peace', 'cooperation', 'trade deal',
            'stimulus', 'rate cut', 'easing', 'growth', 'recovery',
            # 体育/娱乐
            'win', 'champion', 'gold', 'victory', 'award', 'record',
        ]
        _NEG_WORDS = [
            # 金融/市场 (韩中英)
            '급락', '하락', '악재', '약세', '매도', '상장폐지', '규제',
            '下跌', '利空', '暴跌', '崩盘', '监管',
            'crash', 'dump', 'bearish', 'fall', 'drop', 'plunge', 'slump',
            'sell', 'downgrade', 'underperform', 'ban', 'hack', 'lawsuit',
            'fraud', 'bankruptcy', 'delisted', 'regulation', 'crackdown',
            'miss expectations', 'loss', 'layoff', 'recall',
            # 政治/宏观
            'war', 'conflict', 'sanction', 'tariff', 'inflation', 'recession',
            'rate hike', 'debt crisis', 'default', 'protest', 'coup',
            'earthquake', 'disaster', 'pandemic',
            # 体育/娱乐
            'injury', 'suspended', 'banned', 'scandal',
        ]

        def _news_score_for(sym: str, info: dict) -> tuple:
            """返回 (score, matched_count, sentiment_str)"""
            short = sym.replace('KRW-', '').replace('USDT-', '')
            name  = info.get('name', '').lower()
            # 候选关键词：代码短名 + 公司名 + 预设别名
            kws = [short.lower(), name] + _CRYPTO_KW.get(short, [])
            kws = [k for k in kws if len(k) >= 2]

            pos_cnt = neg_cnt = 0
            for hl in news_headlines:
                if any(kw in hl for kw in kws):
                    pos_cnt += sum(1 for w in _POS_WORDS if w in hl)
                    neg_cnt += sum(1 for w in _NEG_WORDS if w in hl)

            net = pos_cnt - neg_cnt
            # 映射到 -15 ~ +15
            if net >= 5:   ns = 15.0
            elif net >= 3: ns = 10.0
            elif net >= 1: ns = 5.0
            elif net == 0: ns = 0.0
            elif net >= -2: ns = -5.0
            elif net >= -4: ns = -10.0
            else:           ns = -15.0
            sentiment = f"利好{pos_cnt}条/利空{neg_cnt}条"
            return ns, pos_cnt + neg_cnt, sentiment

        # ── 步骤3：多维度打分 ──
        scored = []
        for r in raw_results:
            if isinstance(r, Exception):
                continue
            sym, info, analysis = r
            price      = info.get('price', 0)
            chg_pct    = info.get('change_pct', 0)
            volume     = info.get('volume', 0)
            score      = 0.0
            score_detail = {}

            # A. 价格动量分（-10~+10）
            mom_s = max(-10, min(10, chg_pct * 1.5))
            score += mom_s
            score_detail['动量'] = f"{mom_s:+.1f}"

            # B. 成交量分（0~20）：按对数归一化
            import math
            vol_log = math.log10(volume + 1)
            vol_max = math.log10(max(c[1].get('volume', 1) for c in sorted_cands) + 1)
            vol_s = (vol_log / vol_max * 20) if vol_max > 0 else 0
            score += vol_s
            score_detail['流动性'] = f"{vol_s:.1f}"

            if analysis and 'error' not in analysis:
                mom   = analysis.get('momentum', {})
                trend = analysis.get('trend', {})
                mflow = analysis.get('money_flow', {})
                vol_i = analysis.get('volume', {})
                sigs  = analysis.get('signals', {})

                # C. RSI 分（-10~+10）
                rsi = mom.get('rsi', 50)
                if 40 <= rsi <= 60:
                    rsi_s = 5.0   # 中性健康
                elif 30 <= rsi < 40 or 60 < rsi <= 70:
                    rsi_s = 3.0   # 轻微过热/超卖
                elif rsi < 30:
                    rsi_s = 8.0   # 超卖反弹机会
                else:
                    rsi_s = -5.0  # 超买风险
                score += rsi_s
                score_detail['RSI'] = f"{rsi:.0f}({rsi_s:+.1f})"

                # D. MACD 分（-8~+8）
                macd_sig = mom.get('macd', {}).get('signal', 'NEUTRAL')
                macd_s = {'BULLISH': 8, 'NEUTRAL': 0, 'BEARISH': -8}.get(macd_sig, 0)
                score += macd_s
                score_detail['MACD'] = f"{macd_sig}({macd_s:+d})"

                # E. ADX 趋势强度分（0~10）
                adx = trend.get('adx', 0)
                adx_s = min(10, adx / 5) if adx > 20 else 0
                score += adx_s
                score_detail['ADX'] = f"{adx:.0f}({adx_s:+.1f})"

                # F. MFI 资金流分（-8~+8）
                mfi = mflow.get('mfi', 50)
                if mfi < 20:
                    mfi_s = 8.0   # 超卖，资金可能流入
                elif mfi > 80:
                    mfi_s = -6.0  # 超买，资金可能流出
                elif 40 <= mfi <= 60:
                    mfi_s = 3.0
                else:
                    mfi_s = 0.0
                score += mfi_s
                score_detail['MFI'] = f"{mfi:.0f}({mfi_s:+.1f})"

                # G. OBV 趋势分（-5~+5）
                obv_trend = mflow.get('obv_trend', 'NEUTRAL')
                obv_s = {'BULLISH': 5, 'NEUTRAL': 0, 'BEARISH': -5}.get(obv_trend, 0)
                score += obv_s
                score_detail['OBV'] = f"{obv_trend}({obv_s:+d})"

                # H. 成交量异常加分（0~8）：放量突破
                vol_anomaly = vol_i.get('volume_ratio', 1.0)
                if vol_anomaly > 2.5:
                    vol_s2 = 8.0
                elif vol_anomaly > 1.5:
                    vol_s2 = 4.0
                else:
                    vol_s2 = 0.0
                score += vol_s2
                score_detail['量比'] = f"{vol_anomaly:.1f}x({vol_s2:+.1f})"

                # I. EMA 排列分（-5~+5）
                ema_align = trend.get('ema_alignment', 'NEUTRAL')
                ema_s = {'BULLISH': 5, 'NEUTRAL': 0, 'BEARISH': -5}.get(ema_align, 0)
                score += ema_s
                score_detail['EMA'] = f"{ema_align}({ema_s:+d})"

            # J. 新闻情绪分（-15~+15，高权重信源）
            news_s, news_cnt, news_label = _news_score_for(sym, info)
            score += news_s
            if news_cnt > 0:
                score_detail['新闻'] = f"{news_label}({news_s:+.0f})"

            scored.append({
                'sym': sym,
                'price': price,
                'chg_pct': chg_pct,
                'volume': volume,
                'score': score,
                'detail': score_detail,
                'analysis': analysis,
            })

        if not scored:
            return ""

        # ── 步骤4：按综合分降序，输出报告 ──
        scored.sort(key=lambda x: x['score'], reverse=True)
        lines = ["\n\n【量化打分排行（多维度综合评分，供LLM深度研判）】"]
        lines.append(f"{'排名':<4} {'代码':<14} {'现价':>12} {'涨跌':>7} {'综合分':>7}  评分明细")
        lines.append("─" * 80)
        for rank, item in enumerate(scored[:15], 1):
            sym      = item['sym']
            price    = item['price']
            
            # [ATR动态目标算法]
            target_steady, target_aggr, t_steady_pct, t_aggr_pct, stop_loss, stop_pct = \
                self._calculate_target_price(sym, price, item.get('analysis', {}))
            
            detail_str = ' | '.join(f"{k}:{v}" for k, v in item['detail'].items())
            lines.append(
                f"{rank:<4} {sym:<14} ₩{item['price']:>10,.4g} {item['chg_pct']:>+6.2f}%"
                f"  {item['score']:>6.1f}分  {detail_str}"
            )
            # 输出算法计算后的目标行
            lines.append(
                f"      👉 动态目标(ATR基准): 稳健₩{target_steady:,.0f}(+{t_steady_pct:.1f}%) / 进取₩{target_aggr:,.0f}(+{t_aggr_pct:.1f}%) / 止损₩{stop_loss:,.0f}(-{stop_pct:.1f}%)"
            )
            
            # 将稳健目标存入缓存，供买入时引用
            self._recommendation_targets[sym] = target_steady
            
        lines.append("─" * 80)
        lines.append("评分含义: 动量=价格动量, 流动性=成交量归一化, RSI/MACD/ADX/MFI/OBV/量比/EMA均为技术指标加减分, 新闻=100+全球RSS情绪分（高权重）")
        lines.append("★ 【强制规则】推荐必须且只能从以上排行榜中选取Top5，按综合分从高到低推荐，推荐理由必须引用该品种的综合分和各维度得分亮点。")
        lines.append("★ 【目标价引用】必须直接引用上方「算法目标」行中的计算结果，禁止LLM自行编造数值。")
        return "\n".join(lines)

    async def _fetch_all_stock_prices(self) -> dict:
        """
        从 pykrx 批量获取 KOSPI + KOSDAQ 全量行情。
        缓存 TTL = 5 分钟（近实时，避免每次拉取等待 5~15 秒）。
        返回: {ticker: {name, price, change_pct, volume_krw, market}}
        """
        import time as _time
        cls = self.__class__
        _TTL = 5 * 60   # 5 分钟
        now = _time.time()
        if cls._stock_price_cache and (now - cls._stock_price_cache_ts) < _TTL:
            age_sec = int(now - cls._stock_price_cache_ts)
            logger.info(f'韩股行情缓存命中（{age_sec}秒前拉取，TTL=5分钟）')
            return cls._stock_price_cache
        from pykrx import stock as krx
        from datetime import datetime as _dt, timedelta as _td

        today = _dt.now().strftime('%Y%m%d')
        # 取最近5个日历日保证有交易日
        start = (_dt.now() - _td(days=5)).strftime('%Y%m%d')

        async def _fetch_market(market: str) -> dict:
            try:
                df = await asyncio.to_thread(
                    krx.get_market_price_change, start, today, market=market
                )
                if df is None or df.empty:
                    return {}
                result = {}
                for ticker, row in df.iterrows():
                    try:
                        result[ticker] = {
                            'name': str(row.get('종목명', ticker)),
                            'price': float(row['종가']),
                            'change_pct': float(row.get('등락률', 0)),
                            'volume_krw': float(row.get('거래대금', 0)),
                            'market': market,
                        }
                    except Exception:
                        continue
                logger.info(f'pykrx {market}: {len(result)} 종목')
                return result
            except Exception as e:
                logger.warning(f'pykrx {market} 배치 실패: {e}')
                return {}

        kospi, kosdaq = await asyncio.gather(
            _fetch_market('KOSPI'), _fetch_market('KOSDAQ')
        )
        combined = {**kospi, **kosdaq}
        logger.info(f'한국 전체 주식 배치: {len(combined)} 종목')
        # 写入缓存
        cls._stock_price_cache = combined
        cls._stock_price_cache_ts = _time.time()
        return combined

    async def _process_with_llm(self, user_message: str) -> str:
        """
        使用 LLM 处理消息，实现真正的 tool-use 循环：
          Round 1 → LLM 可以输出 [QUERY_PRICE|X] 表达"我要查这些价格"
          System  → 并发查询所有价格
          Round 2 → 若是推荐/分析类请求，把价格喂回 LLM 生成完整分析
                    否则直接替换标签为价格行（查价/买卖操作流程）
        """
        if not self.model_manager:
            return await self._fallback_processing(user_message)

        try:
            # 1. 收集当前系统状态
            context = self._build_system_context()

            # 2. 快速预判：DART 公告仅在明确涉及韩股+分析意图时获取
            # 条件：① 消息含韩股关键词 OR 6位股票代码 OR 持仓有韩股
            #       AND ② 消息含分析/推荐/操作意图词
            _KRX_TOPIC_KWS = ['韩股', '韩国股', '코스피', '코스닥', 'kospi', 'kosdaq',
                               '韩国', '주식', '공시', '한국']
            _DART_INTENT_KWS = ['推荐', '建议', '分析', '策略', '研判', '公告', 'DART', '공시',
                                 '怎么看', '前景', '机会', '风险', '值不值', '应该买',
                                 '应该卖', '涨还是跌', '走势', '利好', '利空', '深度']
            _has_krx_code = bool(re.search(r'\b\d{6}\b', user_message))
            _held_krx = [s for s in (self.tracker.positions if self.tracker else {})
                         if s.isdigit() and len(s) == 6]
            _has_krx_context = (
                any(k in user_message.lower() for k in _KRX_TOPIC_KWS)
                or _has_krx_code
                or bool(_held_krx)  # 持仓含韩股，操作/分析时需要公告
            )
            _has_dart_intent = any(k in user_message for k in _DART_INTENT_KWS)
            _need_dart = _has_krx_context and _has_dart_intent
            dart_context = ''
            if _need_dart:
                dart_context = await self._fetch_relevant_announcements(user_message)
                if dart_context:
                    context = context + dart_context

            # 3. 判断消息复杂度，路由到对应模型
            task_type = self._classify_task_type(user_message, bool(dart_context))

            # 4. 判断是否是"推荐/分析"类请求
            RECOMMEND_KWS = ['推荐', '建议', '分析', '投资建议', '怎么看', '应该买', '值不值',
                             '涨还是跌', '机会', '看涨', '看跌', '前景', '市场行情']
            CRYPTO_KWS = ['虚拟货币', '加密货币', '加密', '比特币', 'btc', 'eth', 'sol',
                          'xrp', '以太', '莱特', '币种', 'coin', 'crypto', '数字货币',
                          '非主流', '山寨', 'doge', 'ada', 'avax', 'dot', 'link',
                          # 口语/俗语
                          '币子', '币圈', '炒币', '囤币', '主流币', '空气币', '数字币',
                          '山寨币', '公链', '链圈', 'defi', 'nft', 'web3', '代币']
            is_recommend = any(k in user_message for k in RECOMMEND_KWS)
            is_crypto_topic = (
                any(k in user_message.lower() for k in CRYPTO_KWS)
                # 消息中含「币」且不含明确韩股词汇时，也视为加密货币话题
                or ('币' in user_message and not any(k in user_message for k in
                    ['股票', '韩股', 'kospi', 'kosdaq', '코스', '调仓', '减仓', '持仓', '加仓']))
            )

            # 5a. 推荐类 + 韩股 → pykrx 全量行情注入 context
            STOCK_KWS = ['韩股', '股票', '上市公司', 'kospi', 'kosdaq', '코스피', '코스닥',
                         '주식', '한국주식', '种股', '股']
            is_stock_topic = any(k in user_message.lower() for k in STOCK_KWS)
            # 未明确指定市场时（纯「推荐一下」等），视为通用推荐，两类数据都预取
            is_general_recommend = is_recommend and not is_stock_topic and not is_crypto_topic
            if is_recommend and (is_stock_topic or is_general_recommend):
                try:
                    stock_data = await self._fetch_all_stock_prices()
                    if stock_data:
                        # 按거래대금(成交金额)降序，流动性好的排前面
                        sorted_stocks = sorted(
                            stock_data.items(),
                            key=lambda x: x[1].get('volume_krw', 0),
                            reverse=True
                        )
                        # 通用推荐（无市场词）只取 Top50，避免上下文过长；明确韩股请求取 Top200
                        top_n = 50 if is_general_recommend else 200
                        sorted_stocks = sorted_stocks[:top_n]
                        stock_lines = '\n'.join(
                            f"{ticker}({info['name']}): ₩{self._fmt_price(info['price'])}"
                            f"  涨跌{info['change_pct']:+.2f}%"
                            f"  거래대금₩{info['volume_krw']/1e8:.1f}亿"
                            f"  [{info['market']}]"
                            for ticker, info in sorted_stocks
                        )
                        from datetime import datetime as _now_dt
                        _fetch_ts = _now_dt.now().strftime('%Y-%m-%d %H:%M:%S')
                        context += (
                            f'\n\n【KRX股票实时行情（采集时间: {_fetch_ts}，成交额Top{top_n}，共{len(stock_data)}只中按成交额排序）】\n'
                            f'{stock_lines}\n'
                            f'★ 数据采集于 {_fetch_ts}（有效期5小时内）。'
                            '请直接基于这些数据分析推荐，严禁输出[QUERY_PRICE]标签。可按成交量/涨幅/市场等维度筛选。'
                        )
                        logger.info(f'韩股全量行情注入: top{top_n}/{len(stock_data)} 只，采集时间 {_fetch_ts}')
                        # 量化打分：对Top候选进行多维度评分排名
                        try:
                            _stock_score_input = {
                                ticker: {
                                    'price': info['price'],
                                    'change_pct': info['change_pct'],
                                    'volume': info.get('volume_krw', 0),
                                }
                                for ticker, info in sorted_stocks
                            }
                            scoring_ctx = await self._score_and_rank_candidates(
                                _stock_score_input, top_n=20, is_crypto=False
                            )
                            if scoring_ctx:
                                context += scoring_ctx
                                logger.info("📊 量化打分表已注入（韩股）")
                        except Exception as _se:
                            logger.warning(f"韩股打分失败: {_se}")
                except Exception as _e:
                    logger.warning(f'韩股全量行情获取失败: {_e}')

            # 5b. 推荐类 + 加密货币 → 从两个交易所全量拉取价格注入 context
            prefetched_prices: dict = {}
            if is_recommend and (is_crypto_topic or is_general_recommend) and self.crypto_fetcher:
                try:
                    prefetched_prices = await self._fetch_all_crypto_prices()
                    if prefetched_prices:
                        # 按 24H 成交量降序（流动性好的排前面），无成交量的排后
                        sorted_pairs = sorted(
                            prefetched_prices.items(),
                            key=lambda x: x[1].get('volume', 0),
                            reverse=True
                        )
                        price_lines = '\n'.join(
                            f"{sym}: ₩{self._fmt_price(info['price'])}  涨跌{info.get('change_pct', 0):+.2f}%"
                            f"  24H成交额₩{info.get('volume', 0)/1e8:.1f}亿"
                            f"  [{info.get('exchange','?')}]"
                            for sym, info in sorted_pairs
                        )
                        from datetime import datetime as _now_dt2
                        _crypto_ts = _now_dt2.now().strftime('%Y-%m-%d %H:%M:%S')
                        context += (
                            f'\n\n【两大交易所全量加密货币实时行情（采集时间: {_crypto_ts}，共{len(prefetched_prices)}个币种，已按24H成交量排序）】\n'
                            f'{price_lines}\n'
                            f'★ 数据采集于 {_crypto_ts}（有效期5小时内）。'
                            '以上是 Upbit+Bithumb 两个交易所当前全部币种实时数据，'
                            '请直接基于这些真实数据进行分析和推荐，严禁再输出任何 [QUERY_PRICE] 标签。'
                            '可根据用户要求筛选主流/非主流/涨幅最大/成交量最高等维度。'
                        )
                        logger.info(f'全量加密货币价格注入: 共{len(prefetched_prices)}个币种，采集时间 {_crypto_ts}')
                        # 量化打分：对Top候选进行多维度评分排名
                        try:
                            scoring_ctx = await self._score_and_rank_candidates(
                                prefetched_prices, top_n=20, is_crypto=True
                            )
                            if scoring_ctx:
                                context += scoring_ctx
                                logger.info("📊 量化打分表已注入（加密货币）")
                        except Exception as _se:
                            logger.warning(f"加密货币打分失败: {_se}")
                except Exception as _e:
                    logger.warning(f'全量加密货币价格获取失败: {_e}')

            # 5c. 技术指标深度分析 → 对消息中明确提及的股票/加密货币代码/名称计算全套指标
            # 条件：用户在推荐/分析/建议/怎么样等场景下提到了具体品种
            ANALYSIS_KWS = ['推荐', '建议', '分析', '怎么样', '怎么看', '走势', '策略',
                             '值不值', '涨还是跌', '应该买', '风险', '前景', 'K线', '技术面']
            is_single_symbol_analysis = any(k in user_message for k in ANALYSIS_KWS)
            if is_single_symbol_analysis:
                # 提取消息中的品种代码（6位韩股数字 / KRW-XXX / 字母美股 / 中文公司名→代码）
                _mentioned_syms = []
                # 6位数字韩股代码
                _mentioned_syms += re.findall(r'\b(\d{6})\b', user_message)
                # KRW-XXX 加密货币
                _mentioned_syms += re.findall(r'(KRW-[A-Z]+)', user_message.upper())
                # 美股 Ticker (2-5位大写字母)
                _mentioned_syms += [m for m in re.findall(r'\b([A-Z]{2,5})\b', user_message.upper())
                                     if m not in ('KRW', 'USD', 'ETH', 'BTC') and len(m) <= 5]
                # 中文公司名/币种名 → 代码（通过缓存查找）
                if not self.__class__._krx_cache_loaded:
                    await asyncio.to_thread(self.__class__._load_krx_name_map)
                _crypto_name_map2 = {
                    '比特币': 'KRW-BTC', '以太坊': 'KRW-ETH', '以太': 'KRW-ETH',
                    '瑞波': 'KRW-XRP', '狗狗币': 'KRW-DOGE', '索拉纳': 'KRW-SOL',
                    '莱特币': 'KRW-LTC', '艾达': 'KRW-ADA', '波卡': 'KRW-DOT',
                }
                for cn_name, code in _crypto_name_map2.items():
                    if cn_name in user_message:
                        _mentioned_syms.append(code)
                for krx_name, krx_code in self.__class__._krx_name_to_code.items():
                    if krx_name in user_message and krx_name not in ('시가', '고가', '저가'):
                        _mentioned_syms.append(krx_code)
                        break  # 只取第一个匹配，避免过多
                # 持仓中的品种也纳入（若用户问"我的持仓"类场景）
                if self.tracker and self.tracker.positions and any(k in user_message for k in ['持仓', '仓位', '我的股']):
                    _mentioned_syms += list(self.tracker.positions.keys())[:3]

                _mentioned_syms = list(dict.fromkeys(_mentioned_syms))  # 去重保序
                if _mentioned_syms:
                    try:
                        tech_context = await self._compute_technical_context(_mentioned_syms)
                        if tech_context:
                            context += tech_context
                            logger.info(f"📐 技术指标注入: {_mentioned_syms}")
                    except Exception as _te:
                        logger.warning(f"技术指标计算注入失败: {_te}")

            # 5c. 行情/价格查询：提前 force_live 查价，避免 LLM 读取批量缓存的整数近似值
            PRICE_QUERY_KWS = ['行情', '价格', '现价', '多少钱', '当前价', '涨幅', '跌幅', '今天多少']
            is_price_query = any(k in user_message for k in PRICE_QUERY_KWS)
            if is_price_query and self.crypto_fetcher:
                # 提取消息中裸字母 ticker（2-8位）及 KRW-XXX 格式
                _all_words = [s.upper() for s in re.findall(r'\b([A-Za-z]{2,8})\b', user_message)
                              if s.upper() not in ('KRW', 'USD', 'THE', 'KRX', 'DART')]
                _krw_syms  = re.findall(r'KRW-([A-Z]+)', user_message.upper())
                live_symbols = list(dict.fromkeys(_krw_syms + _all_words))[:6]

                if live_symbols:
                    live_lines = []
                    for sym in live_symbols:
                        krw_sym  = f'KRW-{sym}' if not sym.startswith('KRW-') else sym
                        bare_sym = sym.replace('KRW-', '')
                        info = await self._get_current_price(krw_sym, force_live=True)
                        if not info:
                            info = await self._get_current_price(bare_sym, force_live=True)
                        if info and info.get('price', 0) > 0:
                            chg = info.get('change_pct', info.get('change', 0))
                            live_lines.append(
                                f"{bare_sym}({krw_sym}): ₩{self._fmt_price(info['price'])}"
                                f"  24H涨跌{chg:+.2f}%  [{info.get('exchange','?')}实时]"
                            )
                    if live_lines:
                        from datetime import datetime as _dt_live
                        _live_ts = _dt_live.now().strftime('%H:%M:%S')
                        context += (
                            f'\n\n【实时精确价格（{_live_ts} 强制刷新，非缓存）】\n'
                            + '\n'.join(live_lines)
                            + '\n★ 以上是刚刚实时查询的最新精确价格，直接基于此价格回答用户，'
                              '禁止使用任何其他来源的价格数据（包括上文中的批量行情缓存）。'
                        )
                        logger.info(f'[price-query] 实时价格注入 context: {live_lines}')

            # 6. 构建提示词并调用 LLM（第一轮）
            prompt = self._build_llm_prompt(user_message, context)
            llm_text = await self.model_manager.generate_with_fallback(prompt, task_type=task_type)
            if not llm_text:
                return "❌ 所有AI模型配额已耗尽，请明天再试（每日配额UTC 0点重置）"

            logger.info(f"LLM第一轮回复: {llm_text[:120]}...")

            # 7. Tool-use 循环：只要 LLM 输出了 [QUERY_PRICE] 标签，都进行 round 2
            price_tag_pattern = re.compile(r'\[QUERY_PRICE\|([^\]]+)\]')
            has_price_tags = bool(price_tag_pattern.search(llm_text))

            if has_price_tags:
                # 7a. 查询 LLM 请求的所有价格
                price_lines_map, price_infos = await self._resolve_query_price_tags(llm_text)
                fetched_text = '\n'.join(price_lines_map.values())
                logger.info(f'Tool-use 查询价格: {list(price_lines_map.keys())}')

                # 7b. 把价格结果喂回 LLM，让它直接回答用户的原始问题（第二轮）
                round2_prompt = (
                    f"用户问：{user_message}\n\n"
                    f"系统已查询到以下实时价格：\n{fetched_text}\n\n"
                    "请基于以上真实价格，直接完整地回答用户的问题。"
                    "若用户问数量/计算，直接给出计算结果；若用户问推荐，给出推荐+目标价+止损。"
                    "纯文本，不要markdown，不要再输出任何[QUERY_PRICE]标签。"
                    "【格式规则】推荐多个品种时，每个品种单独一行，禁止用分号连接。"
                )
                llm_text2 = await self.model_manager.generate_with_fallback(round2_prompt, task_type=task_type)
                if llm_text2:
                    logger.info('Tool-use 第二轮回复生成成功')
                    return await self._execute_actions_if_needed(llm_text2, user_message)

            # 8. 常规流程：执行操作标签（买入/卖出/K线等）
            return await self._execute_actions_if_needed(llm_text, user_message)

        except Exception as e:
            logger.error(f"LLM处理失败: {e}")
            import traceback
            traceback.print_exc()
            return f"❌ AI处理失败: {str(e)}"

    async def _build_realtime_pnl_summary(self) -> str:
        """
        并发强制实时查询所有持仓价格，写回共享缓存后返回格式化盈亏快报。
        与告警循环、置顶摘要共享同一价格来源，确保三处数字一致。
        """
        if not self.tracker or not self.tracker.positions:
            return ""
        try:
            import time as _ti_pnl
            positions = dict(self.tracker.positions)
            # 强制实时查价（force_live=True），与告警循环一致
            price_results = await asyncio.gather(
                *[self._get_current_price(sym, force_live=True) for sym in positions],
                return_exceptions=True
            )
            price_map: dict = {}
            for sym, res in zip(positions, price_results):
                if isinstance(res, dict) and res.get('price', 0) > 0:
                    price_map[sym] = res

            from datetime import datetime as _dt
            ts = _dt.now().strftime('%H:%M')
            lines = [f"📊 当前持仓盈亏（{ts}）"]
            total_cost = 0.0
            total_value = 0.0

            for sym, pos in positions.items():
                entry  = pos['avg_entry_price']
                qty    = pos['quantity']
                cost   = pos.get('total_cost', entry * qty)
                pinfo  = price_map.get(sym)
                cur    = pinfo['price'] if pinfo else entry
                value  = cur * qty
                pnl    = value - cost
                pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0
                icon   = "🟢" if pnl >= 0 else "🔴"
                if sym.startswith('KRW-'):
                    qty_str = f"{qty:.4f}枚"
                else:
                    qty_str = f"{qty:.2f}股"

                # 获取目标/止损设置
                target_price = pos.get('profit_target_price', 0)
                stop_price   = pos.get('stop_loss_price', 0)
                
                # 构造基础行
                line1 = f"{icon} {sym}  {qty_str}  成本₩{self._fmt_price(entry)}"
                line2 = f"   当前₩{self._fmt_price(cur)}  盈亏₩{self._fmt_signed(pnl)}（{pnl_pct:+.2f}%）"
                
                # 构造目标展示行
                line3 = ""
                if target_price > 0:
                    dist_target = (target_price - cur) / cur * 100
                    line3 += f"\n   🎯 目标₩{self._fmt_price(target_price)} (距{dist_target:+.1f}%)"
                if stop_price > 0:
                    dist_stop = (stop_price - cur) / cur * 100
                    if line3: line3 += "  "
                    else: line3 += "\n   "
                    line3 += f"🛑 止损₩{self._fmt_price(stop_price)} (距{dist_stop:+.1f}%)"

                lines.append(f"{line1}\n{line2}{line3}")

                total_cost  += cost
                total_value += value

            total_pnl     = total_value - total_cost
            total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
            lines.append(
                f"───\n"
                f"💰 总持仓盈亏：₩{self._fmt_signed(total_pnl)}（{total_pnl_pct:+.2f}%）\n"
                f"💵 剩余现金：₩{self._fmt_price(self.tracker.cash)}"
            )
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"构建盈亏摘要失败: {e}")
            return ""

    async def _build_pinned_summary(self) -> str:
        """
        极简持仓概览，用于置顶消息（30秒刷新）。
        格式：
          +2.3% 持有10000ENSO ₩2024万 剩余：₩1325万
          持仓动态（22:44:06）
        多仓时持仓部分用 | 分隔，剩余资金放最后。
        """
        if not self.tracker or not self.tracker.positions:
            return ""
        try:
            from datetime import datetime as _dt
            positions = dict(self.tracker.positions)

            # 每次全量实时查价
            _fresh = await asyncio.gather(
                *[self._get_current_price(s, force_live=True) for s in positions],
                return_exceptions=True
            )
            _price_map = {}
            for s, r in zip(positions, _fresh):
                if isinstance(r, dict) and r.get('price', 0) > 0:
                    _price_map[s] = r['price']

            parts = []
            for sym, pos in positions.items():
                entry  = pos['avg_entry_price']
                qty    = pos['quantity']
                cur = _price_map.get(sym, entry)
                market_val = cur * qty
                pnl_pct = ((cur - entry) / entry * 100) if entry > 0 else 0.0
                short  = sym.replace('KRW-', '')
                val_wan = market_val / 10000
                pnl_str = f"{pnl_pct:+.2f}%"
                parts.append(f"{pnl_str} 持有{qty:g}{short} ₩{val_wan:.0f}万")
            cash_wan = self.tracker.cash / 10000
            ts = _dt.now().strftime('%H:%M:%S')
            positions_str = " | ".join(parts)
            return f"{positions_str} 剩余：₩{cash_wan:.0f}万\n持仓动态（{ts}）"
        except Exception as e:
            logger.debug(f"_build_pinned_summary 失败: {e}")
            return ""

    async def start_pnl_alert_loop(self, send_fn, interval: int = 5):
        """
        高频盈亏告警循环（每1秒扫描，按盈亏档位控制推送频率）：
          +1～+5%   : 3分钟一次
          +6～+10%  : 30秒一次
          +11～+15% : 10秒一次
          +15%+     : 1秒一次
          -0.5~-3%  : 3分钟一次
          -3.1%~-5% : 1分钟一次
          -10%+     : 1秒一次
        """
        import time as _ti
        logger.info("🔔 盈亏高频告警循环已启动（1秒扫描，分档位控频推送）")

        # 档位定义：(min_pct, max_pct, icon, desc, interval_sec)
        # 注意 max_pct 用 None 表示无上限/无下限
        TIERS = [
            # 盈利档（从高到低判断）
            ( 15.0,  None,  "💰", "+15%+ 重大盈利",    1),
            ( 11.0,  15.0,  "🚀", "+11%~15% 大幅盈利", 10),
            (  6.0,  11.0,  "🟢", "+6%~10% 盈利提示",  30),
            (  1.0,   6.0,  "📈", "+1%~5% 盈利提示",   180),
            # 亏损档（从深到浅判断）
            (None,  -10.0,  "🆘", "-10%+ 止损警告",    1),
            ( -5.0,  -3.1,  "🔴", "-3.1%~5% 亏损预警", 60),
            ( -3.0,  -0.5,  "⚠️", "-0.5%~3% 亏损提示", 180),
        ]

        def _get_tier(pnl_pct: float):
            for item in TIERS:
                lo, hi, icon, desc, ivl = item
                if lo is not None and hi is not None:
                    if lo <= pnl_pct < hi:
                        return icon, desc, ivl
                elif lo is not None and hi is None:
                    if pnl_pct >= lo:
                        return icon, desc, ivl
                elif lo is None and hi is not None:
                    if pnl_pct <= hi:
                        return icon, desc, ivl
            return None, None, None  # 正常区间不告警

        # {sym: last_sent_ts}
        _last_sent: dict = {}
        # {sym: (last_pnl_pct, timestamp)}，用于计算急速下跌
        _last_pnl_state: dict = {}
        # {sym: last_rapid_drop_alert_ts}，控制急速下跌告警频率（3秒/次）
        _last_rapid_alert: dict = {}
        
        # 默认5秒扫描；当任一仓位触达 ≥+15% 或 ≤-10% 极端档时降为1秒
        _high_freq: bool = False

        while True:
            # 如果处于急速下跌监控状态（有最近触发过下跌告警），也保持1秒扫描
            # 但这里简单起见，只要检测到急速下跌，下一轮自然会更快捕获
            await asyncio.sleep(1 if _high_freq else 5)
            _high_freq = False   # 每轮重置，扫描中若发现极端档位再置True
            
            try:
                if not self.tracker or not self.tracker.positions:
                    _last_sent.clear()
                    _last_pnl_state.clear()
                    continue
                
                positions = dict(self.tracker.positions)
                # 清理已平仓状态
                for sym in list(_last_pnl_state):
                    if sym not in positions:
                        del _last_pnl_state[sym]
                        if sym in _last_rapid_alert: del _last_rapid_alert[sym]

                price_results = await asyncio.gather(
                    *[self._get_current_price(sym, force_live=True) for sym in positions],
                    return_exceptions=True
                )
                
                from datetime import datetime as _dt
                import time as _ti2
                now_ts = _ti.time()

                for sym, res in zip(positions, price_results):
                    pos = positions[sym]
                    entry = pos['avg_entry_price']
                    qty   = pos['quantity']
                    
                    if isinstance(res, Exception) or not isinstance(res, dict):
                        continue
                        
                    cur = res.get('price', entry)
                    pnl_pct = ((cur - entry) / entry * 100) if entry > 0 else 0.0

                    # ── 急速下跌检测逻辑 (Start) ──
                    # 规则：如果两轮扫描间（约5秒或1秒），跌幅 > 0.8% (绝对值)，且当前总盈亏非大幅盈利
                    prev_pnl, prev_ts = _last_pnl_state.get(sym, (None, None))
                    
                    # 更新状态供下轮对比
                    _last_pnl_state[sym] = (pnl_pct, now_ts)
                    
                    if prev_pnl is not None:
                        delta = pnl_pct - prev_pnl
                        # 阈值：单次扫描下跌超过 0.8%
                        if delta < -0.8:
                            # [新增] 仅当上一次盈亏率 > 3% 或 < -2% 时才触发急速下跌告警
                            # 避免在 0% 附近微小波动频繁骚扰
                            if prev_pnl > 3.0 or prev_pnl < -2.0:
                                # 触发急速下跌预警
                                last_rapid = _last_rapid_alert.get(sym, 0)
                                # 3秒冷却
                                if now_ts - last_rapid >= 3:
                                    _last_rapid_alert[sym] = now_ts
                                    warning_msg = (
                                        f"📉 【急速下跌警报】 {sym.replace('KRW-', '')}\n"
                                        f"短时跌幅 {delta:.2f}% ({prev_pnl:.2f}% ➔ {pnl_pct:.2f}%)\n"
                                        f"现价 ₩{self._fmt_price(cur)}  持仓盈亏 {pnl_pct:+.2f}%"
                                    )
                                    await send_fn(warning_msg)
                                    logger.warning(f"📉 急速下跌推送 {sym}: {delta:.2f}% in {now_ts - prev_ts:.1f}s")
                                    
                                    # 既然发生了急速下跌，开启高频扫描模式以备后续追踪
                                    _high_freq = True
                                # 跳过常规档位检查，避免重复刷屏？或者继续？
                                # 继续吧，常规档位有自己的CD
                    # ── 急速下跌检测逻辑 (End) ──

                    icon, desc, ivl = _get_tier(pnl_pct)
                    if icon is None:
                        # 正常区间：重置计时器（下次进入告警区间立即触发）
                        _last_sent.pop(sym, None)
                        continue

                    # 极端档位（ivl==1）→ 下轮也用1秒扫描
                    if ivl == 1:
                        _high_freq = True

                    last = _last_sent.get(sym, 0)
                    if now_ts - last < ivl:
                        continue  # 还没到下次发送时间

                    _last_sent[sym] = now_ts
                    short   = sym.replace('KRW-', '')
                    val_wan = cur * qty / 10000
                    msg = (
                        f"【{desc}】{short}\n"
                        f"持{qty:g}枚  市值₩{val_wan:.0f}万    盈亏利润  {pnl_pct:+.2f}%\n"
                        f"买入价₩{self._fmt_price(entry)}       现价₩{self._fmt_price(cur)}"
                    )
                    await send_fn(msg)
                    logger.info(f"🔔 告警推送 {sym} pnl={pnl_pct:.2f}% 间隔={ivl}s")

                # 清理已平仓
                for sym in list(_last_sent):
                    if sym not in positions:
                        del _last_sent[sym]

            except Exception as e:
                logger.error(f"盈亏告警循环异常: {e}")

    async def start_position_monitor_loop(
        self,
        send_fn,          # async callable(text: str)
        interval: int = 300,   # 默认5分钟
    ):
        """
        持仓盈亏定时推送循环。
        如果持仓不为空，每隔 interval 秒自动推送一次盈亏快报。
        send_fn: 异步函数，接收一个 str 并发送到 Telegram。
        """
        logger.info(f"📡 持仓盈亏定时推送循环已启动（间隔 {interval//60} 分钟）")
        while True:
            await asyncio.sleep(interval)
            try:
                if self.tracker and (self.tracker.positions or self.tracker.closed_positions):
                    summary = await self._build_full_session_report(periodic=True)
                    if summary:
                        await send_fn(summary)
                        logger.info("定时盈亏快报已推送")
            except Exception as e:
                logger.error(f"定时盈亏推送失败: {e}")

    async def _build_full_session_report(self, periodic: bool = False) -> str:
        """
        完整盈亏报告：未实现持仓（实时价）+ 已实现平仓 + 总盈亏汇总。
        periodic=True 时为定时推送格式（省略无仓位的情况）。
        """
        if not self.tracker:
            return ""
        try:
            from datetime import datetime as _dt
            ts = _dt.now().strftime('%H:%M')
            lines = []

            # ── 一、未实现持仓 ──
            positions = dict(self.tracker.positions)
            total_unrealized = 0.0
            total_open_cost  = 0.0

            if positions:
                price_results = await asyncio.gather(
                    *[self._get_current_price(sym) for sym in positions],
                    return_exceptions=True
                )
                price_map = {
                    sym: (res if isinstance(res, dict) else None)
                    for sym, res in zip(positions, price_results)
                }
                lines.append(f"📊 持仓盈亏快报（{ts}）")
                lines.append("【未平仓】")
                for sym, pos in positions.items():
                    entry  = pos['avg_entry_price']
                    qty    = pos['quantity']
                    cost   = pos.get('total_cost', entry * qty)
                    pinfo  = price_map.get(sym)
                    cur    = pinfo['price'] if pinfo else entry
                    pnl    = cur * qty - cost
                    pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0
                    icon   = "🟢" if pnl >= 0 else "🔴"
                    qty_str = f"{qty:g}枚" if sym.startswith('KRW-') else f"{qty:g}股"
                    lines.append(
                        f"{icon} {sym}  {qty_str}  买入₩{self._fmt_price(entry)} → 现₩{self._fmt_price(cur)}\n"
                        f"   浮动盈亏 ₩{self._fmt_signed(pnl)}（{pnl_pct:+.2f}%）"
                    )
                    total_open_cost  += cost
                    total_unrealized += pnl
            elif not periodic:
                lines.append(f"📊 持仓盈亏报告（{ts}）")
                lines.append("【未平仓】暂无持仓")

            # ── 二、已实现平仓 ──
            closed = list(self.tracker.closed_positions) if self.tracker.closed_positions else []
            total_realized = sum(c.get('pnl', 0) for c in closed)
            if closed:
                lines.append("【已平仓】")
                for c in closed[-5:]:   # 最近5笔，避免过长
                    sym   = c.get('symbol', '?')
                    ep    = c.get('entry_price', 0)
                    xp    = c.get('exit_price', 0)
                    q     = c.get('quantity', 0)
                    pnl   = c.get('pnl', 0)
                    pp    = c.get('pnl_pct', 0)
                    icon  = "🟢" if pnl >= 0 else "🔴"
                    qty_str = f"{q:g}枚" if sym.startswith('KRW-') else f"{q:g}股"
                    lines.append(
                        f"{icon} {sym}  {qty_str}  买入₩{self._fmt_price(ep)} → 卖出₩{self._fmt_price(xp)}\n"
                        f"   已实现 ₩{self._fmt_signed(pnl)}（{pnl_pct:+.2f}%）"
                    )
                if len(closed) > 5:
                    lines.append(f"   …共 {len(closed)} 笔平仓记录")

            # ── 三、总计 ──
            grand_total = total_unrealized + total_realized
            lines.append("───")
            if positions:
                lines.append(f"📈 未实现盈亏：₩{self._fmt_signed(total_unrealized)}")
            if closed:
                lines.append(f"✅ 已实现盈亏：₩{self._fmt_signed(total_realized)}（{len(closed)}笔）")
            lines.append(f"💰 总盈亏合计：₩{self._fmt_signed(grand_total)}")
            lines.append(f"💵 当前现金：₩{self._fmt_price(self.tracker.cash)}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"_build_full_session_report 失败: {e}")
            return ""

    async def start_price_refresh_loop(self, interval_seconds: int = 3600):
        """
        后台价格刷新循环：每隔 interval_seconds 秒（默认1小时）
        并发拉取全量 KRX 股票 + Upbit/Bithumb 加密货币行情并写入类缓存。
        应作为 asyncio.create_task 在 bot 启动时调用。
        """
        logger.info(f'🔄 市场价格定时刷新任务已启动（间隔 {interval_seconds//60} 分钟）')
        while True:
            try:
                logger.info('⏰ 定时刷新：开始拉取全量 KRX 股票 + 加密货币价格...')
                stock_task  = asyncio.create_task(self._fetch_all_stock_prices_force())
                crypto_task = asyncio.create_task(self._fetch_all_crypto_prices_force())
                stock_result, crypto_result = await asyncio.gather(
                    stock_task, crypto_task, return_exceptions=True
                )
                stock_cnt  = len(stock_result)  if isinstance(stock_result,  dict) else 0
                crypto_cnt = len(crypto_result) if isinstance(crypto_result, dict) else 0
                logger.info(f'✅ 定时刷新完成：韩股 {stock_cnt} 只 / 加密货币 {crypto_cnt} 个')
            except Exception as e:
                logger.error(f'定时刷新失败: {e}')
            await asyncio.sleep(interval_seconds)

    async def _fetch_all_stock_prices_force(self) -> dict:
        """强制绕过缓存，直接拉取 KRX 全量行情并写入缓存。"""
        import time as _time
        cls = self.__class__
        from pykrx import stock as krx
        from datetime import datetime as _dt, timedelta as _td

        today = _dt.now().strftime('%Y%m%d')
        start = (_dt.now() - _td(days=5)).strftime('%Y%m%d')

        async def _fetch_market(market: str) -> dict:
            try:
                df = await asyncio.to_thread(
                    krx.get_market_price_change, start, today, market=market
                )
                if df is None or df.empty:
                    return {}
                result = {}
                for ticker, row in df.iterrows():
                    try:
                        result[ticker] = {
                            'name': str(row.get('종목명', ticker)),
                            'price': float(row['종가']),
                            'change_pct': float(row.get('등락률', 0)),
                            'volume_krw': float(row.get('거래대금', 0)),
                            'market': market,
                        }
                    except Exception:
                        continue
                return result
            except Exception as e:
                logger.warning(f'[force] pykrx {market} 失败: {e}')
                return {}

        kospi, kosdaq = await asyncio.gather(
            _fetch_market('KOSPI'), _fetch_market('KOSDAQ')
        )
        combined = {**kospi, **kosdaq}
        if combined:
            cls._stock_price_cache    = combined
            cls._stock_price_cache_ts = _time.time()
            logger.info(f'[force] KRX 缓存已更新: {len(combined)} 只')
        return combined

    async def _fetch_all_crypto_prices_force(self) -> dict:
        """强制绕过缓存，直接拉取 Upbit+Bithumb 全量行情并写入缓存。"""
        import time as _time
        cls = self.__class__
        combined: dict = {}

        async def _upbit():
            try:
                import pyupbit as _upbit_mod
                markets = await asyncio.to_thread(_upbit_mod.get_tickers, fiat='KRW')
                if not markets:
                    return {}
                raw = await asyncio.to_thread(_upbit_mod.get_current_price, markets)
                if not raw:
                    return {}
                return {
                    sym: {'price': float(price), 'change_pct': 0.0, 'volume': 0, 'exchange': 'upbit'}
                    for sym, price in raw.items() if price is not None
                }
            except Exception as e:
                logger.warning(f'[force] Upbit 失败: {e}')
                return {}

        async def _bithumb():
            try:
                import pybithumb as _bithumb_mod
                raw = await asyncio.to_thread(_bithumb_mod.get_current_price, 'ALL')
                if not isinstance(raw, dict):
                    return {}
                result = {}
                for coin, data in raw.items():
                    if coin == 'date':
                        continue
                    try:
                        price = float(data.get('closing_price', 0))
                        prev  = float(data.get('prev_closing_price', price) or price)
                        chg   = ((price - prev) / prev * 100) if prev else 0.0
                        vol   = float(data.get('acc_trade_value_24H', 0) or 0)
                        result[f'KRW-{coin}'] = {
                            'price': price, 'change_pct': round(chg, 2),
                            'volume': vol, 'exchange': 'bithumb',
                        }
                    except Exception:
                        continue
                return result
            except Exception as e:
                logger.warning(f'[force] Bithumb 失败: {e}')
                return {}

        upbit_data, bithumb_data = await asyncio.gather(_upbit(), _bithumb())
        combined.update(bithumb_data)
        for sym, info in upbit_data.items():
            if sym in combined:
                combined[sym]['price']    = info['price']
                combined[sym]['exchange'] = 'upbit+bithumb'
            else:
                combined[sym] = info

        if combined:
            cls._crypto_price_cache    = combined
            cls._crypto_price_cache_ts = _time.time()
            logger.info(f'[force] 加密货币缓存已更新: {len(combined)} 个')
        return combined


    # 行情数据 TTL 缓存（1.5小时，配合每小时自动刷新后台任务）
    _stock_price_cache: dict = {}           # {ticker: info}
    _stock_price_cache_ts: float = 0.0     # 上次拉取时间（time.time()）
    _crypto_price_cache: dict = {}
    _crypto_price_cache_ts: float = 0.0
    _MARKET_CACHE_TTL: int = 90 * 60        # 1.5小时（秒），配合1小时刷新任务

    # 告警循环写入的最新持仓实时价缓存（5秒有效），供置顶摘要复用，保证二者价格一致
    _live_pos_price_cache: dict = {}        # {symbol: {'price': float, 'ts': float}}
    _LIVE_POS_CACHE_TTL: float = 5.0        # 秒

    # 新闻头条缓存（30分钟，供打分引擎情绪分析使用）
    _news_headlines_cache: list = []        # [headline_text_lower, ...]
    _news_headlines_cache_ts: float = 0.0
    _NEWS_CACHE_TTL: int = 60 * 60          # 1小时（新闻按48小时窗口筛选，缓存可适当延长）

    # pykrx 公司名→KRX代码缓存（懒加载）
    _krx_name_to_code: dict = {}
    _krx_cache_loaded: bool = False

    async def _fetch_recent_news_headlines(self) -> list:
        """
        从100+全球新闻源中拉取关键RSS订阅，返回最近新闻标题列表（小写）。
        结果缓存30分钟，供打分引擎各候选品种情绪分析复用。
        优先选取韩国金融、全球加密货币、国际财经等最相关的RSS源。
        """
        import time as _t
        cls = self.__class__
        if cls._news_headlines_cache and (_t.time() - cls._news_headlines_cache_ts) < cls._NEWS_CACHE_TTL:
            return cls._news_headlines_cache

        # 7大洲全覆盖 RSS 源：政治/财经/娱乐/体育/科技/加密（共80+源，并发拉取）
        RSS_FEEDS = [
            # ══ 亚洲 · 韩国 ══
            "https://www.hankyung.com/rss/finance",          # 한국경제 금융
            "https://www.hankyung.com/rss/all",              # 한국경제 전체
            "https://www.mk.co.kr/rss/30100041/",            # 매일경제 주식
            "https://www.mk.co.kr/rss/50200011/",            # 매일경제 정치
            "https://www.yna.co.kr/rss/economy.xml",         # 연합뉴스 경제
            "https://www.yna.co.kr/rss/politics.xml",        # 연합뉴스 정치
            "https://www.yna.co.kr/rss/sports.xml",          # 연합뉴스 스포츠
            "https://www.yna.co.kr/rss/entertainment.xml",   # 연합뉴스 연예
            "https://biz.chosun.com/rss/stock.xml",          # 조선비즈 주식
            "https://news.naver.com/main/rss/rss.naver?mode=LSD&mid=shm&sid1=101",  # 네이버 경제
            "https://news.naver.com/main/rss/rss.naver?mode=LSD&mid=shm&sid1=100",  # 네이버 정치
            "https://sports.news.naver.com/rss/sports.naver",                        # 네이버 스포츠

            # ══ 亚洲 · 日本 ══
            "https://jp.reuters.com/arc/outboundfeeds/rss/japanBusinessNews/",
            "https://www3.nhk.or.jp/rss/news/cat6.xml",     # NHK 경제
            "https://www3.nhk.or.jp/rss/news/cat4.xml",     # NHK 정치
            "https://www3.nhk.or.jp/rss/news/cat7.xml",     # NHK 스포츠

            # ══ 亚洲 · 中国 ══
            "http://rss.sina.com.cn/finance/stocks/main.xml",
            "http://rss.sina.com.cn/news/china/politics.xml",
            "http://rss.sina.com.cn/sports/global/globalrollnews.xml",
            "http://rss.sina.com.cn/ent/ent.xml",

            # ══ 亚洲 · 印度 ══
            "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
            "https://economictimes.indiatimes.com/news/politics-and-nation/rssfeeds/1052732854.cms",
            "https://www.moneycontrol.com/rss/marketreports.xml",
            "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",

            # ══ 亚洲 · 东南亚/香港/新加坡 ══
            "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511",  # CNA business
            "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=10416", # CNA world
            "https://www.scmp.com/rss/2/feed",               # SCMP business
            "https://www.scmp.com/rss/4/feed",               # SCMP sport
            "https://www.businesstimes.com.sg/rss-feeds/companies-markets",

            # ══ 亚洲 · 中东 ══
            "https://www.arabnews.com/rss.xml",
            "https://gulfnews.com/rss",
            "https://www.aljazeera.com/xml/rss/all.xml",

            # ══ 欧洲 · 英国 ══
            "https://feeds.bbci.co.uk/news/rss.xml",          # BBC 全球
            "https://feeds.bbci.co.uk/news/business/rss.xml", # BBC business
            "https://feeds.bbci.co.uk/news/politics/rss.xml", # BBC politics
            "https://feeds.bbci.co.uk/sport/rss.xml",         # BBC sport
            "https://www.theguardian.com/world/rss",
            "https://www.theguardian.com/business/rss",
            "https://www.theguardian.com/sport/rss",
            "https://www.ft.com/markets?format=rss",
            "https://www.independent.co.uk/rss",

            # ══ 欧洲 · 德国/法国/欧陆 ══
            "https://www.spiegel.de/schlagzeilen/index.rss",
            "https://www.spiegel.de/wirtschaft/index.rss",
            "https://www.handelsblatt.com/contentexport/feed/finanzen",
            "https://www.euronews.com/rss?level=theme&name=news",
            "https://www.euronews.com/rss?level=theme&name=business",

            # ══ 欧洲 · 俄罗斯/东欧 ══
            "https://tass.com/rss/v2.xml",
            "https://rt.com/rss/",

            # ══ 北美 · 美国 综合 ══
            "https://feeds.reuters.com/reuters/topNews",
            "https://feeds.reuters.com/reuters/businessNews",
            "https://feeds.reuters.com/reuters/technologyNews",
            "https://feeds.reuters.com/reuters/sportsNews",
            "https://feeds.reuters.com/reuters/entertainment",
            "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml",
            "https://www.cnbc.com/id/10001147/device/rss/rss.html",  # CNBC markets
            "https://www.cnbc.com/id/10000664/device/rss/rss.html",  # CNBC world
            "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",          # WSJ markets
            "https://feeds.bloomberg.com/markets/news.rss",
            "http://feeds.marketwatch.com/marketwatch/topstories/",
            "https://finance.yahoo.com/news/rssindex",
            "https://www.benzinga.com/feed",

            # ══ 北美 · 加密货币 ══
            "https://cointelegraph.com/rss",
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://bitcoinmagazine.com/.rss/full/",
            "https://www.theblock.co/rss.xml",
            "https://decrypt.co/feed",

            # ══ 北美 · 加拿大 ══
            "https://financialpost.com/category/news/feed/",
            "https://globalnews.ca/feed/",

            # ══ 南美 ══
            "https://www.infomoney.com.br/feed/",            # 巴西 finance
            "https://valor.globo.com/rss/financas/",         # 巴西 economia
            "https://www.ambito.com/finanzas/rss/",          # 阿根廷

            # ══ 非洲 ══
            "https://www.moneyweb.co.za/feed/",              # 南非 finance
            "https://www.businesslive.co.za/bd/rss/",        # 南非 business
            "https://businessday.ng/feed/",                  # 尼日利亚
            "https://www.theeastafrican.co.ke/tea/rss",      # 东非

            # ══ 大洋洲 ══
            "https://www.abc.net.au/news/feed/51120/rss.xml",  # ABC Australia business
            "https://www.abc.net.au/news/feed/2942460/rss.xml",# ABC Australia politics
            "https://www.afr.com/rss/markets",                  # 澳洲 AFR markets
            "https://www.nzherald.co.nz/arc/outboundfeeds/rss/section/business/", # 新西兰

            # ══ Reddit 公开 RSS（无需 API Key）══
            "https://www.reddit.com/r/CryptoCurrency/new.rss",
            "https://www.reddit.com/r/Bitcoin/new.rss",
            "https://www.reddit.com/r/ethereum/new.rss",
            "https://www.reddit.com/r/solana/new.rss",
            "https://www.reddit.com/r/altcoin/new.rss",
            "https://www.reddit.com/r/investing/new.rss",
            "https://www.reddit.com/r/stocks/new.rss",
            "https://www.reddit.com/r/wallstreetbets/new.rss",
            "https://www.reddit.com/r/binance/new.rss",
            "https://www.reddit.com/r/korea/new.rss",
            "https://www.reddit.com/r/CryptoMarkets/new.rss",
            "https://www.reddit.com/r/defi/new.rss",
        ]

        headlines = []
        try:
            import feedparser as _fp

            # 限制并发数，避免网络过载
            _sem = asyncio.Semaphore(20)

            async def _fetch_one(url: str):
                async with _sem:
                    try:
                        feed = await asyncio.wait_for(
                            asyncio.to_thread(_fp.parse, url), timeout=8
                        )
                        import time as _tf
                        _cutoff = _tf.time() - 48 * 3600  # 只保留48小时内的新闻
                        for entry in (feed.entries or [])[:30]:  # 每源最多取30条
                            # 过滤发布时间（48小时内）
                            _pub = entry.get('published_parsed') or entry.get('updated_parsed')
                            if _pub:
                                import calendar
                                _pub_ts = calendar.timegm(_pub)
                                if _pub_ts < _cutoff:
                                    continue  # 超过48小时，跳过
                            title   = entry.get('title', '')
                            summary = entry.get('summary', '')
                            combined = (title + ' ' + summary).lower()
                            if combined.strip():
                                headlines.append(combined)
                    except Exception:
                        pass

            await asyncio.gather(*[_fetch_one(u) for u in RSS_FEEDS], return_exceptions=True)
            logger.info(f"📰 新闻头条已拉取: {len(headlines)} 条（来自 {len(RSS_FEEDS)} 个RSS源，7大洲，过去48小时）")
        except Exception as e:
            logger.warning(f"新闻头条拉取失败: {e}")


        cls._news_headlines_cache = headlines
        cls._news_headlines_cache_ts = _t.time()
        return headlines

    @classmethod
    def _load_krx_name_map(cls):
        """懒加载 pykrx 全市场公司名→6位代码映射"""
        if cls._krx_cache_loaded:
            return
        try:
            from pykrx import stock as krx_stock
            tickers = krx_stock.get_market_ticker_list(market='ALL')
            for t in tickers:
                name = krx_stock.get_market_ticker_name(t)
                if name:
                    cls._krx_name_to_code[name] = t
            cls._krx_cache_loaded = True
            logger.info(f"📋 KRX名称映射加载完成: {len(cls._krx_name_to_code)}家公司")
        except Exception as e:
            logger.warning(f"KRX名称映射加载失败: {e}")
            cls._krx_cache_loaded = True  # 避免重复尝试

    async def _fetch_relevant_announcements(self, user_message: str) -> str:
        """获取与当前消息/持仓相关的DART公告，作为交易信号注入LLM上下文"""
        if not self.announcement_monitor:
            return ""
        
        try:
            # 收集需要查询的股票代码
            # 1. 用户消息中的韩股代码
            mentioned_codes = re.findall(r'\b(\d{6})\b', user_message)
            
            # 2. 当前持仓中的韩股
            held_codes = []
            if self.tracker and self.tracker.positions:
                for symbol in self.tracker.positions.keys():
                    if symbol.isdigit() and len(symbol) == 6:
                        held_codes.append(symbol)
            
            # 3. 获取今日重要公告（始终获取，用于推荐场景）
            is_advice_query = any(kw in user_message for kw in [
                '建议', '推荐', '分析', '看法', '买什么', '机会', '公告', '消息',
                '利好', '利空', 'advice', '추천', '공시'
            ])
            
            # 无持仓且非建议类问题则跳过（节省API配额）
            if not mentioned_codes and not held_codes and not is_advice_query:
                return ""
            
            # 获取今日公告
            announcements = await self.announcement_monitor.monitor_announcements()

            if not announcements:
                return ""

            # 懒加载 KRX 公司名→代码映射
            await asyncio.to_thread(self._load_krx_name_map)

            def _find_krx_code(corp_name: str) -> str:
                """从公司名找6位KRX代码"""
                # 精确匹配
                if corp_name in self._krx_name_to_code:
                    return self._krx_name_to_code[corp_name]
                # 前缀匹配（如 '현대리바트' → '현대리바트주식회사'）
                for name, code in self._krx_name_to_code.items():
                    if corp_name in name or name in corp_name:
                        return code
                return ""

            # 按相关性过滤和排序
            relevant = []
            other_important = []
            
            for ann in announcements:
                corp_code = ann.get('corp_code', '')
                corp_name = ann.get('corp_name', '')
                
                # 检查是否与用户提及或持仓股票相关
                is_related = (
                    corp_code in mentioned_codes or
                    corp_code in held_codes or
                    any(code in corp_name for code in mentioned_codes)
                )
                
                if is_related:
                    relevant.append(ann)
                else:
                    other_important.append(ann)
            
            # 构建DART上下文
            dart_lines = []
            dart_lines.append("\n\n【DART公告信号（今日）】")
            
            if relevant:
                dart_lines.append("⚡ 持仓/关注股票相关公告：")
                for ann in relevant[:5]:
                    krx = _find_krx_code(ann['corp_name'])
                    code_str = f" KRX:{krx}" if krx else ""
                    dart_lines.append(
                        f"  • {ann['corp_name']}{code_str}: "
                        f"{ann['report_name']} ({ann['receive_date']})"
                    )

            if is_advice_query and other_important:
                dart_lines.append("📋 其他重要公告（可参考选股）：")
                for ann in other_important[:5]:
                    krx = _find_krx_code(ann['corp_name'])
                    code_str = f" KRX:{krx}" if krx else ""
                    dart_lines.append(
                        f"  • {ann['corp_name']}{code_str}: {ann['report_name']} ({ann['receive_date']})"
                    )
            
            if len(dart_lines) <= 1:  # 只有标题行
                return ""
            
            dart_lines.append("（公告来源：韩国金融监督院DART，可参考判断潜在利好/利空）")
            
            result = "\n".join(dart_lines)
            logger.info(f"📢 DART上下文注入: {len(relevant)}条相关, {len(other_important)}条其他重要")
            return result
            
        except Exception as e:
            logger.warning(f"DART公告获取失败（不影响主流程）: {e}")
            return ""

    def _build_system_context(self) -> str:
        """构建系统上下文信息"""
        context_parts = []
        
        # 1. 当前时间
        context_parts.append(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 2. 账户信息
        if self.tracker:
            context_parts.append(f"\n【账户真实数据，禁止修改】可用现金: ₩{self._fmt_price(self.tracker.cash)}（此为实际值，如为0则账户确实为空，禁止自行假设其他金额）")
            context_parts.append(f"初始资金: ₩{self._fmt_price(self.tracker.initial_capital)}")
            
            # 3. 持仓信息
            if self.tracker.positions:
                context_parts.append("\n当前持仓:")
                # 懒加载 pykrx 名称映射（用于显示韩股名称）
                if not self.__class__._krx_cache_loaded:
                    try:
                        import asyncio as _asyncio
                        import threading
                        # 在同步上下文里同步调用（构建context时非async）
                        self.__class__._load_krx_name_map()
                    except Exception:
                        pass
                # 构建反向映射: code → name
                _code_to_name = {v: k for k, v in self.__class__._krx_name_to_code.items()}

                for symbol, pos in self.tracker.positions.items():
                    current_value = pos['quantity'] * pos['avg_entry_price']
                    pnl = current_value - pos['total_cost']
                    pnl_pct = (pnl / pos['total_cost'] * 100) if pos['total_cost'] > 0 else 0

                    # 韩股显示公司名
                    display = symbol
                    if symbol.isdigit() and len(symbol) == 6:
                        display = f"{_code_to_name.get(symbol, symbol)}({symbol})"

                    context_parts.append(
                        f"  - {display}: {pos['quantity']} 股/枚 @ ₩{self._fmt_price(pos['avg_entry_price'])} "
                        f"(成本: ₩{self._fmt_price(pos['total_cost'])}, 盈亏: {pnl_pct:+.2f}%)"
                    )
            else:
                context_parts.append("\n当前持仓: 无")
        else:
            context_parts.append("\n账户状态: 未初始化")
        
        # 4. 对话历史（最近3条）
        if self.conversation_history:
            recent = self.conversation_history[-6:]  # 最近3轮对话（6条消息）
            if recent:
                context_parts.append("\n最近对话:")
                for item in recent:
                    role = "用户" if item['type'] == 'user' else "助手"
                    msg = item['message'][:80] + "..." if len(item['message']) > 80 else item['message']
                    context_parts.append(f"  {role}: {msg}")
        
        return "\n".join(context_parts)
    
    def _classify_task_type(self, user_message: str, has_dart: bool) -> str:
        """
        根据消息内容判断任务复杂度，路由到对应模型：
          lightweight → gemini-2.0-flash-lite （简单问候/查价/查持仓）
          standard    → gemini-2.0-flash      （买卖操作/一般分析）
          complex     → gemini-2.5-flash      （深度研判/DART+多维分析）
        """
        msg = user_message.strip()

        # 纯查账/查持仓/查盈亏 → lightweight（不涉及买卖，最简单）
        account_query_patterns = [
            '账户资金', '账户余额', '资金余额', '现金余额', '剩余资金',
            '初始资金', '账户', '余额', '现金', '资金',
            '持仓', '仓位', '我的持仓', '当前持仓',
            '盈亏', '浮动盈亏', '盈利', '亏损',
        ]
        # 简单问候/闲聊 → lightweight
        simple_patterns = [
            '你好', '早', '晚', '谢谢', '感谢', 'hi', 'hello', '帮助', '功能',
            '怎么用', '使用说明', '介绍一下'
        ]
        # 快速操作（查价/买卖）→ standard（需要理解意图但不需要深度推理）
        operation_patterns = [
            '买入', '卖出', '平仓', '价格', '多少钱', '现价', '行情',
            '买', '卖'
        ]
        # 深度分析 → complex（DART联动/市场分析/策略建议）
        complex_patterns = [
            '推荐', '建议', '分析', '策略', '研判', '怎么看', '前景', '机会',
            '风险', '值不值得', '应该买', '应该卖', '涨还是跌', '走势',
            '公告', 'DART', '利好', '利空', '深度'
        ]

        if any(kw in msg for kw in complex_patterns) or has_dart:
            task = 'complex'
        elif any(kw in msg for kw in operation_patterns):
            task = 'standard'
        elif any(kw in msg for kw in account_query_patterns) or any(kw in msg for kw in simple_patterns):
            task = 'lightweight'
        else:
            task = 'standard'

        logger.info(f"🧠 消息复杂度: {task} | '{msg[:30]}'")
        return task

    def _build_llm_prompt(self, user_message: str, context: str) -> str:
        """构建LLM提示词"""
        
        # 添加系统能力说明
        capabilities = []
        if self.crypto_fetcher:
            capabilities.append("✅ 实时加密货币价格获取（Upbit/Bithumb）")
        if self.us_hk_fetcher:
            capabilities.append("✅ 美股/港股实时数据（美股用Finnhub，港股用yfinance）")
        if self.announcement_monitor:
            capabilities.append("✅ DART公告监控（韩国上市公司重大事项）")
        
        capabilities_text = "\n".join(capabilities) if capabilities else "⚠️ 仅基础功能"
        
        prompt = f"""你是安诚科技 Ancent AI 交易助手。简洁、专业地回答用户问题。

【系统状态】
{context}

【能力】实时价格查询、自动买卖、风险监控、DART公告监控
{capabilities_text}

【交易分析原则】
如果上下文中包含【DART公告信号】，请将其纳入交易建议：
- 업무합병/인수（合并收购）→ 利好，可考虑买入
- 배당（配息）→ 短期利好
- 증자（增资发行）→ 一般利空（股权稀释）
- 감자（减资）→ 重大利空
- 거래정지（停牌）→ 谨慎，等待恢复
- 실적（业绩）공시 → 需结合具体内容判断
- 조회공시（查询公示）→ 关注异常波动信号

基于DART公告给推荐时，必须：
1. 先用 [QUERY_PRICE|KRX代码] 获取实时价格（用公告中的 KRX:XXXXXX 字段）
2. 说明公告类型对股价的具体影响
3. 给出明确的建议买入价、目标价（+X%）、止损价（-X%）
4. 禁止只给公司名和模糊理由

【技术指标解读规则】
如果上下文中包含【技术指标深度分析（AdvancedIndicatorMonitor 实时计算）】，请严格基于这些实时计算的指标进行分析，不要凭感觉给出与指标相矛盾的结论：

▸ RSI 解读：
  - RSI < 30 → 超卖区，反弹概率高，可考虑买入
  - RSI 30-50 → 偏弱，谨慎买入
  - RSI 50-70 → 健康上升，趋势看涨
  - RSI > 70 → 超买区，注意回调风险，考虑减仓

▸ MACD 解读：
  - 金叉（BULLISH_CROSS）→ 动能转强，买入信号
  - 死叉（BEARISH_CROSS）→ 动能转弱，卖出信号
  - 看涨（BULLISH）→ 正处上升通道
  - 看跌（BEARISH）→ 正处下降通道

▸ EMA 排列解读：
  - 多头排列（EMA5>EMA10>EMA20>EMA50）→ 强势上涨格局，趋势追多
  - 空头排列 → 下跌趋势，观望或减仓
  - ADX > 25 → 趋势强劲（配合多/空头排列判断方向）

▸ 成交量解读：
  - 成交量 ≥ 2x 均量 → 异常放量，结合价格方向判断突破或出货
  - 成交量萎缩 + 价格横盘 → 蓄势，等待方向选择
  - 量价背离（BEARISH）→ 价涨量跌，小心顶部

▸ 资金流解读：
  - MFI > 80 → 超买，谨慎
  - MFI < 20 → 超卖，关注反弹
  - CMF > 0.1 → 资金净流入，看涨
  - CMF < -0.1 → 资金净流出，看跌
  - OBV 持续上升 → 机构持续建仓

▸ 布林带（Bollinger Bands）解读：
  - 布林带收窄（Squeeze）+ 突破向上 → 强烈买入信号
  - 布林带收窄 + 突破向下 → 做空信号（警惕下跌加速）
  - 待突破（PENDING）→ 保持关注，方向未明

▸ 市场状态综合解读：
  - BREAKOUT（突破）→ 最强信号，顺势买入/卖出
  - TRENDING（趋势）→ 按趋势方向操作，不逆势
  - RANGING（震荡）→ 高抛低吸，控制仓位
  - VOLATILE（高波动）→ 控制仓位，设置严格止损

▸ 综合判断原则：
  买入信号数量 > 卖出信号数量 + 1 → 建议买入
  卖出信号数量 > 买入信号数量 + 1 → 建议卖出
  信号拉锯 → 建议持有观望
  必须给出基于指标计算的目标价和止损价。
  【盈利目标设定】：
    - 稳健倾向：目标涨幅设定为 +40%
    - 高盈利倾向：目标涨幅设定为 +60%
    - 止损：统一设定为 -10%（ATR×1 作为参考但不低于-10%硬线）
  若分析任何已持仓品种（在【我的持仓】列表中），且当前收益已达到上述目标（+40%或+60%），
  必须明确建议：「🚀 已达盈利目标，建议立即止盈卖出锁定利润」。

【重要规则】
1. 回答必须简短，禁止使用markdown格式（**、#、-等符号），只用纯文本和emoji
2. 【格式规则】推荐多个品种时，每个品种必须单独一行，禁止用分号或顿号连接在同一行。格式：
   品种名(代码): ₩价格  理由  目标₩XXX (+X%)  止损₩XXX (-X%)
   每个品种之间空一行。
3. 金额用₩显示，添加千位分隔符
4. 绝对禁止反问或征询确认：不能说"需要为您查询吗"、"需要帮您..."、"要查询吗"等，直接执行操作
5. 用户要推荐时，直接用 [QUERY_PRICE|代码] 查价再给出结论，不要问用户需不需要
6. 推荐加密货币时：若上下文已有【当前加密货币实时价格】板块，直接用这些价格给出推荐理由+目标价+止损价，不要再输出[QUERY_PRICE]标签；若没有价格则用[QUERY_PRICE|KRW-BTC]等查询后再分析
7. 股票代码识别：系统已加载全量KRX数据库（KOSPI+KOSDAQ共约2700只），任何韩国上市公司名称都能自动转换为6位代码。美股直接用Ticker（TSLA/AAPL/NVDA等）。若上下文中已有【KRX全量股票实时行情】或【实时加密货币价格】，直接基于这些数据分析，无需输出[QUERY_PRICE]。
8. 【推荐场景歧义消解 - 严格遵守】
   ▸ 含"币子/币/虚拟货币/加密货币/炒币/囤币/币圈/代币"且无"股票/韩股"→ 只推荐加密货币，禁止推荐韩国股票
   ▸ 含"股票/韩股/KOSPI/KOSDAQ/上市公司"→ 只推荐韩股，禁止推荐加密货币
   ▸ 仅含"推荐/投资建议"等通用词且未指定市场→ 分别推荐加密货币2个+韩股2个，用「📈 加密货币推荐」和「🏢 韩股推荐」分段
8. 金额识别："2000美元" → USD×1300转KRW，"200000韩币" → 直接用，纯数字 → 默认KRW
9. 【绝对禁止】输出任何占位语或虚假进度消息，例如：
   「正在获取…」「稍后提供…」「请稍等…」「马上为您查询…」「即将分析…」
   系统会在你输出[QUERY_PRICE|X]或[GET_PRICE_AND_BUY|X|Y]标签后立即自动执行并返回结果。
   你只需输出行动标记+分析结论，绝不能假装自己在fetch数据或承诺稍后给结果。
10. 若上下文已注入【KRX股票实时行情】或【两大交易所全量加密货币实时行情】，
    必须直接基于这些真实数据分析推荐，禁止再输出任何[QUERY_PRICE]标签。
    若上下文同时有股票和加密货币数据，优先按用户意图（或两者都推荐）。
11. 【数据时效性要求】所有价格引用必须来自上下文中「采集时间」字段标注的数据。
    上下文数据有效期为5小时。若上下文中没有价格数据（未注入行情），
    则用[QUERY_PRICE|代码]实时查询，绝不允许凭记忆或训练数据捏造任何历史价格。
    分析结论中必须注明价格来源时间，例如「基于 HH:MM 行情数据」。
12. 【推荐必须基于量化打分】若上下文中包含【量化打分排行（多维度综合评分，供LLM深度研判）】，
    则所有推荐品种必须从该排行榜中产生（按综合分从高到低选取），禁止推荐排行榜以外的品种，
    禁止无视打分结果而自行决定推荐对象。推荐时必须在理由中引用该品种的综合分与评分维度亮点
    （如「综合分XX分，动量+8.5 / MACD金叉 / 新闻利好12条」），让用户知道推荐有据可查。

【用户问题】
{user_message}

【回复格式】
【⚠️ 严格区分"计算询问"和"买入指令"】
以下属于"计算询问"，只做计算回答，绝对禁止输出任何买入标签：
- "能买几个/多少个/多少股"
- "X元能买多少"
- "按实时价格计算..."
- "大概能买"、"可以买多少"、"买得起多少"
- "帮我算一下"、"计算..."
- 所有含"能买"、"可以买"、"买多少"但未明确说"买入"/"帮我买"/"购买"的句子
→ 对这类问题：查询实时价格后直接给出数量计算结果，不输出任何操作标签。

以下才是"买入指令"，才输出买入标签：
- "买入X元的..."
- "帮我买..."
- "购买..."
- "买X个..."（直接陈述操作，非疑问句）

买入/卖出请求必须转换为操作标记：
- 用户说"买入200000韩币的三星电子" → [GET_PRICE_AND_BUY|005930|200000]
- 用户说"买入2000美元的特斯拉" → [GET_PRICE_AND_BUY|TSLA|2600000]（假设汇率1USD=1300KRW）
- 用户说"买入0.01个比特币价格60000000" → [ACTION:BUY|KRW-BTC|0.01|60000000]
- 用户说"EPT单价3韩币 买入700万个" → [ACTION:BUY|KRW-EPT|7000000|3]
- 用户说"以均价XX买入YY股/个/枚 某资产" → [ACTION:BUY|代码|数量|用户给定价格]
- 【重要】只要用户给定了「单价」/「均价」/「价格」/「价位」→ 必须用[ACTION:BUY|代码|数量|给定价格]，禁止实时查价
- 只有用户仅给出总金额、未指定价格时 → 才用[GET_PRICE_AND_BUY|代码|总金额KRW]
- 用户说"卖出/平仓 X股 某股票" → [ACTION:SELL|代码|数量]（不指定价格时系统自动获取实时价）
- 用户说"以2韩币卖出700万个EPT" → [ACTION:SELL|KRW-EPT|7000000|2]（指定价格时填第4字段）
- 【重要】用户卖出时若指定了价格 → [ACTION:SELL|代码|数量|给定价格]；未指定价格 → [ACTION:SELL|代码|数量]
- 用户说"全部平仓" → 对持仓中每个仓位各输出一行 [ACTION:SELL|代码|持仓数量]
- 价格查询 → [QUERY_PRICE|代码]
- K线+交易量+资金流向 → [QUERY_KLINE|代码]（韩股6位数字代码用pykrx；美股用TSLA/AAPL/NVDA等，美股仅含当日OHLC，无历史K线）
- 监控状态 → [CHECK_MONITORING_STATUS]
- 查询公告 → [QUERY_ANNOUNCEMENTS|公司名称或代码]（可选参数）
- 调整总资产/现金 → [ACTION:ADJUST_TOTAL_ASSET|金额]（纯数字，单位韩元）

回复示例（简短纯文本）：
✅ 已买入 三星电子 2.66股 @ ₩75,000
   总金额：₩200,000
   剩余资金：₩8,000,000

请回复："""
        
        return prompt
    
    async def _execute_actions_if_needed(self, llm_response: str, user_message: str) -> str:
        """检查LLM回复中是否包含需要执行的操作"""

        # ★ 计算询问保护：如果用户问的是"能买几个/多少个"等计算问题，
        #   即使 LLM 误输出了买入标签，也强制剥离，只保留文字回答。
        _CALC_QUERY_KWS = ['能买几个', '能买多少', '可以买几个', '可以买多少',
                           '买多少个', '买几个', '买多少枚', '买几枚',
                           '买多少股', '买几股', '按实时价格计算', '帮我算',
                           '计算一下', '大概能买', '买得起多少', '买得了多少']
        _EXPLICIT_BUY_KWS = ['买入', '帮我买', '购买', '下单']
        _is_calc_query = (
            any(k in user_message for k in _CALC_QUERY_KWS)
            and not any(k in user_message for k in _EXPLICIT_BUY_KWS)
        )
        if _is_calc_query:
            # 剥离所有买入操作标签，只保留文字
            llm_response = re.sub(r'\[GET_PRICE_AND_BUY\|[^\]]+\]', '', llm_response)
            llm_response = re.sub(r'\[ACTION:BUY\|[^\]]+\]', '', llm_response).strip()
            logger.info(f'[calc-guard] 计算询问，已剥离买入标签: "{user_message[:40]}"')

        clean_response = llm_response
        
        # 0a. 处理总资产调整 [ACTION:ADJUST_TOTAL_ASSET|金额]
        adjust_pattern = r'\[ACTION:ADJUST_TOTAL_ASSET\|(\d+(?:\.\d+)?)\]'
        adjust_matches = re.findall(adjust_pattern, llm_response)
        if adjust_matches and self.tracker:
            for amount_str in adjust_matches:
                try:
                    new_total = float(amount_str)
                    # 计算当前持仓成本（保留持仓不变，调整现金）
                    position_value = sum(
                        pos['quantity'] * pos['avg_entry_price']
                        for pos in self.tracker.positions.values()
                    )
                    new_cash = max(0.0, new_total - position_value)
                    self.tracker.initial_capital = new_total
                    self.tracker.cash = new_cash
                    clean_response = re.sub(
                        r'\[ACTION:ADJUST_TOTAL_ASSET\|' + re.escape(amount_str) + r'\]',
                        f"✅ 总资产已调整为 ₩{self._fmt_price(new_total)}\n"
                        f"   现金余额：₩{self._fmt_price(new_cash)}\n"
                        f"   持仓价值：₩{self._fmt_price(position_value)}",
                        clean_response
                    )
                    self._auto_save()
                    logger.info(f"✅ 总资产调整: ₩{new_total:,.0f}, 现金: ₩{new_cash:,.0f}")
                except Exception as e:
                    logger.error(f"总资产调整失败: {e}")
                    clean_response = re.sub(adjust_pattern, f"❌ 总资产调整失败: {e}", clean_response)

        # 0b. 处理监控状态查询 [CHECK_MONITORING_STATUS]
        if '[CHECK_MONITORING_STATUS]' in llm_response:
            monitoring_report = await self._generate_monitoring_report()
            clean_response = re.sub(
                r'\[CHECK_MONITORING_STATUS\]',
                f"\n\n{monitoring_report}",
                clean_response
            )

        # 0c. 【新增】扫描并缓存 LLM 推荐的目标价
        # 格式范例: "SOL(KRW-SOL): ₩122,800  理由  目标₩135,080 (+10%)  止损₩116,660 (-5%)"
        # 提取目标价逻辑：匹配 "目标" 关键字后的金额
        try:
            # 仅匹配包含 "目标" 和 "₩" 的行
            target_matches = re.findall(r'(\w+(?:-\w+)?(?:\([^\)]+\))?)\s*[:：].*?目标\s*₩([\d,]+)', llm_response)
            for sym_mixed, price_str in target_matches:
                # 解析 symbol: "SOL(KRW-SOL)" -> "KRW-SOL"; "005930" -> "005930"
                if '(' in sym_mixed and ')' in sym_mixed:
                    # 取括号内
                    raw = sym_mixed.split('(')[1].split(')')[0]
                else:
                    raw = sym_mixed
                
                # 尝试标准化（此处上下文可能没有 normalize_symbol 函数定义，需注意作用域）
                # 由于 normalize_symbol 在下面定义，这里只能先存 raw 或者简单处理
                # 简单处理：仅保留字母数字和连字符
                c_sym = re.sub(r'[^\w-]', '', raw).upper()
                c_price = float(price_str.replace(',', ''))
                
                # 存入类级缓存
                if not hasattr(self.__class__, '_recommendation_targets'):
                    self.__class__._recommendation_targets = {}
                self.__class__._recommendation_targets[c_sym] = c_price
                logger.info(f"💾 缓存推荐目标价: {c_sym} -> ₩{c_price:,.0f}")
        except Exception as e_cache:
            logger.warning(f"解析推荐目标失败: {e_cache}")
        
        # 1. 处理价格查询 [QUERY_PRICE|币种]  
        price_query_pattern = r'\[QUERY_PRICE\|([^\]]+)\]'
        price_queries = re.findall(price_query_pattern, llm_response)
        
        # 符号标准化：动态查 KRX 缓存 + 加密货币中文名映射
        _crypto_name_map = {
            '比特币': 'KRW-BTC', 'bitcoin': 'KRW-BTC', 'btc': 'KRW-BTC',
            '以太坊': 'KRW-ETH', 'ethereum': 'KRW-ETH', 'eth': 'KRW-ETH',
            '瑞波': 'KRW-XRP', 'ripple': 'KRW-XRP', 'xrp': 'KRW-XRP',
            '狗狗币': 'KRW-DOGE', 'dogecoin': 'KRW-DOGE', 'doge': 'KRW-DOGE',
            '索拉纳': 'KRW-SOL', 'solana': 'KRW-SOL', 'sol': 'KRW-SOL',
            '波卡': 'KRW-DOT', 'polkadot': 'KRW-DOT',
            '艾达币': 'KRW-ADA', 'cardano': 'KRW-ADA',
        }
        # 确保 KRX 名称缓存已加载
        if not self.__class__._krx_cache_loaded:
            await asyncio.to_thread(self.__class__._load_krx_name_map)

        def normalize_symbol(symbol):
            """将中文/英文公司名动态解析为可查询代码"""
            symbol = symbol.strip()
            # 先剥离 KRX: 前缀
            if symbol.upper().startswith('KRX:'):
                symbol = symbol[4:]
            sym_lower = symbol.lower()
            
            # 0. 检查推荐缓存中的符号匹配（新增）
            if hasattr(self.__class__, '_recommendation_targets'):
                if symbol.upper() in self.__class__._recommendation_targets:
                    return symbol.upper()
                # 反向查：如果缓存里有 KRW-SOL，用户输入 SOL
                for k in self.__class__._recommendation_targets:
                    if k.endswith(f'-{symbol.upper()}'):
                        return k

            # 1. 加密货币中文/英文名
            if sym_lower in _crypto_name_map:
                return _crypto_name_map[sym_lower]

            # 2. 已经是标准格式（6位数字/KRW-XXX/字母Ticker）直接返回
            if symbol.isdigit() and len(symbol) == 6:
                return symbol
            if symbol.upper().startswith('KRW-') or symbol.upper().startswith('USDT-'):
                return symbol
            if symbol.isalpha() and symbol.isupper() and len(symbol) <= 10:
                # 先查加密货币缓存（避免短字母 ticker 被当成股票）
                krw_sym = f'KRW-{symbol}'
                if krw_sym in self.__class__._crypto_price_cache:
                    return krw_sym
                return symbol

            # 3. 在 KRX 名称缓存里查（支持任意韩国上市公司名称）
            krx_cache = self.__class__._krx_name_to_code
            if symbol in krx_cache:
                return krx_cache[symbol]
            # 模糊匹配：名称包含关系
            sym_lower_full = symbol.lower()
            for name, code in krx_cache.items():
                if sym_lower_full in name.lower() or name.lower() in sym_lower_full:
                    return code

            return symbol  # 找不到则原样返回
        
        price_queries = [normalize_symbol(s) for s in price_queries]
        
        for symbol in price_queries:
            price_info = await self._get_current_price(symbol)
            if price_info:
                clean_response = re.sub(
                    r'\[QUERY_PRICE\|' + re.escape(symbol) + r'\]',
                    f"\n\n💰 {symbol} 当前价格：₩{self._fmt_price(price_info['price'])}\n"
                    f"   24h 涨跌：{price_info.get('change_pct', 0):+.2f}%",
                    clean_response
                )
            else:
                clean_response = re.sub(
                    r'\[QUERY_PRICE\|' + re.escape(symbol) + r'\]',
                    f"\n\n❌ 无法获取 {symbol} 的价格",
                    clean_response
                )
        
        # 2. 处理自动获取价格并买入 [GET_PRICE_AND_BUY|币种|总金额]
        auto_buy_pattern = r'\[GET_PRICE_AND_BUY\|([^|]+)\|([^|]+)\]'
        auto_buys = re.findall(auto_buy_pattern, llm_response)
        
        for raw_sym, amount_str in auto_buys:
            raw_sym = raw_sym.strip()
            # 用原始 symbol 构造 regex（LLM 输出的是原始 symbol）
            tag_pattern = r'\[GET_PRICE_AND_BUY\|' + re.escape(raw_sym) + r'\|[^\]]+\]'
            symbol = raw_sym  # 可能被 normalize 改变，但 regex 始终用 raw_sym
            try:
                # 标准化符号（仅用于价格查询和仓位记录）
                symbol = normalize_symbol(raw_sym)
                
                # 解析金额（支持中文单位和货币转换）
                amount_str = amount_str.strip()
                
                # 检测货币单位
                is_usd = '美元' in amount_str or 'USD' in amount_str.upper()
                
                # 提取数字
                clean_amount = amount_str.replace(',', '').replace('韩币', '').replace('韩元', '').replace('美元', '').replace('USD', '').replace('KRW', '').strip()
                total_amount = float(clean_amount)
                
                # 美元转韩元（假设汇率1300，实际应该查询实时汇率）
                if is_usd:
                    total_amount = total_amount * 1300
                    logger.info(f"💱 货币转换: ${clean_amount} → ₩{total_amount:,.0f} (汇率1:1300)")
                
                # 获取当前价格
                price_info = await self._get_current_price(symbol)
                
                if not price_info:
                    clean_response = re.sub(
                        tag_pattern,
                        f"\n\n❌ 无法获取 {symbol} 的当前价格，买入失败",
                        clean_response
                    )
                    continue
                
                current_price = price_info['price']
                quantity = total_amount / current_price
                
                # 尝试从推荐缓存中获取目标价
                target_p = None
                if hasattr(self.__class__, '_recommendation_targets'):
                    # 尝试匹配 KRW-SOL 或 SOL
                    for k in [symbol, symbol.replace('KRW-', '')]:
                        if k in self.__class__._recommendation_targets:
                            target_p = self.__class__._recommendation_targets[k]
                            break
                        # 尝试反向匹配：缓存里是 KRW-SOL，当前是 SOL
                        for ck in self.__class__._recommendation_targets:
                            if ck.endswith(f'-{k}'):
                                target_p = self.__class__._recommendation_targets[ck]
                                break
                        if target_p: break

                # 执行买入
                if self.tracker:
                    result = self.tracker.open_position(
                        symbol, quantity, current_price,
                        custom_profit_target_price=target_p
                    )
                    
                    if result.get('success', True):
                        pnl_block = await self._build_full_session_report()
                        pnl_text  = f"\n\n{pnl_block}" if pnl_block else ""
                        
                        target_msg = ""
                        if target_p:
                            pct = (target_p - current_price) / current_price * 100
                            target_msg = f"\n   🎯 止盈目标：₩{self._fmt_price(target_p)} (+{pct:.1f}%)"
                        
                        clean_response = re.sub(
                            tag_pattern,
                            f"\n\n✅ 买入成功！\n"
                            f"   币种：{symbol}\n"
                            f"   数量：{quantity:g}\n"
                            f"   单价：₩{self._fmt_price(current_price)}\n"
                            f"   总金额：₩{self._fmt_price(total_amount)}\n"
                            f"   24h涨跌：{price_info.get('change_pct', 0):+.2f}%\n"
                            f"   剩余资金：₩{self._fmt_price(self.tracker.cash)}"
                            f"{target_msg}"
                            f"{pnl_text}",
                            clean_response
                        )
                        self._auto_save()
                        logger.info(f"✅ 自动买入: {symbol} {quantity:g} @ {current_price:,.0f} (Target: {target_p})")
                    else:
                        reason = result.get('reason', '')
                        if reason == 'insufficient_funds':
                            required  = result.get('required', total_amount)
                            available = result.get('available', self.tracker.cash)
                            shortage  = required - available
                            err_msg = (
                                f"\n\n\u274c \u8d44\u91d1\u4e0d\u8db3\uff0c\u65e0\u6cd5\u4e70\u5165 {symbol}\n"
                                f"   \u9700\u8981\uff1a\u20a9{self._fmt_price(required)}\n"
                                f"   \u4f59\u989d\uff1a\u20a9{self._fmt_price(available)}\n"
                                f"   \u7f3a\u53e3\uff1a\u20a9{self._fmt_price(shortage)}\n\n"
                                f"   \ud83d\udca1 \u53ef\u53d1\u9001\u201c\u8c03\u6574\u603b\u8d44\u4ea7 {int((required+available)/10000)}\u4e07\u201d\u6765\u8c03\u6574\u8d26\u6237\u4f59\u989d"
                            )
                        else:
                            err_msg = f"\n\n\u274c \u4e70\u5165\u5931\u8d25\uff1a{result.get('reason', '\u672a\u77e5\u9519\u8bef')}"
                        clean_response = re.sub(tag_pattern, err_msg, clean_response)
                else:
                    clean_response = re.sub(
                        tag_pattern,
                        "\n\n❌ 持仓追踪器未初始化",
                        clean_response
                    )
            
            except Exception as e:
                logger.error(f"自动买入失败: {e}")
                clean_response = re.sub(
                    tag_pattern,
                    f"\n\n❌ 买入失败：{str(e)}",
                    clean_response
                )
        
        # 3. 处理卖出操作（LLM输出格式：[ACTION:SELL|symbol|quantity] 或 [ACTION:SELL|symbol|quantity|price]）
        sell_pattern = r'\[ACTION:SELL\|([^|]+)\|([^|\]]+)(?:\|([^\]]+))?\]'
        sell_matches = re.findall(sell_pattern, llm_response)

        for symbol, quantity_str, price_str_raw in sell_matches:
            raw_sym = symbol.strip()
            symbol = normalize_symbol(raw_sym)  # 标准化：EPT→KRW-EPT
            sell_tag_re = r'\[ACTION:SELL\|' + re.escape(raw_sym) + r'\|[^\]]+\]'
            try:
                quantity = float(quantity_str.strip())

                # 卖出前先记录持仓信息（用于计算预计盈亏）
                pos_info = self.tracker.positions.get(symbol, {}) if self.tracker else {}
                entry_price = pos_info.get('avg_entry_price', 0)

                # 用户指定了价格 → 直接用；否则实时查价
                user_price_str = price_str_raw.strip() if price_str_raw else ''
                if user_price_str:
                    price = float(user_price_str.replace(',', ''))
                    market_price = None  # 不需要实时查价
                    logger.info(f"卖出使用用户指定价格: {symbol} @ ₩{self._fmt_price(price)}")
                else:
                    price_info = await self._get_current_price(symbol)
                    if not price_info:
                        clean_response = re.sub(
                            sell_tag_re,
                            f"\n\n❌ 卖出失败：无法获取 {symbol} 当前价格",
                            clean_response
                        )
                        continue
                    price = price_info['price']
                    market_price = price  # 按市价卖，无需单独显示预计

                result = self.tracker.close_position(symbol, quantity, price)
                if result.get('success', True):
                    cp = result.get('closed_position', {})
                    pnl     = cp.get('pnl', 0)
                    pnl_pct = cp.get('pnl_pct', 0)

                    # 构造卖出回执
                    msg_lines = [
                        f"\n\n✅ 卖出成功：{symbol} {quantity:g}个/股 @ ₩{self._fmt_price(price)}",
                    ]
                    if entry_price > 0:
                        # 若用户指定了卖出价，额外展示「若按市价」的预计盈亏
                        if user_price_str:
                            market_info = await self._get_current_price(symbol)
                            if market_info:
                                mkt = market_info['price']
                                mkt_pnl = (mkt - entry_price) * quantity
                                mkt_pnl_pct = (mkt - entry_price) / entry_price * 100
                                msg_lines.append(
                                    f"   📈 市价参考：₩{self._fmt_price(mkt)}  预计盈亏 ₩{mkt_pnl:+,.0f}（{mkt_pnl_pct:+.2f}%）"
                                )
                        msg_lines.append(
                            f"   💹 实际盈亏（买入₩{self._fmt_price(entry_price)} → 卖出₩{self._fmt_price(price)}）：₩{pnl:+,.0f}（{pnl_pct:+.2f}%）"
                        )
                    msg_lines.append(f"   💵 剩余资金：₩{self._fmt_price(self.tracker.cash)}")
                    # 追加完整 session 报告（含已实现盈亏汇总）
                    session_rpt = await self._build_full_session_report()
                    if session_rpt:
                        msg_lines.append(f"\n{session_rpt}")
                    clean_response = re.sub(sell_tag_re, "".join(msg_lines), clean_response)
                    self._auto_save()
                    logger.info(f"✅ 卖出执行: {symbol} {quantity} @ {price:,.0f}, P&L: ₩{pnl:+,.0f} ({pnl_pct:+.2f}%)")
                else:
                    clean_response = re.sub(
                        sell_tag_re,
                        f"\n\n❌ 卖出失败：{result.get('reason', '未知错误')}",
                        clean_response
                    )

            except Exception as e:
                logger.error(f"卖出操作失败 {raw_sym}: {e}")
                clean_response = re.sub(
                    sell_tag_re,
                    f"\n\n❌ 卖出失败：{str(e)}",
                    clean_response
                )

        # 3b. 处理标准买入操作 [ACTION:BUY|代码|数量|价格]
        buy_pattern = r'\[ACTION:BUY\|([^|]+)\|([^|]+)\|([^\]]+)\]'
        buy_matches = re.findall(buy_pattern, llm_response)

        for symbol, quantity_str, price_str in buy_matches:
            raw_sym = symbol.strip()
            symbol = normalize_symbol(raw_sym)  # 标准化：EPT→KRW-EPT 等
            # tag_pattern 始终用 raw_sym（LLM 输出的原始符号）
            buy_tag_re = r'\[ACTION:BUY\|' + re.escape(raw_sym) + r'\|[^\]]+\]'
            try:
                quantity = float(quantity_str)
                price = float(price_str.replace(',', ''))

                # 尝试从推荐缓存中获取目标价
                target_p = None
                if hasattr(self.__class__, '_recommendation_targets'):
                    for k in [symbol, symbol.replace('KRW-', '')]:
                        if k in self.__class__._recommendation_targets:
                            target_p = self.__class__._recommendation_targets[k]
                            break
                        for ck in self.__class__._recommendation_targets:
                            if ck.endswith(f'-{k}'):
                                target_p = self.__class__._recommendation_targets[ck]
                                break
                        if target_p: break

                result = self.tracker.open_position(
                    symbol, quantity, price,
                    custom_profit_target_price=target_p
                )
                
                if result.get('success', True):
                    pnl_block = await self._build_full_session_report()
                    pnl_text  = f"\n\n{pnl_block}" if pnl_block else ""
                    
                    target_msg = ""
                    if target_p:
                        pct = (target_p - price) / price * 100
                        target_msg = f"\n   🎯 止盈目标：₩{self._fmt_price(target_p)} (+{pct:.1f}%)"
                        
                    clean_response = re.sub(
                        buy_tag_re,
                        f"\n\n✅ 买入成功：{symbol} {quantity:g}个/股 @ ₩{self._fmt_price(price)}\n"
                        f"   总金额：₩{self._fmt_price(quantity * price)}\n"
                        f"   剩余资金：₩{self._fmt_price(self.tracker.cash)}"
                        f"{target_msg}"
                        f"{pnl_text}",
                        clean_response
                    )
                    self._auto_save()
                    logger.info(f"✅ 买入执行: {symbol} {quantity} @ {price:,.0f} (Target: {target_p})")
                else:
                    reason = result.get('reason', '')
                    if reason == 'insufficient_funds':
                        required  = result.get('required', quantity * price)
                        available = result.get('available', self.tracker.cash)
                        shortage  = required - available
                        err_msg = (
                            f"\n\n❌ 资金不足，无法买入 {symbol}\n"
                            f"   需要：₩{self._fmt_price(required)}\n"
                            f"   余额：₩{self._fmt_price(available)}\n"
                            f"   缺口：₩{self._fmt_price(shortage)}\n\n"
                            f"   💡 可发送「调整总资产 {int((required+available)/10000)}万」来调整账户余额"
                        )
                    else:
                        err_msg = f"\n\n❌ 买入失败：{result.get('reason', '未知错误')}"
                    clean_response = re.sub(buy_tag_re, err_msg, clean_response)

            except Exception as e:
                logger.error(f"买入操作失败 {raw_sym}: {e}")
                clean_response = re.sub(
                    buy_tag_re,
                    f"\n\n❌ 买入失败：{str(e)}",
                    clean_response
                )
        
        # 4. 处理DART公告查询 [QUERY_ANNOUNCEMENTS] 或 [QUERY_ANNOUNCEMENTS|公司名]
        if self.announcement_monitor:
            announcement_pattern = r'\[QUERY_ANNOUNCEMENTS(?:\|([^\]]+))?\]'
            announcement_matches = re.findall(announcement_pattern, llm_response)
            
            if announcement_matches:
                try:
                    # 获取最近的重要公告
                    announcements = await self.announcement_monitor.monitor_announcements()
                    
                    if announcements:
                        # 格式化公告信息
                        ann_text = "📢 最近重要公告：\n"
                        for i, ann in enumerate(announcements[:5], 1):  # 只显示前5条
                            ann_text += f"{i}. {ann['corp_name']}\n"
                            ann_text += f"   {ann['report_name']}\n"
                            ann_text += f"   日期: {ann['receive_date']}\n"
                        
                        ann_text += f"\n共{len(announcements)}条重要公告"
                        
                        clean_response = re.sub(
                            announcement_pattern,
                            f"\n\n{ann_text}",
                            clean_response
                        )
                    else:
                        clean_response = re.sub(
                            announcement_pattern,
                            "\n\n📢 暂无重要公告",
                            clean_response
                        )
                    
                except Exception as e:
                    logger.error(f"查询DART公告失败: {e}")
                    clean_response = re.sub(
                        announcement_pattern,
                        f"\n\n❌ 公告查询失败: {str(e)}",
                        clean_response
                    )

        # 5. 处理K线查询 [QUERY_KLINE|代码] 或 [QUERY_KLINE|代码|天数]
        if self.kline_fetcher:
            kline_pattern = r'\[QUERY_KLINE\|([^|\]]+)(?:\|(\d+))?\]'
            kline_matches = re.findall(kline_pattern, llm_response)
            for symbol, days_str in kline_matches:
                symbol = symbol.strip()
                days = int(days_str) if days_str else 20
                try:
                    ohlcv = await self.kline_fetcher.get_ohlcv(symbol, days)
                    # 美股不支持资金流向（pykrx仅限韩股）
                    flow = None
                    if not self.kline_fetcher._is_us_stock(symbol):
                        flow = await self.kline_fetcher.get_investor_flow(symbol)
                    text  = self.kline_fetcher.format_kline_summary(ohlcv, flow)
                    clean_response = re.sub(
                        r'\[QUERY_KLINE\|' + re.escape(symbol) + r'(?:\|\d+)?\]',
                        f"\n\n{text}",
                        clean_response
                    )
                    logger.info(f"✅ K线查询成功: {symbol}")
                except Exception as e:
                    logger.error(f"K线查询失败 {symbol}: {e}")
                    clean_response = re.sub(
                        r'\[QUERY_KLINE\|' + re.escape(symbol) + r'(?:\|\d+)?\]',
                        f"\n\n❌ {symbol} K线获取失败",
                        clean_response
                    )

        # 最终兜底：清理所有未被处理的 action tag，绝不暴露给用户
        clean_response = re.sub(
            r'\[(GET_PRICE_AND_BUY|ACTION:BUY|ACTION:SELL|QUERY_PRICE|QUERY_ANNOUNCEMENTS|QUERY_KLINE)[^\]]*\]',
            '',
            clean_response
        ).strip()

        return clean_response
    
    @staticmethod
    def _fmt_price(price: float) -> str:
        """
        原始精度格式化价格/金额，绝不四舍五入：
          ≥ 100            → 整数时无小数，有小数最多保留2位：₩181,200 / ₩181,200.5
          1 ≤ price < 100  → 至少2位小数，最多4位（去尾零）：₩2.00 / ₩1.35 / ₩1.3500 → ₩1.35
          < 1              → 至少4位小数，最多8位（去尾零）：₩0.0230 / ₩0.000234
        对于小价值加密货币（< 100 ₩），始终显示小数位，让用户确认没有四舍五入。
        """
        neg = price < 0
        abs_p = abs(price)

        if abs_p >= 100:
            # 大价格：整数则不加小数位
            if abs_p == int(abs_p):
                s = f'{int(abs_p):,}'
                return f'-{s}' if neg else s
            s = f'{abs_p:.2f}'.rstrip('0').rstrip('.')
        elif abs_p >= 1:
            # 小价格（1~99）：始终保留至少2位小数，去除多余尾零
            raw = f'{abs_p:.4f}'          # "2.0000" / "1.3500"
            stripped = raw.rstrip('0')    # "2." / "1.35"
            # 补足到至少2位小数
            if '.' not in stripped or len(stripped.split('.')[1]) < 2:
                stripped = f'{abs_p:.2f}'
            s = stripped
        else:
            # 极小价格（< 1）：保留至少4位小数
            raw = f'{abs_p:.8f}'.rstrip('0')
            if '.' not in raw or len(raw.split('.')[1]) < 4:
                raw = f'{abs_p:.4f}'
            s = raw

        # 加千位分隔符（整数部分）
        if '.' in s:
            int_part, dec_part = s.split('.', 1)
            formatted = f'{int(int_part):,}.{dec_part}'
        else:
            formatted = f'{int(s.replace(",", "")):,}'
        return f'-{formatted}' if neg else formatted

    @staticmethod
    def _fmt_signed(amount: float) -> str:
        """格式化带符号金额（+/-），不四舍五入"""
        s = ConversationHandler._fmt_price(abs(amount))
        return f'+{s}' if amount >= 0 else f'-{s}'

    async def _get_current_price(self, symbol: str, force_live: bool = False) -> Optional[Dict[str, Any]]:
        """获取当前价格（加密货币或股票）。
        force_live=True 时绕过缓存直接从交易所查询实时数据。
        """

        # 1. 加密货币（KRW-BTC, USDT-BTC等）
        if symbol.startswith('KRW-') or symbol.startswith('USDT-'):
            # ★ 命中类缓存（每小时刷新），force_live 时跳过
            if not force_live:
                cached = self.__class__._crypto_price_cache.get(symbol)
                if cached and cached.get('price', 0) > 0:
                    logger.info(f'[cache] {symbol}: ₩{self._fmt_price(cached["price"])} ({cached.get("change_pct", 0):+.2f}%)')
                    return {
                        'price':      cached['price'],
                        'change_pct': cached.get('change_pct', 0.0),
                        'volume':     cached.get('volume', 0),
                        'exchange':   cached.get('exchange', '?'),
                    }
            # 缓存未命中 或 force_live → 实时查询（Bithumb 优先，其次 Upbit）
            if self.crypto_fetcher:
                try:
                    price_data = await self.crypto_fetcher.get_bithumb_price(symbol.replace('KRW-', ''))
                    if price_data:
                        logger.info(f'[live] {symbol} Bithumb: ₩{self._fmt_price(price_data["price"])}')
                        return price_data
                    price_data = await self.crypto_fetcher.get_upbit_price(symbol)
                    if price_data:
                        logger.info(f'[live] {symbol} Upbit(降级): ₩{self._fmt_price(price_data["price"])}')
                        return price_data
                    logger.warning(f"无法从任何交易所获取 {symbol} 价格")
                    return None
                except Exception as e:
                    logger.error(f"获取加密货币价格失败: {e}")
                    return None
            else:
                logger.warning("CryptoDataFetcher 未初始化")
                return None
        
        # 1b. 裸字母加密货币 ticker（如 EPT、DOGE）→ 转为 KRW- 前缀重试
        if symbol.isalpha() and symbol.isupper() and len(symbol) <= 10:
            krw_sym = f'KRW-{symbol}'
            # ① 先查类级别缓存（force_live 时跳过）
            if not force_live:
                cached = self.__class__._crypto_price_cache.get(krw_sym)
                if cached and cached.get('price', 0) > 0:
                    logger.info(f'[cache-bare] {symbol} → {krw_sym}: ₩{self._fmt_price(cached["price"])}')
                    return {
                        'price':      cached['price'],
                        'change_pct': cached.get('change_pct', 0.0),
                        'volume':     cached.get('volume', 0),
                        'exchange':   cached.get('exchange', '?'),
                    }
            # ② 实时查（Bithumb 优先，其次 Upbit）
            if self.crypto_fetcher:
                try:
                    price_data = await self.crypto_fetcher.get_bithumb_price(symbol)
                    if price_data:
                        logger.info(f'[live-bare] {symbol} Bithumb: ₩{self._fmt_price(price_data["price"])}')
                        return price_data
                    price_data = await self.crypto_fetcher.get_upbit_price(krw_sym)
                    if price_data:
                        logger.info(f'[live-bare] {symbol} Upbit(降级): ₩{self._fmt_price(price_data["price"])}')
                        return price_data
                except Exception as e:
                    logger.warning(f'裸ticker {symbol} 加密查询失败: {e}')
            # 不是加密货币 → 继续往下走（韩股/美股）

        # 2. 韩国股票（6位数字代码，或带KRX:前缀）
        if symbol.upper().startswith('KRX:'):
            symbol = symbol[4:]  # 去掉 KRX: 前缀
        if symbol.isdigit() and len(symbol) == 6:
            try:
                from pykrx import stock as pykrx_stock
                from datetime import datetime as dt
                
                today = dt.now().strftime('%Y%m%d')
                yesterday = (dt.now() - timedelta(days=5)).strftime('%Y%m%d')
                
                df = await asyncio.to_thread(
                    pykrx_stock.get_market_ohlcv_by_date,
                    yesterday, today, symbol
                )
                
                if df is None or df.empty:
                    logger.warning(f"pykrx未返回数据: {symbol}")
                    return None
                
                latest = df.iloc[-1]
                prev_close = df.iloc[-2]['종가'] if len(df) > 1 else latest['종가']
                
                return {
                    'price': float(latest['종가']),
                    'change_pct': ((float(latest['종가']) - float(prev_close)) / float(prev_close) * 100)
                        if prev_close > 0 else 0,
                    'volume': float(latest['거래량']),
                    'high': float(latest['고가']),
                    'low': float(latest['저가'])
                }
                
            except Exception as e:
                logger.error(f"获取韩股价格失败 ({symbol}): {e}")
                return None
        
        # 3. 美股/港股（TSLA, AAPL等）
        elif self.us_hk_fetcher:
            try:
                # 尝试作为美股获取
                stock_info = await asyncio.to_thread(
                    self.us_hk_fetcher.get_us_stock_info,
                    symbol
                )
                
                # 如果美股失败，尝试作为港股
                if not stock_info:
                    stock_info = await asyncio.to_thread(
                        self.us_hk_fetcher.get_hk_stock_info,
                        symbol
                    )
                
                if not stock_info or not stock_info.get('price'):
                    logger.warning(f"未获取到 {symbol} 的价格数据")
                    return None
                
                # 转换为统一格式
                price = stock_info['price']
                change_pct = stock_info.get('change_percent', 0)
                
                # 如果价格是美元，转换为韩元（假设汇率1300）
                if stock_info.get('currency') == 'USD':
                    price = price * 1300
                    logger.info(f"💱 {symbol} USD价格转换为KRW: ${stock_info['price']:.2f} → ₩{price:,.0f}")
                
                return {
                    'price': price,
                    'change_pct': change_pct,
                    'volume': stock_info.get('volume', 0)
                }
                
            except Exception as e:
                logger.error(f"获取美股/港股价格失败 ({symbol}): {e}")
                return None
        
        else:
            logger.warning(f"无法识别符号类型或缺少对应数据源: {symbol}")
            return None
    
    async def _generate_monitoring_report(self) -> str:
        """生成完整的监控状态报告"""
        report_parts = []
        
        report_parts.append("=" * 50)
        report_parts.append("📊 系统监控状态报告")
        report_parts.append("=" * 50)
        report_parts.append(f"⏰ 报告时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 1. 持仓风险监控
        if self.tracker and self.tracker.positions:
            report_parts.append("🔍 持仓风险监控：")
            report_parts.append("-" * 50)
            
            # 获取当前价格
            current_prices = {}
            for symbol in self.tracker.positions.keys():
                price_info = await self._get_current_price(symbol)
                if price_info:
                    current_prices[symbol] = price_info['price']
                else:
                    current_prices[symbol] = self.tracker.positions[symbol]['avg_entry_price']
            
            # 分析每个持仓
            high_risk_count = 0
            warning_count = 0
            profit_target_count = 0
            major_gain_count = 0
            
            for symbol, pos in self.tracker.positions.items():
                current_price = current_prices.get(symbol, pos['avg_entry_price'])
                pnl_pct = ((current_price - pos['avg_entry_price']) / pos['avg_entry_price'] * 100)
                
                status_icon = "🟢"
                status_text = "正常"
                
                if pnl_pct <= -10:
                    status_icon = "🔴"
                    status_text = "止损红线"
                    high_risk_count += 1
                elif pnl_pct <= -8:
                    status_icon = "⚠️"
                    status_text = "风险警告"
                    warning_count += 1
                elif pnl_pct >= 20:
                    status_icon = "✅"
                    status_text = "达标止盈"
                    profit_target_count += 1
                elif pnl_pct >= 15:
                    status_icon = "📈"
                    status_text = "重大利好"
                    major_gain_count += 1
                
                report_parts.append(
                    f"{status_icon} {symbol}: {pnl_pct:+.2f}% ({status_text})\n"
                    f"   成本：₩{self._fmt_price(pos['avg_entry_price'])} | "
                    f"现价：₩{self._fmt_price(current_price)} | "
                    f"数量：{pos['quantity']}"
                )
            
            # 风险总结
            report_parts.append("\n📌 风险总结：")
            if high_risk_count > 0:
                report_parts.append(f"   🔴 止损红线：{high_risk_count} 个持仓（需立即处理）")
            if warning_count > 0:
                report_parts.append(f"   ⚠️ 风险警告：{warning_count} 个持仓（密切关注）")
            if profit_target_count > 0:
                report_parts.append(f"   ✅ 达标止盈：{profit_target_count} 个持仓（考虑获利了结）")
            if major_gain_count > 0:
                report_parts.append(f"   📈 重大利好：{major_gain_count} 个持仓（表现优秀）")
            if high_risk_count == 0 and warning_count == 0:
                report_parts.append("   ✅ 所有持仓风险可控")
        else:
            report_parts.append("📭 当前无持仓，无需监控")
        
        # 2. 数据源状态
        report_parts.append("\n" + "=" * 50)
        report_parts.append("🌐 数据源连接状态：")
        report_parts.append("-" * 50)
        
        if self.crypto_fetcher:
            report_parts.append("✅ 加密货币数据：Upbit + Bithumb（实时）")
        else:
            report_parts.append("❌ 加密货币数据：未初始化")
        
        if self.us_hk_fetcher:
            report_parts.append("✅ 美股数据：Finnhub API（实时）")
            report_parts.append("✅ 港股数据：yfinance（实时）")
        else:
            report_parts.append("❌ 美股/港股数据：未初始化")
        
        report_parts.append("✅ 韩国股票数据：pykrx（可用）")
        
        if self.announcement_monitor:
            report_parts.append("✅ DART公告监控：韩国金融监督院（已连接）")
        else:
            report_parts.append("⚠️ DART公告监控：未初始化（需配置DART_API_KEY）")
        
        # 3. DART最新公告（快速预览）
        if self.announcement_monitor:
            report_parts.append("\n" + "=" * 50)
            report_parts.append("📢 DART最新重要公告：")
            report_parts.append("-" * 50)
            try:
                significant = await self.announcement_monitor.monitor_announcements()
                if significant:
                    for ann in significant[:3]:  # 只显示最近3条
                        report_parts.append(f"• {ann['corp_name']}: {ann['report_name'][:30]}")
                    if len(significant) > 3:
                        report_parts.append(f"  …还有{len(significant)-3}条重要公告")
                else:
                    report_parts.append("📭 今日暂无重要公告")
            except Exception as e:
                report_parts.append(f"⚠️ 公告获取失败: {str(e)[:30]}")
        
        # 3. AI 模型状态
        if self.model_manager:
            report_parts.append("\n" + "=" * 50)
            report_parts.append("🤖 AI 模型状态：")
            report_parts.append("-" * 50)
            model_info = self.model_manager.get_model_info()
            report_parts.append(f"✅ 当前模型：{model_info.get('name', 'Unknown')}")
            report_parts.append(f"   配额：{model_info.get('quota', 'Unknown')}")
            report_parts.append(f"   描述：{model_info.get('description', 'Unknown')}")
        
        # 4. 告警系统状态
        report_parts.append("\n" + "=" * 50)
        report_parts.append("🔔 告警系统：")
        report_parts.append("-" * 50)
        report_parts.append("✅ 持仓止损告警：已启用（-10%强制止损）")
        report_parts.append("✅ 持仓止盈提示：已启用（+20%目标）")
        report_parts.append("✅ 实时价格监控：已启用")
        
        # 5. 监控建议
        report_parts.append("\n" + "=" * 50)
        report_parts.append("💡 监控建议：")
        report_parts.append("-" * 50)
        
        if high_risk_count > 0:
            report_parts.append("⚠️ 紧急：有持仓触及止损红线，建议立即平仓止损")
        elif warning_count > 0:
            report_parts.append("⚠️ 警告：有持仓接近止损线，密切关注价格走势")
        
        if profit_target_count > 0:
            report_parts.append("✅ 建议：有持仓达到目标收益，可考虑获利了结")
        
        if high_risk_count == 0 and warning_count == 0 and profit_target_count == 0:
            report_parts.append("✅ 当前持仓状态良好，继续保持监控")
        
        report_parts.append("\n" + "=" * 50)
        
        return "\n".join(report_parts)
    
    async def _fallback_processing(self, user_message: str) -> str:
        """当LLM不可用时的降级处理"""
        
        # 简单的关键词匹配
        message_lower = user_message.lower()
        
        # 持仓查询
        if any(kw in user_message for kw in ['持仓', '仓位', '我的', '当前']):
            if not self.tracker:
                return "持仓追踪器未初始化"
            
            if not self.tracker.positions:
                return "您当前没有持仓"
            
            response = "📊 当前持仓：\n\n"
            for symbol, pos in self.tracker.positions.items():
                current_value = pos['quantity'] * pos['avg_entry_price']
                pnl = current_value - pos['total_cost']
                pnl_pct = (pnl / pos['total_cost'] * 100) if pos['total_cost'] > 0 else 0
                
                emoji = "🟢" if pnl >= 0 else "🔴"
                response += f"{emoji} {symbol}\n"
                response += f"   数量: {pos['quantity']} @ ₩{pos['avg_entry_price']:,}\n"
                response += f"   盈亏: ₩{self._fmt_signed(pnl)} ({pnl_pct:+.2f}%)\n\n"
            
            response += f"💰 剩余资金: ₩{self._fmt_price(self.tracker.cash)}"
            return response
        
        # 默认回复
        return "我是安诚科技 Ancent AI 交易助手。我可以帮您：\n• 查询持仓和账户信息\n• 提供交易建议\n• 执行买入卖出操作\n\n请告诉我您需要什么帮助？"
    
    async def _detect_intent(self, message: str) -> Dict[str, Any]:
        """检测用户意图"""
        
        # 先用规则匹配（快速）
        rule_based_intent = self._rule_based_intent_detection(message)
        if rule_based_intent['confidence'] > 0.8:
            return rule_based_intent
        
        # 如果规则不确定，使用AI
        if self.model:
            ai_intent = await self._ai_intent_detection(message)
            return ai_intent
        
        return rule_based_intent
    
    def _rule_based_intent_detection(self, message: str) -> Dict[str, Any]:
        """基于规则的意图识别"""
        message_lower = message.lower()
        
        # 买入关键词
        buy_keywords = ['买入', '买', '购买', '建仓', 'buy', '입수', '매수']
        # 卖出关键词
        sell_keywords = ['卖出', '卖', '平仓', 'sell', '매도', '팔다']
        # 建议关键词
        advice_keywords = ['建议', '推荐', '分析', '看法', 'advice', '추천', '분석']
        # 持仓关键词
        position_keywords = ['持仓', '仓位', '我的', '当前', 'position', '포지션']
        # 价格关键词
        price_keywords = ['价格', '多少钱', '报价', 'price', '가격']
        # 调仓关键词
        adjustment_keywords = ['调整', '优化', '调仓', '再平衡', 'rebalance', '조정']
        # 分析关键词
        analysis_keywords = ['市场', '行情', '趋势', '走势', 'market', '시장']
        
        # 提取股票代码或币种
        extracted_symbols = self._extract_symbols(message)
        
        # 买入检测
        if any(kw in message for kw in buy_keywords):
            return {
                'intent': 'BUY_STOCK',
                'confidence': 0.9,
                'symbols': extracted_symbols,
                'raw_message': message
            }
        
        # 卖出检测
        if any(kw in message for kw in sell_keywords):
            return {
                'intent': 'SELL_STOCK',
                'confidence': 0.9,
                'symbols': extracted_symbols,
                'raw_message': message
            }
        
        # 建议检测
        if any(kw in message for kw in advice_keywords):
            return {
                'intent': 'ASK_ADVICE',
                'confidence': 0.85,
                'symbols': extracted_symbols,
                'raw_message': message
            }
        
        # 持仓检测
        if any(kw in message for kw in position_keywords):
            return {
                'intent': 'CHECK_POSITION',
                'confidence': 0.85,
                'symbols': extracted_symbols,
                'raw_message': message
            }
        
        # 价格检测
        if any(kw in message for kw in price_keywords):
            return {
                'intent': 'CHECK_PRICE',
                'confidence': 0.85,
                'symbols': extracted_symbols,
                'raw_message': message
            }
        
        # 调仓检测
        if any(kw in message for kw in adjustment_keywords):
            return {
                'intent': 'PORTFOLIO_ADJUSTMENT',
                'confidence': 0.8,
                'symbols': [],
                'raw_message': message
            }
        
        # 市场分析检测
        if any(kw in message for kw in analysis_keywords):
            return {
                'intent': 'MARKET_ANALYSIS',
                'confidence': 0.75,
                'symbols': extracted_symbols,
                'raw_message': message
            }
        
        # 回测检测
        backtest_keywords = ['回测', '测试策略', '历史测试', 'backtest', '백테스트', '策略测试']
        if any(kw in message for kw in backtest_keywords):
            return {
                'intent': 'RUN_BACKTEST',
                'confidence': 0.85,
                'symbols': extracted_symbols,
                'raw_message': message
            }
        
        # 默认为通用对话
        return {
            'intent': 'GENERAL',
            'confidence': 0.5,
            'symbols': [],
            'raw_message': message
        }
    
    def _extract_symbols(self, message: str) -> List[str]:
        """从消息中提取股票代码或币种符号"""
        symbols = []
        
        # 韩国股票代码 (6位数字)
        stock_pattern = r'\b\d{6}\b'
        stocks = re.findall(stock_pattern, message)
        symbols.extend(stocks)
        
        # 加密货币符号
        crypto_pattern = r'\b(BTC|ETH|XRP|SOL|ADA|DOGE|BNB|USDT|USDC|MATIC|LINK|DOT|AVAX|SHIB|UNI|ATOM|LTC|ETC|BCH|XLM|비트코인|이더리움|리플)\b'
        cryptos = re.findall(crypto_pattern, message.upper())
        symbols.extend(cryptos)
        
        # KRW-格式
        krw_pattern = r'KRW-[A-Z]+'
        krw_pairs = re.findall(krw_pattern, message.upper())
        symbols.extend(krw_pairs)
        
        return list(set(symbols))
    
    async def _ai_intent_detection(self, message: str) -> Dict[str, Any]:
        """使用AI进行意图识别"""
        
        prompt = f"""你是一个交易助手，需要识别用户的意图。

用户消息: "{message}"

请识别用户的意图，从以下选项中选择一个：
1. BUY_STOCK - 用户想买入股票或加密货币
2. SELL_STOCK - 用户想卖出股票或加密货币
3. ASK_ADVICE - 用户询问交易建议
4. CHECK_POSITION - 用户查询持仓
5. CHECK_PRICE - 用户查询价格
6. PORTFOLIO_ADJUSTMENT - 用户想调整投资组合
7. MARKET_ANALYSIS - 用户想了解市场分析
8. GENERAL - 一般对话

请只回复意图类型和置信度（0-1），格式：
INTENT|CONFIDENCE

例如：BUY_STOCK|0.95"""
        
        try:
            text = await self.model_manager.generate_with_fallback(prompt, 'lightweight')
            if not text:
                text = 'GENERAL|0.5'
            parts = text.strip().split('|')
            
            if len(parts) >= 2:
                intent = parts[0].strip()
                confidence = float(parts[1].strip())
            else:
                intent = 'GENERAL'
                confidence = 0.5
            
            return {
                'intent': intent,
                'confidence': confidence,
                'symbols': self._extract_symbols(message),
                'raw_message': message
            }
            
        except Exception as e:
            logger.error(f"AI意图识别失败: {e}")
            return self._rule_based_intent_detection(message)
    
    async def _handle_buy(self, intent: Dict[str, Any]) -> str:
        """处理买入请求"""
        message = intent['raw_message']
        symbols = intent['symbols']
        
        if not symbols:
            return "请告诉我您想买入哪只股票或加密货币？\n例如：买入三星电子（005930）或买入BTC"
        
        if not self.tracker:
            return "持仓追踪器未初始化，无法记录交易"
        
        # 提取数量和价格
        quantity, price = self._extract_trade_details(message)
        
        if quantity is None or price is None:
            return f"请提供完整的交易信息：\n例如：买入 {symbols[0]} 10股，价格75000"
        
        # 执行买入
        symbol = symbols[0]
        result = self.tracker.open_position(symbol, quantity, price)
        
        if result.get('success', True):
            self._auto_save()
            return f"""买入成功！

交易详情:
股票/币种: {symbol}
数量: {quantity}
价格: {price:,}韩元
总成本: {quantity * price:,}韩元

剩余资金: {self.tracker.cash:,}韩元

持仓已更新！"""
        else:
            return f"买入失败: {result.get('reason', '未知错误')}"
    
    async def _handle_sell(self, intent: Dict[str, Any]) -> str:
        """处理卖出请求"""
        message = intent['raw_message']
        symbols = intent['symbols']
        
        if not symbols:
            return "请告诉我您想卖出哪只股票或加密货币？"
        
        if not self.tracker:
            return "持仓追踪器未初始化"
        
        symbol = symbols[0]
        
        # 检查是否持有
        if symbol not in self.tracker.positions:
            return f"您当前未持有 {symbol}"
        
        # 提取数量和价格
        quantity, price = self._extract_trade_details(message)
        
        position = self.tracker.positions[symbol]
        
        if quantity is None:
            quantity = position['quantity']  # 全部卖出
        
        if price is None:
            return f"请提供卖出价格\n例如：卖出 {symbol} 价格 80000"
        
        # 执行卖出
        result = self.tracker.close_position(symbol, quantity, price)
        
        if result.get('success', True):
            self._auto_save()
            pnl = result.get('pnl', 0)
            pnl_pct = result.get('pnl_pct', 0)
            profit_status = "盈利" if pnl > 0 else "亏损"
            
            return f"""卖出成功！

交易详情:
股票/币种: {symbol}
数量: {quantity}
卖出价格: {price:,}韩元
总收入: {quantity * price:,}韩元

{profit_status}: {abs(pnl):,}韩元 ({pnl_pct:+.2f}%)
当前资金: {self.tracker.cash:,}韩元

持仓已更新！"""
        else:
            return f"卖出失败: {result.get('reason', '未知错误')}"
    
    def _extract_trade_details(self, message: str) -> Tuple[Optional[float], Optional[float]]:
        """从消息中提取交易数量和价格"""
        quantity = None
        price = None
        
        # 提取数量
        qty_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:股|个|枚|coins?|shares?)',
            r'数量[：:]\s*(\d+(?:\.\d+)?)',
            r'买入\s+\d+\s+(\d+(?:\.\d+)?)',
        ]
        
        for pattern in qty_patterns:
            match = re.search(pattern, message)
            if match:
                quantity = float(match.group(1))
                break
        
        # 提取价格
        price_patterns = [
            r'价格[：:]\s*(\d+(?:,\d{3})*(?:\.\d+)?)',
            r'[@＠]\s*(\d+(?:,\d{3})*(?:\.\d+)?)',
            r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:元|won|₩)',
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, message)
            if match:
                price_str = match.group(1).replace(',', '')
                price = float(price_str)
                break
        
        return quantity, price
    
    async def _handle_ask_advice(self, intent: Dict[str, Any]) -> str:
        """处理询问建议"""
        symbols = intent['symbols']
        message = intent.get('raw_message', '')
        
        if not self.ai_advisor:
            return "❌ AI顾问未初始化"
        
        if not symbols:
            # 检测是否是开放式推荐请求
            recommend_keywords = ['推荐', '哪些', '什么股票', '宏观', 'recommend', '추천']
            is_recommend_request = any(kw in message for kw in recommend_keywords)
            
            if is_recommend_request and self.model_manager:
                # 使用AI生成推荐列表（股票+加密货币）
                return await self._generate_market_recommendations(message)
            
            # 分析所有持仓
            if not self.tracker or not self.tracker.positions:
                return "请告诉我您想分析哪只股票或加密货币？\n例如：给我三星电子的建议"
            
            # 分析第一个持仓
            symbol = list(self.tracker.positions.keys())[0]
        else:
            symbol = symbols[0]
        
        # 获取数据并生成建议
        try:
            # 这里应该获取实际数据，暂时使用模拟数据
            advice = await self.ai_advisor.generate_trading_advice(
                symbol=symbol,
                name=symbol,
                current_price=75000,  # 应该获取实际价格
                price_data={'change_pct': 0, 'volume_ratio': 1.0},
                technical_indicators={'rsi': 50},
                sentiment={'score': 0}
            )
            
            return self.ai_advisor.format_advice_for_telegram(advice)
            
        except Exception as e:
            logger.error(f"生成建议失败: {e}")
            return f"❌ 分析失败: {e}"
    
    async def _handle_check_position(self, intent: Dict[str, Any]) -> str:
        """处理查询持仓"""
        if not self.tracker:
            return "持仓追踪器未初始化"
        
        positions = self.tracker.positions
        
        if not positions:
            return "您当前没有持仓"
        
        # 获取当前价格（这里使用简化版本，实际应该从市场获取）
        current_prices = {}
        for symbol, pos in positions.items():
            current_prices[symbol] = pos.get('current_price', pos['avg_entry_price'])
        
        # 检查持仓告警
        alerts = self.tracker.check_position_alerts(current_prices)
        
        # 构建持仓显示
        message = "当前持仓：\n\n"
        
        for symbol, pos in positions.items():
            current_price = current_prices.get(symbol, pos['avg_entry_price'])
            pnl_pct = ((current_price - pos['avg_entry_price']) / pos['avg_entry_price'] * 100)
            
            # 根据盈亏情况显示状态
            if pnl_pct >= 20:
                status = "[已达标]"
            elif pnl_pct >= 15:
                status = "[利好]"
            elif pnl_pct <= -10:
                status = "[止损]"
            elif pnl_pct <= -8:
                status = "[警告]"
            else:
                status = ""
            
            message += f"{status} {symbol}\n"
            message += f"数量: {pos['quantity']} | 成本: ₩{self._fmt_price(pos['avg_entry_price'])}韩元\n"
            message += f"当前: ₩{self._fmt_price(current_price)}韩元 | 盈亏: {pnl_pct:+.2f}%\n\n"
        
        message += f"剩余资金: ₩{self._fmt_price(self.tracker.cash)}韩元\n"
        
        # 添加告警信息
        if alerts:
            message += "\n" + "="*40 + "\n"
            for alert in alerts:
                severity_icon = {
                    "CRITICAL": "!! ",
                    "HIGH": "! ",
                    "SUCCESS": "+ ",
                    "GOOD_NEWS": "++ "
                }.get(alert['severity'], "")
                message += f"{severity_icon}{alert['message']}\n"
        
        return message
    
    async def _handle_check_price(self, intent: Dict[str, Any]) -> str:
        """处理查询价格"""
        symbols = intent['symbols']
        
        if not symbols:
            return "请告诉我您想查询哪个股票或加密货币的价格？"
        
        return f"正在查询 {symbols[0]} 的价格..."
    
    async def _handle_portfolio_adjustment(self, intent: Dict[str, Any]) -> str:
        """处理投资组合调整建议"""
        if not self.tracker or not self.tracker.positions:
            return "您当前没有持仓，无需调整"
        
        if not self.model:
            return "❌ AI模型未初始化，无法提供调仓建议"
        
        # 获取当前持仓信息
        portfolio_info = self._get_portfolio_summary()
        
        prompt = f"""你是一位专业的投资顾问。请基于以下投资组合，提供调整建议：

{portfolio_info}

请提供：
1. 📊 **组合评估**: 当前配置的优缺点
2. 💡 **调整建议**: 具体的买入/卖出建议
3. ⚖️ **风险平衡**: 如何优化风险收益比
4. 🎯 **目标配置**: 建议的理想持仓比例

请用简洁的中文回答，不使用Markdown符号或emoji，总字数不超过200字。"""
        
        try:
            text = await self.model_manager.generate_with_fallback(prompt, 'standard')
            if not text:
                return "❌ 所有AI模型配额已耗尽，请明天再试"
            return f"投资组合调整建议\n\n{text}"
            
        except Exception as e:
            return f"❌ 生成建议失败: {e}"
    
    async def _handle_market_analysis(self, intent: Dict[str, Any]) -> str:
        """处理市场分析请求"""
        if not self.model:
            return "AI模型未初始化"
        
        symbols = intent['symbols']
        
        if symbols:
            prompt = f"【短线交易分析，10小时窗口】请分析 {', '.join(symbols)} 的短线交易机会，包括最佳买入时机和10小时内的目标价位。用简洁的纯文本格式回复，不使用Markdown符号或emoji，不超过150字。"
        else:
            prompt = "【短线交易分析，10小时窗口】请分析当前韩国股市和加密货币市场的短线交易机会，关注日内波动和快速获利机会。用简洁的纯文本格式回复，不使用Markdown符号或emoji，不超过150字。"
        
        try:
            text = await self.model_manager.generate_with_fallback(prompt, 'standard')
            if not text:
                return "❌ 所有AI模型配额已耗尽，请明天再试"
            return f"市场分析\n\n{text}"
            
        except Exception as e:
            return f"❌ 分析失败: {e}"
    
    async def _handle_general_conversation(self, message: str) -> str:
        """处理一般对话"""
        if not self.model:
            return "我是安诚科技 Ancent AI 交易助手。我可以帮您：\n分析股票和加密货币\n提供交易建议\n管理持仓\n查询价格和行情"
        
        # 构建上下文
        context = self._build_conversation_context()
        
        prompt = f"""你是安诚科技 Ancent AI 交易助手，一个专业的股票和加密货币交易顾问。

对话历史:
{context}

用户: {message}

请提供有帮助的回复。如果用户询问交易相关问题，提供专业建议。保持友好和专业。

重要：使用简洁的纯文本格式，不使用Markdown符号或emoji，回复不超过100字。"""
        
        try:
            text = await self.model_manager.generate_with_fallback(prompt, 'standard')
            if not text:
                return "❌ 所有AI模型配额已耗尽，请明天再试"
            return text
            
        except Exception as e:
            return f"❌ 对话失败: {e}"
    
    def _get_portfolio_summary(self) -> str:
        """获取投资组合摘要"""
        if not self.tracker:
            return "无持仓数据"
        
        positions = self.tracker.positions
        summary = f"💰 总资金: ₩{self.tracker.initial_capital:,}\n"
        summary += f"💵 剩余现金: ₩{self.tracker.cash:,}\n\n"
        summary += "📊 持仓明细:\n"
        
        for symbol, pos in positions.items():
            summary += f"  • {symbol}: {pos['quantity']} @ ₩{pos['avg_entry_price']:,}\n"
        
        return summary
    
    def _build_conversation_context(self) -> str:
        """构建对话上下文"""
        if not self.conversation_history:
            return "（新对话）"
        
        # 最近5条对话
        recent = self.conversation_history[-5:]
        context = ""
        
        for item in recent:
            role = "用户" if item['type'] == 'user' else "助手"
            context += f"{role}: {item['message'][:100]}\n"
        
        return context
    
    async def _generate_market_recommendations(self, message: str) -> str:
        """使用AI生成市场推荐（股票+加密货币+美股+港股）"""
        if not self.model_manager:
            return "AI模型未初始化，无法生成推荐"
        
        try:
            # 判断用户要求的市场类型
            crypto_keywords = ['加密', '币', 'crypto', 'bitcoin', 'btc', 'eth', '비트코인']
            stock_keywords = ['韩国股', '韩股', '股票', '股', 'stock', '주식']
            us_keywords = ['美国', '美股', 'us', 'american', 'nasdaq', 'nyse']
            hk_keywords = ['香港', '港股', 'hong kong', 'hk', 'hkex']
            
            wants_crypto = any(kw in message.lower() for kw in crypto_keywords)
            wants_kr_stock = any(kw in message.lower() for kw in stock_keywords)
            wants_us_stock = any(kw in message.lower() for kw in us_keywords)
            wants_hk_stock = any(kw in message.lower() for kw in hk_keywords)
            
            # 如果都没明确说，就推荐所有市场
            if not (wants_crypto or wants_kr_stock or wants_us_stock or wants_hk_stock):
                wants_kr_stock = True
                wants_us_stock = True
                wants_hk_stock = True
                wants_crypto = True
            
            # 使用复杂模型进行深度分析（gemini-3-pro-preview）
            model = self.model_manager.get_model('complex')
            if not model:
                return "无法加载分析模型"
            
            # 构建提示词
            market_types = []
            if wants_kr_stock:
                market_types.append("韩国股票")
            if wants_us_stock:
                market_types.append("美股")
            if wants_hk_stock:
                market_types.append("港股")
            if wants_crypto:
                market_types.append("加密货币")
            
            markets_text = "、".join(market_types)
            
            prompt = f"""你是一个专业的短线交易分析师。用户询问："{message}"

【🔥 最高优先级 - 短线交易策略】
- 这是短线交易分析，买入到卖出时间窗口：不超过10小时
- 所有推荐必须基于短线交易机会，关注日内波动和快速获利
- 重点分析：盘中波动性、成交量异动、短期技术指标（5分钟/15分钟K线）
- 目标：日内交易或隔夜持仓，次日开盘前完成交易

【💰 严格风控要求 - 强制执行】
- 收益目标：每笔交易最低20%收益预期，否则不推荐
- 止损红线：每笔交易亏损不得超过-10%，接近-8%必须告警
- 所有推荐必须有明确的止损位（-10%以内）

请根据2026年2月的市场情况，分析{markets_text}市场并提供短线交易建议。

【重要】输出格式要求：
- 使用简洁的纯文本格式，不要使用Markdown符号（如**、#、-等）
- 不要使用emoji表情符号
- 每个市场推荐1-2只，每只不超过3行
- 总输出不超过400字
- 必须标注：买入时机、目标价位(+20%以上)、止损位(-10%)

"""
            
            if wants_kr_stock:
                prompt += """
韩国股票：推荐1-2只短线机会（收益目标+20%以上，止损-10%）
格式：[代码] 公司名 | 买入价 | 目标价(+20%+) | 止损价(-10%) | 时间窗口
"""
            
            if wants_us_stock:
                prompt += """
美股：推荐1-2只短线机会（收益目标+20%以上，止损-10%）
格式：[符号] 公司名 | 买入价 | 目标价(+20%+) | 止损价(-10%) | 时间窗口
"""
            
            if wants_hk_stock:
                prompt += """
港股：推荐1-2只短线机会（收益目标+20%以上，止损-10%）
格式：[代码] 公司名 | 买入价 | 目标价(+20%+) | 止损价(-10%) | 时间窗口
"""
            
            if wants_crypto:
                prompt += """
加密货币：推荐1-2种短线机会（收益目标+20%以上，止损-10%，24小时交易）
格式：[符号] 币名 | 买入价 | 目标价(+20%+) | 止损价(-10%) | 时间窗口
"""
            
            prompt += """

示例格式（严格风控，纯文本）：
市场概况：波动加大，精选高收益低风险机会。

韩股短线：
[005930] 三星电子 | 买入75000 | 目标90000(+20%) | 止损67500(-10%) | 8小时

美股短线：
[NVDA] 英伟达 | 买入850美元 | 目标1020美元(+20%) | 止损765美元(-10%) | 10小时

港股短线：
[00700] 腾讯控股 | 买入320港元 | 目标384港元(+20%) | 止损288港元(-10%) | 6小时

加密货币短线：
[BTC] 比特币 | 买入50000美元 | 目标60000美元(+20%) | 止损45000美元(-10%) | 8小时

请用中文回复，简洁专业，不使用Markdown或emoji。
重点：每笔推荐必须有20%+收益预期和严格-10%止损，否则不推荐。
"""
            
            logger.info(f"开始生成市场推荐（包含：{markets_text}）")
            
            # 调用Gemini（自动降级）
            result = await self.model_manager.generate_with_fallback(prompt, 'standard')
            if not result:
                return "❌ 所有AI模型配额已耗尽，请明天再试"
            
            # 添加免责声明（纯文本格式）
            result += "\n\n" + "-"*40
            result += "\n免责声明："
            result += "\n以上分析仅供参考，不构成投资建议。"
            result += "\n投资有风险，入市需谨慎。"
            result += "\n请根据自身风险承受能力做出决策。"
            
            logger.info(f"成功生成市场推荐")
            return result
            
        except Exception as e:
            logger.error(f"生成推荐失败: {e}")
            import traceback
            traceback.print_exc()
            return f"❌ 生成推荐失败: {str(e)}"
    
    async def _handle_run_backtest(self, intent: Dict[str, Any]) -> str:
        """
        处理回测请求
        
        Args:
            intent: 意图字典
        
        Returns:
            回测结果报告
        """
        if not BACKTEST_AVAILABLE or not self.backtest_data_fetcher:
            return "❌ 回测功能不可用，请检查回测模块是否安装"
        
        try:
            message = intent.get('raw_message', '')
            symbols = intent.get('symbols', [])
            
            # 如果没有指定股票，使用默认热门股票
            if not symbols:
                symbols = ['005930', '000660', '035420']  # 三星、SK海力士、NAVER
            
            # 提取回测参数
            backtest_params = self._extract_backtest_params(message)
            
            # 默认参数
            start_date = backtest_params.get('start_date', 
                (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
            end_date = backtest_params.get('end_date', 
                datetime.now().strftime('%Y-%m-%d'))
            strategy = backtest_params.get('strategy', 'momentum')
            initial_capital = backtest_params.get('initial_capital', 10000000)
            
            logger.info(f"开始回测: {symbols} ({start_date} ~ {end_date})")
            
            # 获取历史数据
            historical_data = self.backtest_data_fetcher.get_multiple_symbols(
                symbols, start_date, end_date, interval='1d'
            )
            
            if not historical_data:
                return "❌ 无法获取历史数据，请检查股票代码和日期范围"
            
            # 生成交易信号
            signals = self.backtest_data_fetcher.generate_sample_signals(
                symbols, historical_data, strategy=strategy
            )
            
            if not signals:
                return "⚠️ 未生成交易信号，请尝试不同的策略或日期范围"
            
            # 运行回测
            backtest_engine = EnhancedBacktest(
                initial_capital=initial_capital,
                slippage_pct=0.002,
                commission_pct=0.0015
            )
            
            metrics = backtest_engine.run_backtest(
                historical_data=historical_data,
                signals=signals,
                max_position_size=0.2
            )
            
            # 格式化回测报告
            report = self._format_backtest_report(
                metrics, symbols, start_date, end_date, strategy, backtest_engine
            )
            
            return report
        
        except Exception as e:
            logger.error(f"回测失败: {e}")
            import traceback
            traceback.print_exc()
            return f"❌ 回测失败: {str(e)}"
    
    def _extract_backtest_params(self, message: str) -> Dict[str, Any]:
        """从消息中提取回测参数"""
        params = {}
        
        # 提取日期范围
        # 格式: "最近30天", "2024-01-01到2024-02-01"
        if '最近' in message:
            days_match = re.search(r'最近(\d+)天', message)
            if days_match:
                days = int(days_match.group(1))
                params['start_date'] = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                params['end_date'] = datetime.now().strftime('%Y-%m-%d')
        
        date_pattern = r'(\d{4}-\d{2}-\d{2})'
        dates = re.findall(date_pattern, message)
        if len(dates) >= 2:
            params['start_date'] = dates[0]
            params['end_date'] = dates[1]
        elif len(dates) == 1:
            params['end_date'] = dates[0]
            params['start_date'] = (datetime.strptime(dates[0], '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # 提取策略类型
        if '动量' in message or 'momentum' in message.lower():
            params['strategy'] = 'momentum'
        elif '均值' in message or 'mean' in message.lower():
            params['strategy'] = 'mean_reversion'
        elif '突破' in message or 'breakout' in message.lower():
            params['strategy'] = 'breakout'
        
        # 提取初始资金
        capital_pattern = r'(\d+)万'
        capital_match = re.search(capital_pattern, message)
        if capital_match:
            params['initial_capital'] = int(capital_match.group(1)) * 10000
        
        return params
    
    def _format_backtest_report(
        self,
        metrics: Dict[str, Any],
        symbols: List[str],
        start_date: str,
        end_date: str,
        strategy: str,
        backtest_engine
    ) -> str:
        """格式化回测报告"""
        
        # 策略名称映射
        strategy_names = {
            'momentum': '动量策略',
            'mean_reversion': '均值回归策略',
            'breakout': '突破策略'
        }
        strategy_name = strategy_names.get(strategy, strategy)
        
        report = f"""
=== 回测报告 ===

策略：{strategy_name}
标的：{', '.join(symbols)}
周期：{start_date} ~ {end_date}

【资金情况】
初始资金：₩{metrics['initial_capital']:,.0f}
最终资金：₩{metrics['final_capital']:,.0f}
总收益：{metrics['total_return']:+.2f}% (₩{metrics['total_pnl']:+,.0f})

【交易统计】
总交易次数：{metrics['total_trades']}
盈利次数：{metrics['winning_trades']}
亏损次数：{metrics['losing_trades']}
胜率：{metrics['win_rate']:.2f}%

【盈亏分析】
平均盈利：₩{metrics['avg_win']:,.0f}
平均亏损：₩{metrics['avg_loss']:,.0f}
盈亏比：{metrics['profit_factor']:.2f}
最大盈利：₩{metrics['largest_win']:,.0f}
最大亏损：₩{metrics['largest_loss']:,.0f}

【风险指标】
夏普比率：{metrics['sharpe_ratio']:.2f}
最大回撤：{metrics['max_drawdown']:.2f}%
平均持仓时间：{metrics['avg_hold_time_hours']:.1f}小时

【风控执行】
止损触发：{metrics['stop_loss_count']}次
止盈触发：{metrics['take_profit_count']}次
超时平仓：{metrics['time_limit_count']}次
告警触发：{metrics['alerts_triggered']}次

【风控参数】
止损红线：{metrics['risk_params']['stop_loss_pct']}%
收益目标：{metrics['risk_params']['profit_target_pct']}%
最大持仓：{metrics['risk_params']['max_hold_hours']}小时

【总手续费】₩{metrics['total_commission']:,.0f}

"""
        
        # 添加交易明细（最近10笔）
        trade_history = backtest_engine.get_trade_history()
        if trade_history:
            report += "【最近交易明细】\n"
            recent_trades = trade_history[-10:]  # 最近10笔
            for i, trade in enumerate(recent_trades, 1):
                entry_time = trade['entry_time'][:16] if len(trade['entry_time']) > 16 else trade['entry_time']
                exit_reason_emoji = {
                    'STOP_LOSS': '🔴',
                    'TAKE_PROFIT': '✅',
                    'TIME_LIMIT': '⏰',
                    'SIGNAL': '📊',
                    'END_OF_BACKTEST': '🏁'
                }.get(trade['exit_reason'], '❓')
                
                report += f"{i}. {trade['symbol']} | "
                report += f"{entry_time} | "
                report += f"{trade['pnl_pct']:+.2f}% (₩{trade['pnl']:+,.0f}) | "
                report += f"{trade['hold_hours']:.1f}h | "
                report += f"{exit_reason_emoji}{trade['exit_reason']}\n"
        
        report += "\n" + "="*40
        report += "\n提示："
        report += "\n- 回测结果仅供参考，不代表实际交易表现"
        report += "\n- 实际交易中滑点和手续费可能更高"
        report += "\n- 请结合市场环境谨慎决策"
        
        return report
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []
        logger.info("对话历史已清空")


if __name__ == '__main__':
    # 测试
    async def test():
        handler = ConversationHandler()
        
        test_messages = [
            "买入三星电子 10股 价格75000",
            "给我BTC的建议",
            "我当前的持仓怎么样？",
            "三星电子现在多少钱？",
        ]
        
        for msg in test_messages:
            print(f"\n用户: {msg}")
            response = await handler.process_message(msg)
            print(f"助手: {response}")
    
    asyncio.run(test())
