#!/usr/bin/env python3
"""
富途牛牛（FUTU）港股实时行情客户端

架构说明：
  FutuOpenD（本地守护进程）↔ FUTU 服务器 ↔ 港交所（HKEX）
  Python SDK ──────────────→ FutuOpenD（TCP 11111 端口）

  本模块在后台线程中运行 FUTU SDK，通过回调实时更新内存缓存，
  业务层调用 get_cached_price() 直接读缓存，延迟 < 1 秒。

使用前提：
  1. 安装 FutuOpenD：https://www.futunn.com/download/openAPI
  2. 启动 FutuOpenD（默认监听 127.0.0.1:11111）
  3. 安装 Python SDK：pip install futu-api
  4. 在 .env 配置 FUTU_OPEND_HOST / FUTU_OPEND_PORT（可选，默认本地）

代码格式：
  港股 → 'HK.00700'（腾讯）、'HK.09988'（阿里）
  输入可以是 '00700', '0700', '700', '0700.HK'，内部自动转换
"""

import os
import threading
import time
from typing import Dict, List, Optional
from loguru import logger

try:
    import futu as ft
    FUTU_AVAILABLE = True
except ImportError:
    FUTU_AVAILABLE = False
    logger.warning("futu-api 未安装，请运行: pip install futu-api")

# 缓存过期时间（超过此时间视为陈旧，回退 yfinance）
_CACHE_STALE_SEC = 60


def _to_futu_code(symbol: str) -> str:
    """将各种港股代码格式统一转成 FUTU 格式 'HK.XXXXX'"""
    s = symbol.upper().replace('.HK', '').replace('HK.', '').replace('HK', '', 1).lstrip('0') or '0'
    return f"HK.{s.zfill(5)}"


def _from_futu_code(futu_code: str) -> str:
    """HK.00700 → 00700"""
    return futu_code.replace('HK.', '')


class _QuoteHandler(ft.StockQuoteHandlerBase if FUTU_AVAILABLE else object):
    """FUTU 实时报价回调（逐笔快照，约 3 秒一次推送）"""

    def __init__(self, cache: dict, prev_close_map: dict):
        if FUTU_AVAILABLE:
            super().__init__()
        self._cache         = cache
        self._prev_close    = prev_close_map

    def on_recv_rsp(self, rsp_str):
        try:
            ret, data = super().on_recv_rsp(rsp_str)
            if ret != ft.RET_OK or data is None or data.empty:
                return ret, data
            for _, row in data.iterrows():
                code      = row.get('code', '')           # HK.00700
                price     = float(row.get('last_price', 0) or row.get('cur_price', 0))
                if price <= 0:
                    continue
                prev      = self._prev_close.get(code, price)
                chg_pct   = (price - prev) / prev * 100 if prev else 0
                self._cache[code] = {
                    'price':      price,
                    'change_pct': round(chg_pct, 4),
                    'volume':     int(row.get('volume', 0) or 0),
                    'high':       float(row.get('high_price', 0) or 0),
                    'low':        float(row.get('low_price', 0) or 0),
                    'open':       float(row.get('open_price', 0) or 0),
                    'name':       str(row.get('stock_name', code)),
                    'ts':         time.time(),
                    'source':     'FUTU-WS',
                }
            return ret, data
        except Exception as e:
            logger.debug(f"[FUTU] QuoteHandler 处理异常: {e}")
            return ft.RET_ERROR, None


class _TickerHandler(ft.TickerHandlerBase if FUTU_AVAILABLE else object):
    """FUTU 逐笔成交回调（每笔真实成交立即推送，延迟最低）"""

    def __init__(self, cache: dict, prev_close_map: dict):
        if FUTU_AVAILABLE:
            super().__init__()
        self._cache      = cache
        self._prev_close = prev_close_map

    def on_recv_rsp(self, rsp_str):
        try:
            ret, data = super().on_recv_rsp(rsp_str)
            if ret != ft.RET_OK or data is None or data.empty:
                return ret, data
            for _, row in data.iterrows():
                code  = row.get('code', '')
                price = float(row.get('price', 0))
                if price <= 0:
                    continue
                prev  = self._prev_close.get(code, price)
                chg_pct = (price - prev) / prev * 100 if prev else 0
                existing = self._cache.get(code, {})
                self._cache[code] = {
                    'price':      price,
                    'change_pct': round(chg_pct, 4),
                    'volume':     int(row.get('volume', existing.get('volume', 0)) or 0),
                    'high':       existing.get('high', 0),
                    'low':        existing.get('low', 0),
                    'open':       existing.get('open', 0),
                    'name':       existing.get('name', code),
                    'ts':         time.time(),
                    'source':     'FUTU-WS-Ticker',
                }
            return ret, data
        except Exception as e:
            logger.debug(f"[FUTU] TickerHandler 处理异常: {e}")
            return ft.RET_ERROR, None


