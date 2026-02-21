"""
免费数据源连接器

整合多个免费API：
1. Binance Spot API - 现货交易数据
2. Alternative.me - 恐慌贪婪指数
3. CoinGecko - 加密货币数据
4. FRED - 美联储宏观数据
5. Yahoo Finance - 传统市场数据
6. DeFiLlama - DeFi项目数据
7. GitHub - 项目开发活跃度
"""
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import time
from loguru import logger


class FreeDataSourceConnector:
    """
    免费数据源连接器
    
    所有API均免费使用（无社媒API）
    """
    
    def __init__(self):
        """初始化连接器"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
        
        # API端点
        self.binance_base = "https://api.binance.com"
        self.fear_greed_url = "https://api.alternative.me/fng/"
        self.coingecko_base = "https://api.coingecko.com/api/v3"
        self.fred_base = "https://api.stlouisfed.org/fred"
        self.defi_llama_base = "https://api.llama.fi"
        self.github_base = "https://api.github.com"
        
        # 速率限制
        self.last_request_time = {}
        self.rate_limits = {
            'binance': 0.1,      # 10次/秒
            'coingecko': 1.5,    # 50次/分钟
            'fear_greed': 1.0,   # 保守估计
            'fred': 0.1,         # 较宽松
            'defillama': 0.5,    # 保守估计
            'github': 1.0,       # 60次/小时（未认证）
            'yfinance': 0.5      # 保守估计
        }
        
        logger.info("✅ FreeDataSourceConnector 初始化成功")
    
    def _rate_limit(self, source: str):
        """速率限制"""
        if source in self.last_request_time:
            elapsed = time.time() - self.last_request_time[source]
            wait_time = self.rate_limits.get(source, 1.0)
            if elapsed < wait_time:
                time.sleep(wait_time - elapsed)
        
        self.last_request_time[source] = time.time()
    
    # ==================== Binance Spot API ====================
    
    def get_binance_orderbook(
        self,
        symbol: str,
        limit: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        获取Binance订单簿
        
        Args:
            symbol: 交易对，如 'BTCUSDT'
            limit: 深度档位 (5, 10, 20, 50, 100, 500, 1000, 5000)
        
        Returns:
            订单簿数据
        """
        self._rate_limit('binance')
        
        try:
            url = f"{self.binance_base}/api/v3/depth"
            params = {'symbol': symbol, 'limit': limit}
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'bids': [[float(p), float(q)] for p, q in data['bids']],
                'asks': [[float(p), float(q)] for p, q in data['asks']],
                'source': 'binance'
            }
        
        except Exception as e:
            logger.error(f"获取Binance订单簿失败 {symbol}: {e}")
            return None
    
    def get_binance_klines(
        self,
        symbol: str,
        interval: str = '1h',
        limit: int = 100
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取Binance K线数据
        
        Args:
            symbol: 交易对
            interval: 时间周期 (1m, 5m, 15m, 1h, 4h, 1d, 1w)
            limit: 返回数量 (最大1000)
        
        Returns:
            K线数据列表
        """
        self._rate_limit('binance')
        
        try:
            url = f"{self.binance_base}/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            klines = []
            for k in response.json():
                klines.append({
                    'timestamp': datetime.fromtimestamp(k[0]/1000).isoformat(),
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5]),
                    'close_time': datetime.fromtimestamp(k[6]/1000).isoformat(),
                    'quote_volume': float(k[7]),
                    'trades': int(k[8])
                })
            
            return klines
        
        except Exception as e:
            logger.error(f"获取Binance K线失败 {symbol}: {e}")
            return None
    
    def get_binance_ticker_24h(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取24小时行情统计
        
        Args:
            symbol: 交易对
        
        Returns:
            24小时统计数据
        """
        self._rate_limit('binance')
        
        try:
            url = f"{self.binance_base}/api/v3/ticker/24hr"
            params = {'symbol': symbol}
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'symbol': symbol,
                'price_change': float(data['priceChange']),
                'price_change_pct': float(data['priceChangePercent']),
                'last_price': float(data['lastPrice']),
                'volume': float(data['volume']),
                'quote_volume': float(data['quoteVolume']),
                'high': float(data['highPrice']),
                'low': float(data['lowPrice']),
                'trades': int(data['count'])
            }
        
        except Exception as e:
            logger.error(f"获取Binance 24h统计失败 {symbol}: {e}")
            return None
    
    # ==================== Alternative.me (恐慌贪婪指数) ====================
    
    def get_fear_greed_index(self, limit: int = 7) -> Optional[Dict[str, Any]]:
        """
        获取恐慌贪婪指数
        
        Args:
            limit: 获取天数 (默认7天)
        
        Returns:
            恐慌贪婪指数数据
        """
        self._rate_limit('fear_greed')
        
        try:
            params = {'limit': limit}
            response = self.session.get(self.fear_greed_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'data' in data and data['data']:
                current = data['data'][0]
                
                # 分类
                value = int(current['value'])
                if value >= 75:
                    classification = 'EXTREME_GREED'
                elif value >= 55:
                    classification = 'GREED'
                elif value >= 45:
                    classification = 'NEUTRAL'
                elif value >= 25:
                    classification = 'FEAR'
                else:
                    classification = 'EXTREME_FEAR'
                
                return {
                    'value': value,
                    'classification': classification,
                    'value_classification': current['value_classification'],
                    'timestamp': datetime.fromtimestamp(int(current['timestamp'])).isoformat(),
                    'history': [
                        {
                            'value': int(d['value']),
                            'timestamp': datetime.fromtimestamp(int(d['timestamp'])).isoformat()
                        }
                        for d in data['data']
                    ]
                }
            
            return None
        
        except Exception as e:
            logger.error(f"获取恐慌贪婪指数失败: {e}")
            return None
    
    # ==================== CoinGecko API ====================
    
    def get_coingecko_price(
        self,
        coin_id: str,
        vs_currency: str = 'usd'
    ) -> Optional[Dict[str, Any]]:
        """
        获取CoinGecko价格数据
        
        Args:
            coin_id: 币种ID (如 'bitcoin', 'ethereum')
            vs_currency: 计价货币 (默认 'usd')
        
        Returns:
            价格数据
        """
        self._rate_limit('coingecko')
        
        try:
            url = f"{self.coingecko_base}/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': vs_currency,
                'include_24hr_change': 'true',
                'include_market_cap': 'true',
                'include_24hr_vol': 'true'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if coin_id in data:
                return {
                    'coin_id': coin_id,
                    'price': data[coin_id].get(vs_currency),
                    'market_cap': data[coin_id].get(f'{vs_currency}_market_cap'),
                    'volume_24h': data[coin_id].get(f'{vs_currency}_24h_vol'),
                    'change_24h': data[coin_id].get(f'{vs_currency}_24h_change'),
                    'timestamp': datetime.now().isoformat()
                }
            
            return None
        
        except Exception as e:
            logger.error(f"获取CoinGecko价格失败 {coin_id}: {e}")
            return None
    
    def get_coingecko_market_chart(
        self,
        coin_id: str,
        days: int = 7,
        vs_currency: str = 'usd'
    ) -> Optional[Dict[str, Any]]:
        """
        获取CoinGecko历史图表数据
        
        Args:
            coin_id: 币种ID
            days: 天数 (1, 7, 14, 30, 90, 180, 365, max)
            vs_currency: 计价货币
        
        Returns:
            历史数据
        """
        self._rate_limit('coingecko')
        
        try:
            url = f"{self.coingecko_base}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': vs_currency,
                'days': days
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'coin_id': coin_id,
                'prices': [
                    {'timestamp': datetime.fromtimestamp(p[0]/1000).isoformat(), 'price': p[1]}
                    for p in data.get('prices', [])
                ],
                'market_caps': [
                    {'timestamp': datetime.fromtimestamp(m[0]/1000).isoformat(), 'market_cap': m[1]}
                    for m in data.get('market_caps', [])
                ],
                'total_volumes': [
                    {'timestamp': datetime.fromtimestamp(v[0]/1000).isoformat(), 'volume': v[1]}
                    for v in data.get('total_volumes', [])
                ]
            }
        
        except Exception as e:
            logger.error(f"获取CoinGecko历史数据失败 {coin_id}: {e}")
            return None
    
    # ==================== FRED API (美联储数据) ====================
    
    def get_fred_series(
        self,
        series_id: str,
        api_key: Optional[str] = None,
        limit: int = 100
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取FRED经济数据
        
        Args:
            series_id: 数据序列ID
                - 'DFF': 联邦基金利率
                - 'CPIAUCSL': CPI通胀
                - 'UNRATE': 失业率
                - 'GDP': GDP
            api_key: FRED API密钥（可选，免费申请）
            limit: 返回数量
        
        Returns:
            经济数据序列
        """
        if not api_key:
            logger.warning("FRED API需要免费申请API Key: https://fred.stlouisfed.org/docs/api/api_key.html")
            return None
        
        self._rate_limit('fred')
        
        try:
            url = f"{self.fred_base}/series/observations"
            params = {
                'series_id': series_id,
                'api_key': api_key,
                'file_type': 'json',
                'limit': limit,
                'sort_order': 'desc'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'observations' in data:
                return [
                    {
                        'date': obs['date'],
                        'value': float(obs['value']) if obs['value'] != '.' else None
                    }
                    for obs in data['observations']
                ]
            
            return None
        
        except Exception as e:
            logger.error(f"获取FRED数据失败 {series_id}: {e}")
            return None
    
    # ==================== Yahoo Finance (通过yfinance库) ====================
    
    def get_yahoo_finance_data(
        self,
        ticker: str,
        period: str = '1mo'
    ) -> Optional[Dict[str, Any]]:
        """
        获取Yahoo Finance数据
        
        Args:
            ticker: 股票代码
                - '^GSPC': 标普500
                - '^IXIC': 纳斯达克
                - 'GC=F': 黄金
                - 'DX-Y.NYB': 美元指数
            period: 时间周期 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        
        Returns:
            股票/指数数据
        """
        try:
            import yfinance as yf
            
            self._rate_limit('yfinance')
            
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            
            if hist.empty:
                return None
            
            return {
                'ticker': ticker,
                'current_price': float(hist['Close'].iloc[-1]),
                'price_change': float(hist['Close'].iloc[-1] - hist['Close'].iloc[0]),
                'price_change_pct': float((hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100),
                'high': float(hist['High'].max()),
                'low': float(hist['Low'].min()),
                'avg_volume': float(hist['Volume'].mean()),
                'history': [
                    {
                        'date': index.strftime('%Y-%m-%d'),
                        'open': float(row['Open']),
                        'high': float(row['High']),
                        'low': float(row['Low']),
                        'close': float(row['Close']),
                        'volume': int(row['Volume'])
                    }
                    for index, row in hist.iterrows()
                ]
            }
        
        except ImportError:
            logger.error("yfinance库未安装，请运行: pip install yfinance")
            return None
        except Exception as e:
            logger.error(f"获取Yahoo Finance数据失败 {ticker}: {e}")
            return None
    
    # ==================== DeFiLlama API ====================
    
    def get_defillama_tvl(self, protocol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        获取DeFi协议TVL
        
        Args:
            protocol: 协议名称（如 'uniswap', 'aave'），为空则获取总TVL
        
        Returns:
            TVL数据
        """
        self._rate_limit('defillama')
        
        try:
            if protocol:
                url = f"{self.defi_llama_base}/protocol/{protocol}"
            else:
                url = f"{self.defi_llama_base}/charts"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if protocol:
                tvl_data = data.get('tvl')
                current_tvl = None
                
                # tvl可能是列表（历史数据）或数字
                if isinstance(tvl_data, list) and len(tvl_data) > 0:
                    current_tvl = tvl_data[-1].get('totalLiquidityUSD') if isinstance(tvl_data[-1], dict) else tvl_data[-1]
                elif isinstance(tvl_data, (int, float)):
                    current_tvl = tvl_data
                
                return {
                    'protocol': protocol,
                    'name': data.get('name'),
                    'tvl': current_tvl,
                    'chain_tvls': data.get('chainTvls'),
                    'change_1d': data.get('change_1d'),
                    'change_7d': data.get('change_7d'),
                    'mcap': data.get('mcap')
                }
            else:
                # 总TVL
                if isinstance(data, list) and len(data) > 0:
                    latest = data[-1]
                    date_timestamp = int(latest.get('date', 0))
                    return {
                        'total_tvl': latest.get('totalLiquidityUSD'),
                        'date': datetime.fromtimestamp(date_timestamp).isoformat(),
                        'history_count': len(data)
                    }
                else:
                    return None
        
        except Exception as e:
            logger.error(f"获取DeFiLlama TVL失败: {e}")
            return None
    
    # ==================== GitHub API ====================
    
    def get_github_repo_stats(
        self,
        owner: str,
        repo: str,
        token: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取GitHub仓库统计
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            token: GitHub Token（可选，提高速率限制）
        
        Returns:
            仓库统计数据
        """
        self._rate_limit('github')
        
        try:
            headers = {}
            if token:
                headers['Authorization'] = f'token {token}'
            
            # 仓库基本信息
            url = f"{self.github_base}/repos/{owner}/{repo}"
            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # 获取最近提交
            commits_url = f"{self.github_base}/repos/{owner}/{repo}/commits"
            commits_response = self.session.get(
                commits_url,
                headers=headers,
                params={'per_page': 10},
                timeout=10
            )
            
            recent_commits = []
            if commits_response.status_code == 200:
                commits = commits_response.json()
                recent_commits = [
                    {
                        'sha': c['sha'][:7],
                        'message': c['commit']['message'].split('\n')[0],
                        'author': c['commit']['author']['name'],
                        'date': c['commit']['author']['date']
                    }
                    for c in commits[:5]
                ]
            
            return {
                'owner': owner,
                'repo': repo,
                'stars': data['stargazers_count'],
                'forks': data['forks_count'],
                'watchers': data['watchers_count'],
                'open_issues': data['open_issues_count'],
                'language': data['language'],
                'created_at': data['created_at'],
                'updated_at': data['updated_at'],
                'pushed_at': data['pushed_at'],
                'recent_commits': recent_commits,
                'description': data['description']
            }
        
        except Exception as e:
            logger.error(f"获取GitHub仓库统计失败 {owner}/{repo}: {e}")
            return None


if __name__ == '__main__':
    # 测试
    connector = FreeDataSourceConnector()
    
    print("\n=== 测试Binance订单簿 ===")
    orderbook = connector.get_binance_orderbook('BTCUSDT', limit=5)
    if orderbook:
        print(f"✅ 获取成功: {len(orderbook['bids'])}档买单, {len(orderbook['asks'])}档卖单")
        print(f"最优买价: {orderbook['bids'][0][0]}, 最优卖价: {orderbook['asks'][0][0]}")
    
    print("\n=== 测试恐慌贪婪指数 ===")
    fg_index = connector.get_fear_greed_index()
    if fg_index:
        print(f"✅ 当前指数: {fg_index['value']} - {fg_index['classification']}")
    
    print("\n=== 测试CoinGecko价格 ===")
    btc_price = connector.get_coingecko_price('bitcoin')
    if btc_price:
        print(f"✅ BTC价格: ${btc_price['price']:,.0f}")
        print(f"24h涨跌: {btc_price['change_24h']:+.2f}%")
    
    print("\n=== 测试Yahoo Finance ===")
    sp500 = connector.get_yahoo_finance_data('^GSPC', period='5d')
    if sp500:
        print(f"✅ 标普500: {sp500['current_price']:.2f}")
        print(f"涨跌幅: {sp500['price_change_pct']:+.2f}%")
    
    print("\n=== 测试DeFiLlama ===")
    tvl = connector.get_defillama_tvl()
    if tvl:
        print(f"✅ DeFi总TVL: ${tvl['total_tvl']:,.0f}")
    
    print("\n=== 测试GitHub ===")
    repo = connector.get_github_repo_stats('bitcoin', 'bitcoin')
    if repo:
        print(f"✅ Bitcoin仓库: {repo['stars']:,} stars, {repo['forks']:,} forks")
        print(f"最近更新: {repo['pushed_at']}")
