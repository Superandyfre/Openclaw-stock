"""
K线与交易量数据获取器
数据源：
  - 韩股：pykrx（KRX 韩国交易所官方数据，等同于 키움증권 실시간 데이터）
  - 美股：Finnhub quote API（OHLC + 涨跌幅，免费版）
支持：日K线 OHLCV、资金流向（机构/外资/散户）、成交量排名
"""
import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

try:
    from pykrx import stock as krx_stock
    PYKRX_AVAILABLE = True
except ImportError:
    PYKRX_AVAILABLE = False
    logger.warning("pykrx 未安装，韩股K线功能不可用")

try:
    import finnhub as _finnhub_mod
    FINNHUB_AVAILABLE = True
except ImportError:
    FINNHUB_AVAILABLE = False
    logger.warning("finnhub 未安装，美股K线功能不可用")


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")

def _ndays_ago(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).strftime("%Y%m%d")


class KlineFetcher:
    """K线与交易量数据获取器（韩股: KRX/pykrx，美股: Finnhub quote）"""

    def __init__(self, finnhub_api_key: str = None):
        self.available = PYKRX_AVAILABLE
        if self.available:
            logger.info("✅ KlineFetcher 初始化成功（数据源：KRX/pykrx）")
        else:
            logger.warning("⚠️ KlineFetcher 不可用（请 pip install pykrx）")

        # 美股数据：Finnhub
        self._finnhub_client = None
        api_key = finnhub_api_key or os.getenv('FINNHUB_API_KEY')
        if FINNHUB_AVAILABLE and api_key:
            try:
                self._finnhub_client = _finnhub_mod.Client(api_key=api_key)
                logger.info("✅ KlineFetcher 美股支持已启用（Finnhub quote API）")
            except Exception as e:
                logger.warning(f"Finnhub 初始化失败: {e}")

    @staticmethod
    def _is_us_stock(symbol: str) -> bool:
        """判断是否是美股代码（纯字母且非加密货币前缀）"""
        s = symbol.upper()
        if s.startswith('KRW-') or s.startswith('BTC') or s.startswith('ETH'):
            return False
        if symbol.isdigit():
            return False
        if symbol.isalpha() and len(symbol) <= 5:
            return True
        return False

    async def get_ohlcv(self, symbol: str, days: int = 20) -> Optional[dict]:
        """
        获取K线数据（日线）
        - 6位纯数字 → 韩股 pykrx
        - 纯字母 ≤5位 → 美股 Finnhub
        """
        if self._is_us_stock(symbol):
            return await self._get_ohlcv_us(symbol)
        return await self._get_ohlcv_kr(symbol, days)

    async def _get_ohlcv_us(self, symbol: str) -> Optional[dict]:
        """
        获取美股当日 OHLC（via Finnhub quote，免费版，无历史K线/成交量）
        返回字段与韩股保持一致（部分字段为 None/0）
        """
        if not self._finnhub_client:
            return None
        try:
            def _fetch():
                return self._finnhub_client.quote(symbol.upper())

            q = await asyncio.to_thread(_fetch)
            if not q or q.get('c', 0) == 0:
                return None

            return {
                'symbol': symbol.upper(),
                'latest_close': q['c'],
                'latest_open': q['o'],
                'latest_high': q['h'],
                'latest_low': q['l'],
                'latest_volume': 0,          # 免费版不提供成交量
                'change_pct': round(q.get('dp', 0), 2),
                'prev_close': q.get('pc', q['c']),
                'vol_5d_avg': 0,
                'vol_ratio': 0.0,
                'candles': [],
                '_source': 'finnhub',
            }
        except Exception as e:
            logger.error(f"Finnhub K线获取失败 {symbol}: {e}")
            return None

    async def _get_ohlcv_kr(self, symbol: str, days: int = 20) -> Optional[dict]:
        """
        获取韩股 K 线数据（日线）
        返回最近 N 根 K 线的 OHLCV + 涨跌幅
        """
        if not self.available:
            return None
        try:
            end = _today()
            start = _ndays_ago(days + 10)  # 多取几天防节假日空缺

            def _fetch():
                df = krx_stock.get_market_ohlcv(start, end, symbol)
                return df.tail(days)

            df = await asyncio.to_thread(_fetch)
            if df.empty:
                return None

            # 最新一根
            latest = df.iloc[-1]
            prev_close = df.iloc[-2]['종가'] if len(df) >= 2 else latest['종가']

            # 5日均量
            vol_5d_avg = int(df['거래량'].tail(5).mean())

            rows = []
            for date, row in df.tail(10).iterrows():
                rows.append({
                    'date': str(date)[:10],
                    'open': int(row['시가']),
                    'high': int(row['고가']),
                    'low': int(row['저가']),
                    'close': int(row['종가']),
                    'volume': int(row['거래량']),
                    'change_pct': round(float(row['등락률']), 2)
                })

            return {
                'symbol': symbol,
                'latest_close': int(latest['종가']),
                'latest_open': int(latest['시가']),
                'latest_high': int(latest['고가']),
                'latest_low': int(latest['저가']),
                'latest_volume': int(latest['거래량']),
                'change_pct': round(float(latest['등락률']), 2),
                'prev_close': int(prev_close),
                'vol_5d_avg': vol_5d_avg,
                'vol_ratio': round(int(latest['거래량']) / vol_5d_avg, 2) if vol_5d_avg else 1.0,
                'candles': rows
            }
        except Exception as e:
            logger.error(f"K线获取失败 {symbol}: {e}")
            return None

    async def get_investor_flow(self, symbol: str) -> Optional[dict]:
        """
        获取当日资金流向（机构 / 外资 / 散户）
        """
        if not self.available:
            return None
        try:
            today = _today()

            def _fetch():
                return krx_stock.get_market_trading_volume_by_date(today, today, symbol)

            df = await asyncio.to_thread(_fetch)
            if df.empty:
                return None

            row = df.iloc[0]
            inst   = int(row.get('기관합계', 0))
            retail = int(row.get('개인', 0))
            foreign = int(row.get('외국인합계', 0))

            # 正数=净买入，负数=净卖出
            dominant = '机构' if inst > 0 and inst > foreign else \
                       '外资' if foreign > 0 else \
                       '散户' if retail > 0 else '无明显主力'

            return {
                'symbol': symbol,
                'date': today,
                'institutional': inst,
                'retail': retail,
                'foreign': foreign,
                'dominant_buyer': dominant
            }
        except Exception as e:
            logger.error(f"资金流向获取失败 {symbol}: {e}")
            return None

    async def get_volume_leaders(self, top_n: int = 10) -> list:
        """
        获取当日韩股成交量排行榜
        """
        if not self.available:
            return []
        try:
            today = _today()

            def _fetch():
                df = krx_stock.get_market_ohlcv(today, today, market='KOSPI')
                df = df.sort_values('거래량', ascending=False).head(top_n)
                return df

            df = await asyncio.to_thread(_fetch)
            result = []
            for ticker, row in df.iterrows():
                name = krx_stock.get_market_ticker_name(ticker)
                result.append({
                    'symbol': ticker,
                    'name': name,
                    'close': int(row['종가']),
                    'volume': int(row['거래량']),
                    'change_pct': round(float(row['등락률']), 2)
                })
            return result
        except Exception as e:
            logger.error(f"成交量排行获取失败: {e}")
            return []

    def format_kline_summary(self, data: dict, flow: Optional[dict] = None) -> str:
        """格式化 K 线摘要为可读文本"""
        if not data:
            return "❌ 无法获取K线数据"

        s = data
        is_us = s.get('_source') == 'finnhub'

        lines = [
            f"📊 {s['symbol']} K线摘要",
            f"收盘 ${s['latest_close']:,.2f}  涨跌 {s['change_pct']:+.2f}%" if is_us
            else f"收盘 ₩{s['latest_close']:,}  涨跌 {s['change_pct']:+.2f}%",
        ]

        if is_us:
            lines.append(f"今日  开{s['latest_open']:,.2f} 高{s['latest_high']:,.2f} 低{s['latest_low']:,.2f}  前收{s['prev_close']:,.2f}")
            lines.append("（美股免费数据源不含历史K线与成交量，仅当日OHLC）")
        else:
            lines.append(f"今日  开{s['latest_open']:,} 高{s['latest_high']:,} 低{s['latest_low']:,}")
            if s['vol_5d_avg']:
                lines.append(f"成交量 {s['latest_volume']:,}股  5日均量 {s['vol_5d_avg']:,}股")
                if s['vol_ratio'] >= 2.0:
                    lines.append("⚡ 成交量是5日均量的{:.1f}倍（异常放量）".format(s['vol_ratio']))
                elif s['vol_ratio'] >= 1.5:
                    lines.append("📈 成交量高于均量{:.1f}倍".format(s['vol_ratio']))
                elif s['vol_ratio'] <= 0.5:
                    lines.append("📉 成交量明显萎缩（{:.1f}倍均量）".format(s['vol_ratio']))

            if flow:
                inst_str    = f"机构{'买' if flow['institutional']>0 else '卖'} {abs(flow['institutional']):,}"
                foreign_str = f"外资{'买' if flow['foreign']>0 else '卖'} {abs(flow['foreign']):,}"
                retail_str  = f"散户{'买' if flow['retail']>0 else '卖'} {abs(flow['retail']):,}"
                lines.append(f"资金流向: {inst_str} | {foreign_str} | {retail_str}")
                lines.append(f"主力: {flow['dominant_buyer']}")

        return "\n".join(lines)