class FutuHKClient:
    """
    富途港股实时行情客户端。

    接口设计与 AlpacaWSClient 保持一致，方便 USHKStockFetcher 统一调用。
    """

    def __init__(self, host: str = '127.0.0.1', port: int = 11111):
        self.host = host
        self.port = port

        self._price_cache:   Dict[str, dict]  = {}   # futu_code → info
        self._prev_close:    Dict[str, float] = {}   # futu_code → prev_close
        self._subscribed:    List[str]        = []   # futu_code 列表
        self._quote_ctx = None
        self._running   = False
        self._thread:   Optional[threading.Thread] = None

        self.available = FUTU_AVAILABLE

    # ─────────────────────────────────────────────────────────
    # 公开接口
    # ─────────────────────────────────────────────────────────

    def start(self, symbols: List[str]) -> None:
        """
        启动后台线程，连接 FutuOpenD 并订阅港股行情。

        Args:
            symbols: 港股代码列表，支持 '00700'/'0700.HK'/'HK.00700' 等格式
        """
        if not self.available:
            logger.warning(
                "futu-api 未安装。请运行: pip install futu-api\n"
                "并下载 FutuOpenD: https://www.futunn.com/download/openAPI"
            )
            return
        if self._running:
            logger.info("FUTU 客户端已在运行")
            return

        self._subscribed = [_to_futu_code(s) for s in symbols]
        self._running = True
        self._thread  = threading.Thread(
            target=self._run, daemon=True, name="FutuHKClient"
        )
        self._thread.start()
        logger.info(
            f"✅ FutuHKClient 已启动（{self.host}:{self.port}），"
            f"订阅 {len(self._subscribed)} 只港股"
        )

    def stop(self) -> None:
        """停止客户端，关闭 FutuOpenD 连接"""
        self._running = False
        if self._quote_ctx:
            try:
                self._quote_ctx.close()
            except Exception:
                pass
            self._quote_ctx = None
        logger.info("FutuHKClient 已停止")

    def subscribe(self, symbols: List[str]) -> None:
        """动态追加订阅"""
        new_codes = [_to_futu_code(s) for s in symbols]
        new_codes = [c for c in new_codes if c not in self._subscribed]
        if not new_codes or not self._quote_ctx:
            return
        self._subscribed.extend(new_codes)
        ret, err = self._quote_ctx.subscribe(
            new_codes,
            [ft.SubType.QUOTE, ft.SubType.TICKER],
            subscribe_push=True,
        )
        if ret == ft.RET_OK:
            logger.info(f"[FUTU] 追加订阅: {new_codes}")
        else:
            logger.warning(f"[FUTU] 追加订阅失败: {err}")

    def get_cached_price(self, symbol: str) -> Optional[dict]:
        """
        从缓存读取最新价格。

        Args:
            symbol: 任意格式港股代码，如 '00700'、'0700.HK'

        Returns:
            dict 或 None（缓存不存在 / 已过期）
            dict: {price, change_pct, volume, high, low, open, name, ts, source}
        """
        code  = _to_futu_code(symbol)
        entry = self._price_cache.get(code)
        if not entry:
            return None
        if time.time() - entry['ts'] > _CACHE_STALE_SEC:
            return None
        return entry

    def get_snapshot(self, symbol: str) -> Optional[dict]:
        """
        主动拉取最新快照（一次性 REST 风格查询，无需订阅）。
        用于首次查询时快速填充缓存。
        """
        if not self._quote_ctx:
            return None
        code = _to_futu_code(symbol)
        try:
            ret, data = self._quote_ctx.get_market_snapshot([code])
            if ret != ft.RET_OK or data is None or data.empty:
                return None
            row   = data.iloc[0]
            price = float(row.get('last_price', 0) or row.get('cur_price', 0))
            if price <= 0:
                return None
            prev_close = float(row.get('prev_close_price', price) or price)
            self._prev_close[code] = prev_close
            chg_pct = (price - prev_close) / prev_close * 100 if prev_close else 0
            entry = {
                'price':      price,
                'change_pct': round(chg_pct, 4),
                'volume':     int(row.get('volume', 0) or 0),
                'high':       float(row.get('high_price', 0) or 0),
                'low':        float(row.get('low_price', 0) or 0),
                'open':       float(row.get('open_price', 0) or 0),
                'name':       str(row.get('stock_name', code)),
                'ts':         time.time(),
                'source':     'FUTU-Snapshot',
            }
            self._price_cache[code] = entry
            return entry
        except Exception as e:
            logger.debug(f"[FUTU] get_snapshot {symbol} 失败: {e}")
            return None

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    # ─────────────────────────────────────────────────────────
    # 内部：后台线程
    # ─────────────────────────────────────────────────────────

    def _run(self) -> None:
        """后台线程：连接 FutuOpenD，注册回调，保持运行"""
        reconnect_delay = 3
        while self._running:
            try:
                self._connect_and_listen()
                reconnect_delay = 3
            except Exception as e:
                logger.warning(
                    f"[FUTU] 连接断开: {e}，{reconnect_delay}秒后重连"
                )
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)

    def _connect_and_listen(self) -> None:
        ctx = ft.OpenQuoteContext(host=self.host, port=self.port)
        self._quote_ctx = ctx

        # 注册回调
        ctx.set_handler(_QuoteHandler(self._price_cache, self._prev_close))
        ctx.set_handler(_TickerHandler(self._price_cache, self._prev_close))

        # 获取前收盘价（通过快照）并写入 prev_close
        if self._subscribed:
            ret, data = ctx.get_market_snapshot(self._subscribed)
            if ret == ft.RET_OK and data is not None and not data.empty:
                for _, row in data.iterrows():
                    code = row.get('code', '')
                    pc   = float(row.get('prev_close_price', 0) or 0)
                    if code and pc:
                        self._prev_close[code] = pc

        # 订阅实时推送
        if self._subscribed:
            ret, err = ctx.subscribe(
                self._subscribed,
                [ft.SubType.QUOTE, ft.SubType.TICKER],
                subscribe_push=True,
            )
            if ret == ft.RET_OK:
                logger.info(
                    f"[FUTU] 已订阅 {len(self._subscribed)} 只港股实时行情推送"
                )
            else:
                logger.warning(f"[FUTU] 订阅失败: {err}")

        logger.info("✅ FutuOpenD 连接成功，等待行情推送...")

        # 保持线程存活
        while self._running:
            time.sleep(1)

        ctx.close()
        self._quote_ctx = None


