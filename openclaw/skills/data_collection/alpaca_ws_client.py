#!/usr/bin/env python3
"""
Alpaca WebSocket 实时美股价格推送客户端（免费 IEX 数据源）

数据源说明：
  - 端点: wss://stream.data.alpaca.markets/v2/iex
  - 数据: IEX 交易所成交价（覆盖约 70% 的美股成交量，延迟 < 1 秒）
  - 免费账户: 注册即用，无需存款，60次/分钟 REST 补充查询
  - 付费 SIP 源: wss://stream.data.alpaca.markets/v2/sip（全市场 NBBO）

使用方式：
  client = AlpacaWSClient(api_key="...", secret_key="...")
  client.start(symbols=["AAPL", "TSLA", "NVDA"])
  ...
  price_info = client.get_cached_price("AAPL")
  # {"price": 182.5, "change_pct": +1.2, "volume": 123456, "ts": 1700000000}
"""

import asyncio
import json
import os
import time
from typing import Dict, List, Optional, Set
from loguru import logger

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets 未安装，请运行: pip install websockets")

# 免费 IEX 端点（全市场 SIP 需付费）
_WS_URL_IEX = "wss://stream.data.alpaca.markets/v2/iex"
_WS_URL_SIP = "wss://stream.data.alpaca.markets/v2/sip"

# 缓存过期时间（超过此时间的价格视为陈旧）
_CACHE_STALE_SEC = 60