# ─────────────────────────────────────────────────────────────────────────────
# 简单测试
# ─────────────────────────────────────────────────────────────────────────────

def _test():
    host = os.getenv('FUTU_OPEND_HOST', '127.0.0.1')
    port = int(os.getenv('FUTU_OPEND_PORT', '11111'))

    if not FUTU_AVAILABLE:
        print("❌ futu-api 未安装，请运行: pip install futu-api")
        return

    client = FutuHKClient(host=host, port=port)
    symbols = ['00700', '09988', '01810', '03690', '02318']
    client.start(symbols)

    print("⏳ 等待 5 秒接收推送...")
    time.sleep(5)

    print(f"\n{'代码':<8} {'价格':>10} {'涨跌':>8} {'成交量':>12} {'来源'}")
    print("-" * 55)
    for sym in symbols:
        entry = client.get_cached_price(sym)
        if entry:
            print(
                f"{sym:<8} HK${entry['price']:>8.2f} "
                f"{entry['change_pct']:>+7.2f}% "
                f"{entry['volume']:>12,} "
                f"{entry['source']}"
            )
        else:
            # 尝试主动快照
            snap = client.get_snapshot(sym)
            if snap:
                print(
                    f"{sym:<8} HK${snap['price']:>8.2f} "
                    f"{snap['change_pct']:>+7.2f}% "
                    f"{snap['volume']:>12,} "
                    f"{snap['source']}"
                )
            else:
                print(f"{sym:<8} 暂无数据（检查 FutuOpenD 是否已启动）")

    client.stop()


if __name__ == '__main__':
    _test()