class AlpacaWSClient:
    """
    Alpaca WebSocket 实时价格推送客户端。

    架构：
      - 后台 asyncio Task 维持 WebSocket 长连接
      - 收到 trade/quote 推送后写入内存字典 _price_cache
      - get_cached_price() 直接读缓存，无网络 IO，毫秒级响应
      - 断线自动重连（指数退避，最多 60 秒）
    """

    def __init__(self, api_key: str, secret_key: str, use_sip: bool = False):
        """
        Args:
            api_key:    Alpaca API Key（从 https://alpaca.markets 获取，免费）
            secret_key: Alpaca Secret Key
            use_sip:    True = 全市场 SIP（需付费），False = IEX（免费）
        """
        self.api_key    = api_key
        self.secret_key = secret_key
        self.ws_url     = _WS_URL_SIP if use_sip else _WS_URL_IEX

        # 价格缓存: symbol -> {price, change_pct, volume, high, low, open, ts, source}
        self._price_cache: Dict[str, dict] = {}
        # 前收盘价（用于计算 change_pct）: symbol -> float
        self._prev_close: Dict[str, float] = {}
        # 当日累积成交量: symbol -> int
        self._day_volume: Dict[str, int]   = {}

        self._subscribed: Set[str] = set()
        self._pending_subscribe: Set[str] = set()   # 已加入但还未发送的
        self._ws_ref    = None    # 当前 websocket 连接引用
        self._running   = False
        self._task: Optional[asyncio.Task] = None
        self._reconnect_delay = 2  # 初始重连延迟（秒）

        self.available = bool(
            api_key and secret_key and api_key != "your_alpaca_api_key" and WEBSOCKETS_AVAILABLE
        )

    # ─────────────────────────────────────────────────────────────────────
    # 公开接口
    # ─────────────────────────────────────────────────────────────────────

    def start(self, symbols: List[str]) -> None:
        """
        启动后台 WebSocket 任务并订阅给定股票列表。
        必须在 asyncio 事件循环内调用（e.g. await loop.run_in_executor 外部不可用）。
        """
        if not self.available:
            logger.warning(
                "Alpaca WS 不可用：缺少 API Key 或 websockets 库。"
                " 请在 .env 配置 ALPACA_API_KEY / ALPACA_SECRET_KEY，"
                " 并运行 pip install websockets"
            )
            return

        self._subscribed = set(s.upper() for s in symbols)
        self._running    = True
        try:
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._run_forever())
            logger.info(
                f"✅ Alpaca WebSocket 已启动（{self.ws_url.split('/')[-1].upper()} 源），"
                f"订阅 {len(self._subscribed)} 只美股"
            )
        except RuntimeError as e:
            logger.error(f"创建 Alpaca WS 任务失败: {e}")

    def stop(self) -> None:
        """停止 WebSocket 后台任务"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Alpaca WebSocket 已停止")

    def subscribe(self, symbols: List[str]) -> None:
        """
        动态追加订阅（运行中也可调用）。
        若 WS 已连接，立即发送订阅消息；否则加入待发队列。
        """
        new = set(s.upper() for s in symbols) - self._subscribed
        if not new:
            return
        self._subscribed      |= new
        self._pending_subscribe |= new
        asyncio.ensure_future(self._send_subscribe(list(new)))

    def get_cached_price(self, symbol: str) -> Optional[dict]:
        """
        从缓存读取最新价格。

        Returns:
            dict 或 None（若缓存不存在 / 已过期）
            dict 格式:
              {price, change_pct, volume, high, low, open, ts, source}
        """
        entry = self._price_cache.get(symbol.upper())
        if not entry:
            return None
        if time.time() - entry["ts"] > _CACHE_STALE_SEC:
            return None   # 已过期，让调用方回退到 REST
        return entry

    def set_prev_close(self, symbol: str, prev_close: float) -> None:
        """
        设置前收盘价（由 USHKStockFetcher 在首次 Finnhub REST 查询后写入）。
        供后续实时成交价计算 change_pct 使用。
        """
        self._prev_close[symbol.upper()] = prev_close

    @property
    def is_running(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    @property
    def cached_symbols(self) -> List[str]:
        """返回当前有缓存数据的股票列表"""
        return list(self._price_cache.keys())

    # ─────────────────────────────────────────────────────────────────────
    # 内部：连接 / 重连循环
    # ─────────────────────────────────────────────────────────────────────

    async def _run_forever(self) -> None:
        """带指数退避的永久重连循环"""
        while self._running:
            try:
                await self._connect_and_listen()
                self._reconnect_delay = 2   # 正常断开后重置
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(
                    f"Alpaca WS 断线: {e}，{self._reconnect_delay}秒后重连"
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)

    async def _connect_and_listen(self) -> None:
        """建立连接、认证、订阅、接收消息"""
        import websockets as _ws

        async with _ws.connect(
            self.ws_url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            self._ws_ref = ws

            # ── 1. 等待欢迎消息 ──
            raw = await ws.recv()
            msgs = json.loads(raw) if isinstance(raw, str) else raw
            logger.debug(f"Alpaca WS 欢迎: {msgs}")

            # ── 2. 认证 ──
            await ws.send(json.dumps({
                "action": "auth",
                "key":    self.api_key,
                "secret": self.secret_key,
            }))
            raw = await ws.recv()
            resp = json.loads(raw) if isinstance(raw, str) else raw
            resp_list = resp if isinstance(resp, list) else [resp]
            if not any(m.get("msg") == "authenticated" for m in resp_list):
                logger.error(f"Alpaca WS 认证失败: {resp}")
                return
            logger.info("✅ Alpaca WebSocket 认证成功")
            self._reconnect_delay = 2

            # ── 3. 订阅 ──
            syms = list(self._subscribed)
            if syms:
                await self._send_subscribe_on(ws, syms)

            # ── 4. 消息循环 ──
            async for raw in ws:
                if not self._running:
                    break
                try:
                    msgs = json.loads(raw) if isinstance(raw, str) else raw
                    for msg in (msgs if isinstance(msgs, list) else [msgs]):
                        self._handle_message(msg)
                except Exception as e:
                    logger.debug(f"Alpaca WS 消息处理错误: {e}")

            self._ws_ref = None

    async def _send_subscribe(self, symbols: List[str]) -> None:
        """向已连接的 WS 发送订阅请求（动态追加时使用）"""
        if self._ws_ref:
            await self._send_subscribe_on(self._ws_ref, symbols)

    @staticmethod
    async def _send_subscribe_on(ws, symbols: List[str]) -> None:
        msg = json.dumps({
            "action": "subscribe",
            "trades": symbols,
            "quotes": symbols,
        })
        await ws.send(msg)
        preview = symbols[:5]
        suffix  = f"...共{len(symbols)}只" if len(symbols) > 5 else ""
        logger.info(f"Alpaca WS 已订阅: {preview}{suffix}")

    # ─────────────────────────────────────────────────────────────────────
    # 内部：消息处理
    # ─────────────────────────────────────────────────────────────────────

    def _handle_message(self, msg: dict) -> None:
        """处理单条推送消息"""
        t   = msg.get("T")      # 消息类型：t=trade, q=quote, b=bar
        sym = msg.get("S", "").upper()
        if not sym:
            return

        if t == "t":
            # ── trade（实际成交，最精确）──
            price  = float(msg.get("p", 0))
            size   = int(msg.get("s", 0))
            if price <= 0:
                return
            prev_close = self._prev_close.get(sym, price)
            change_pct = (price - prev_close) / prev_close * 100 if prev_close else 0
            # 累积当日成交量
            self._day_volume[sym] = self._day_volume.get(sym, 0) + size
            self._price_cache[sym] = {
                "price":      price,
                "change_pct": round(change_pct, 4),
                "volume":     self._day_volume[sym],
                "ts":         time.time(),
                "source":     "Alpaca-WS-Trade",
            }

        elif t == "q":
            # ── quote（买卖盘中间价，trade 更新前的近似值）──
            bp = float(msg.get("bp", 0))   # bid price
            ap = float(msg.get("ap", 0))   # ask price
            if bp <= 0 or ap <= 0:
                return
            # 只有当前缓存比 _CACHE_STALE_SEC/4 更旧时才用 quote 补充
            existing = self._price_cache.get(sym)
            if existing and (time.time() - existing["ts"]) < _CACHE_STALE_SEC / 4:
                return  # trade 数据还新鲜，不用 quote 覆盖
            mid = (bp + ap) / 2
            prev_close = self._prev_close.get(sym, mid)
            change_pct = (mid - prev_close) / prev_close * 100 if prev_close else 0
            self._price_cache[sym] = {
                "price":      round(mid, 4),
                "change_pct": round(change_pct, 4),
                "volume":     self._day_volume.get(sym, 0),
                "ts":         time.time(),
                "source":     "Alpaca-WS-Quote",
            }

        elif t == "b":
            # ── bar（分钟/日线 OHLCV，可选）──
            close = float(msg.get("c", 0))
            if close <= 0:
                return
            prev_close = self._prev_close.get(sym, close)
            change_pct = (close - prev_close) / prev_close * 100 if prev_close else 0
            self._price_cache[sym] = {
                "price":      close,
                "change_pct": round(change_pct, 4),
                "volume":     int(msg.get("v", 0)),
                "high":       float(msg.get("h", 0)),
                "low":        float(msg.get("l", 0)),
                "open":       float(msg.get("o", 0)),
                "ts":         time.time(),
                "source":     "Alpaca-WS-Bar",
            }


# ─────────────────────────────────────────────────────────────────────────────
# 简单测试（直接执行时可用）
# ─────────────────────────────────────────────────────────────────────────────

async def _test():
    api_key    = os.getenv("ALPACA_API_KEY", "")
    secret_key = os.getenv("ALPACA_SECRET_KEY", "")

    if not api_key or api_key == "your_alpaca_api_key":
        print("❌ 请先在 .env 配置 ALPACA_API_KEY / ALPACA_SECRET_KEY")
        print("   注册地址：https://alpaca.markets（完全免费，无需存款）")
        return

    client = AlpacaWSClient(api_key, secret_key)
    symbols = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN"]
    client.start(symbols)

    print(f"⏳ 等待 5 秒接收推送...\n")
    await asyncio.sleep(5)

    print(f"{'代码':<8} {'价格':>10} {'涨跌':>8} {'成交量':>12} {'来源'}")
    print("-" * 55)
    for sym in symbols:
        entry = client.get_cached_price(sym)
        if entry:
            print(
                f"{sym:<8} ${entry['price']:>9.2f} "
                f"{entry['change_pct']:>+7.2f}% "
                f"{entry['volume']:>12,} "
                f"{entry['source']}"
            )
        else:
            print(f"{sym:<8} 暂无数据（市场可能已收盘）")

    client.stop()


if __name__ == "__main__":
    asyncio.run(_test())
