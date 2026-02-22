"""
财报和宏观数据获取器

支持：
1. Finnhub财报数据（营收、利润、PE、PB等）
2. 宏观经济指标（GDP、通胀率、利率等）
3. 行业指标和市场情绪
"""
import os
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from loguru import logger


class FundamentalDataFetcher:
    """
    财报和宏观数据获取器
    使用Finnhub API获取财报数据
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """初始化"""
        self.api_key = api_key or os.getenv('FINNHUB_API_KEY')
        self.cache = {}
        self.cache_ttl = 3600  # 1小时缓存
        
        if not self.api_key:
            logger.warning("⚠️ FINNHUB_API_KEY 未设置，财报数据功能将受限")
        else:
            logger.info("✅ FundamentalDataFetcher 初始化成功")
    
    def _cache_key(self, symbol: str, data_type: str) -> str:
        """生成缓存键"""
        return f"{symbol}:{data_type}"
    
    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """从缓存获取"""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now().timestamp() - timestamp < self.cache_ttl:
                return data
        return None
    
    def _set_cache(self, key: str, data: Dict):
        """设置缓存"""
        self.cache[key] = (data, datetime.now().timestamp())
    
    async def get_fundamental_metrics(self, symbol: str) -> Dict[str, Any]:
        """
        获取基本面指标
        
        Args:
            symbol: 股票代码（美股格式，如AAPL）
        
        Returns:
            {
                'pe_ratio': float,      # 市盈率
                'pb_ratio': float,      # 市净率
                'roe': float,           # 净资产收益率
                'profit_margin': float, # 净利润率
                'revenue_growth': float,# 营收增长率
                'debt_equity': float,   # 资产负债率
                'current_ratio': float, # 流动比率
                'eps': float,           # 每股收益
                'dividend_yield': float,# 股息率
                'score': float,         # 综合得分 0-100
                'timestamp': str
            }
        """
        cache_key = self._cache_key(symbol, 'fundamentals')
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        if not self.api_key:
            return self._get_default_metrics()
        
        try:
            import finnhub
            client = finnhub.Client(api_key=self.api_key)
            
            # 获取基本面指标
            metrics = await asyncio.to_thread(
                client.company_basic_financials,
                symbol,
                'all'
            )
            
            if not metrics or 'metric' not in metrics:
                return self._get_default_metrics()
            
            m = metrics['metric']
            
            # 提取关键指标
            result = {
                'pe_ratio': m.get('peNormalizedAnnual', m.get('peBasicExclExtraTTM', 0)),
                'pb_ratio': m.get('pbAnnual', m.get('pbQuarterly', 0)),
                'roe': m.get('roeRfy', m.get('roeTTM', 0)),
                'profit_margin': m.get('netProfitMarginTTM', m.get('netProfitMarginAnnual', 0)),
                'revenue_growth': m.get('revenueGrowthTTMYoy', m.get('revenueGrowthQuarterlyYoy', 0)),
                'debt_equity': m.get('totalDebt/totalEquityAnnual', m.get('totalDebt/totalEquityQuarterly', 0)),
                'current_ratio': m.get('currentRatioAnnual', m.get('currentRatioQuarterly', 0)),
                'eps': m.get('epsExclExtraItemsTTM', m.get('epsNormalizedAnnual', 0)),
                'dividend_yield': m.get('dividendYieldIndicatedAnnual', 0),
                'timestamp': datetime.now().isoformat()
            }
            
            # 计算综合得分（0-100）
            result['score'] = self._calculate_fundamental_score(result)
            
            self._set_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.warning(f"获取 {symbol} 财报数据失败: {e}")
            return self._get_default_metrics()
    
    def _calculate_fundamental_score(self, metrics: Dict[str, Any]) -> float:
        """
        计算财报综合得分（0-100）
        
        评分因素：
        - PE合理性（15-25为佳）：15分
        - PB合理性（1-3为佳）：10分
        - ROE高低（>15%优秀）：20分
        - 利润率（>10%优秀）：15分
        - 营收增长（>20%优秀）：20分
        - 负债率（<70%健康）：10分
        - 流动比率（>1.5安全）：10分
        """
        score = 0.0
        
        # 1. PE评分（15分）
        pe = metrics.get('pe_ratio', 0)
        if 15 <= pe <= 25:
            score += 15
        elif 10 <= pe < 15 or 25 < pe <= 35:
            score += 10
        elif 5 <= pe < 10 or 35 < pe <= 50:
            score += 5
        elif pe > 50:
            score -= 5  # PE过高扣分
        
        # 2. PB评分（10分）
        pb = metrics.get('pb_ratio', 0)
        if 1 <= pb <= 3:
            score += 10
        elif 0.5 <= pb < 1 or 3 < pb <= 5:
            score += 6
        elif pb > 10:
            score -= 3
        
        # 3. ROE评分（20分） - 最重要
        roe = metrics.get('roe', 0)
        if roe >= 20:
            score += 20
        elif roe >= 15:
            score += 16
        elif roe >= 10:
            score += 12
        elif roe >= 5:
            score += 6
        elif roe < 0:
            score -= 10  # 负ROE扣分
        
        # 4. 利润率评分（15分）
        margin = metrics.get('profit_margin', 0)
        if margin >= 15:
            score += 15
        elif margin >= 10:
            score += 12
        elif margin >= 5:
            score += 8
        elif margin >= 0:
            score += 3
        elif margin < 0:
            score -= 8
        
        # 5. 营收增长评分（20分）
        growth = metrics.get('revenue_growth', 0)
        if growth >= 30:
            score += 20
        elif growth >= 20:
            score += 16
        elif growth >= 10:
            score += 12
        elif growth >= 0:
            score += 6
        elif growth < -10:
            score -= 10
        
        # 6. 负债率评分（10分）
        debt_eq = metrics.get('debt_equity', 0)
        if debt_eq <= 50:
            score += 10
        elif debt_eq <= 70:
            score += 7
        elif debt_eq <= 100:
            score += 4
        elif debt_eq > 200:
            score -= 5
        
        # 7. 流动比率评分（10分）
        current = metrics.get('current_ratio', 0)
        if current >= 2:
            score += 10
        elif current >= 1.5:
            score += 8
        elif current >= 1:
            score += 5
        elif current < 0.8:
            score -= 5
        
        # 确保分数在0-100范围内
        return max(0, min(100, score))
    
    def _get_default_metrics(self) -> Dict[str, Any]:
        """返回默认指标（API不可用时）"""
        return {
            'pe_ratio': 0,
            'pb_ratio': 0,
            'roe': 0,
            'profit_margin': 0,
            'revenue_growth': 0,
            'debt_equity': 0,
            'current_ratio': 0,
            'eps': 0,
            'dividend_yield': 0,
            'score': 50,  # 默认中性分
            'timestamp': datetime.now().isoformat()
        }
    
    async def get_earnings_quality(self, symbol: str) -> Dict[str, Any]:
        """
        获取盈利质量指标
        
        Returns:
            {
                'beat_estimate': bool,      # 是否超预期
                'earnings_surprise': float, # 盈利惊喜度
                'earnings_trend': str,      # 'improving', 'stable', 'declining'
                'guidance': str,            # 'positive', 'neutral', 'negative'
                'score': float              # 质量得分 -20~+20
            }
        """
        cache_key = self._cache_key(symbol, 'earnings')
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        if not self.api_key:
            return {
                'beat_estimate': False,
                'earnings_surprise': 0,
                'earnings_trend': 'neutral',
                'guidance': 'neutral',
                'score': 0
            }
        
        try:
            import finnhub
            client = finnhub.Client(api_key=self.api_key)
            
            # 获取最近财报
            earnings = await asyncio.to_thread(
                client.company_earnings,
                symbol,
                limit=4  # 最近4个季度
            )
            
            if not earnings:
                return {'beat_estimate': False, 'earnings_surprise': 0, 'earnings_trend': 'neutral', 'guidance': 'neutral', 'score': 0}
            
            # 分析最新财报
            latest = earnings[0] if earnings else {}
            actual = latest.get('actual', 0)
            estimate = latest.get('estimate', 0)
            
            # 计算超预期程度
            surprise = 0
            beat = False
            if estimate != 0:
                surprise = ((actual - estimate) / abs(estimate)) * 100
                beat = actual > estimate
            
            # 分析趋势（最近4季度）
            if len(earnings) >= 3:
                recent_eps = [e.get('actual', 0) for e in earnings[:3]]
                if recent_eps[0] > recent_eps[1] > recent_eps[2]:
                    trend = 'improving'
                elif recent_eps[0] < recent_eps[1] < recent_eps[2]:
                    trend = 'declining'
                else:
                    trend = 'stable'
            else:
                trend = 'neutral'
            
            # 计算盈利质量得分
            score = 0
            if beat:
                score += 10
            if surprise > 10:
                score += 10
            elif surprise > 5:
                score += 5
            elif surprise < -10:
                score -= 10
            
            if trend == 'improving':
                score += 5
            elif trend == 'declining':
                score -= 5
            
            result = {
                'beat_estimate': beat,
                'earnings_surprise': surprise,
                'earnings_trend': trend,
                'guidance': 'positive' if beat else 'neutral',
                'score': score
            }
            
            self._set_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.debug(f"获取 {symbol} 盈利数据失败: {e}")
            return {'beat_estimate': False, 'earnings_surprise': 0, 'earnings_trend': 'neutral', 'guidance': 'neutral', 'score': 0}
    
    async def get_macro_indicators(self) -> Dict[str, Any]:
        """
        获取宏观经济指标
        
        Returns:
            {
                'gdp_growth': float,      # GDP增长率
                'unemployment': float,    # 失业率
                'inflation': float,       # 通胀率
                'interest_rate': float,   # 基准利率
                'market_sentiment': str,  # 'risk_on', 'risk_off', 'neutral'
                'vix': float,             # 恐慌指数
                'score': float            # 宏观面得分 -20~+20
            }
        """
        cache_key = "_macro_global"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        # 简化版本：基于市场常识和VIX估算
        # 实际应用可接入FRED API或其他宏观数据源
        result = {
            'gdp_growth': 2.5,        # 假设正常增长
            'unemployment': 3.7,      # 假设低失业率
            'inflation': 3.0,         # 假设温和通胀
            'interest_rate': 5.25,    # 假设当前基准利率
            'market_sentiment': 'neutral',
            'vix': 15.0,              # 假设低波动
            'score': 0,               # 中性宏观环境
            'timestamp': datetime.now().isoformat()
        }
        
        # 根据VIX判断市场情绪
        # VIX < 15: risk_on (乐观)
        # VIX 15-25: neutral
        # VIX > 25: risk_off (恐慌)
        
        # 计算宏观得分
        score = 0
        
        # GDP增长（-5~+5分）
        if result['gdp_growth'] > 3:
            score += 5
        elif result['gdp_growth'] > 2:
            score += 3
        elif result['gdp_growth'] < 0:
            score -= 5
        
        # 失业率（-3~+3分）
        if result['unemployment'] < 4:
            score += 3
        elif result['unemployment'] > 6:
            score -= 3
        
        # 通胀率（-5~+2分）
        if 2 <= result['inflation'] <= 3:
            score += 2  # 温和通胀有利
        elif result['inflation'] > 5:
            score -= 5  # 高通胀不利
        elif result['inflation'] < 1:
            score -= 2  # 通缩风险
        
        # 利率（-3~+3分）
        # 低利率有利于股市
        if result['interest_rate'] < 3:
            score += 3
        elif result['interest_rate'] > 5:
            score -= 3
        
        # VIX恐慌指数（-7~+5分）
        if result['vix'] < 15:
            score += 5
            result['market_sentiment'] = 'risk_on'
        elif result['vix'] < 20:
            score += 2
        elif result['vix'] > 30:
            score -= 7
            result['market_sentiment'] = 'risk_off'
        
        result['score'] = score
        
        self._set_cache(cache_key, result)
        return result
    
    async def get_sector_strength(self, symbol: str) -> Dict[str, Any]:
        """
        获取行业强度指标
        
        Returns:
            {
                'sector': str,           # 行业名称
                'sector_momentum': float,# 行业动量
                'relative_strength': float, # 相对强度
                'score': float           # 行业得分 -10~+10
            }
        """
        # 简化版本：返回默认值
        # 实际应用可分析同行业其他股票的平均表现
        return {
            'sector': 'Technology',
            'sector_momentum': 0,
            'relative_strength': 0,
            'score': 0,
            'timestamp': datetime.now().isoformat()
        }


# 全局实例
_fetcher = None

def get_fundamental_fetcher() -> FundamentalDataFetcher:
    """获取全局财报数据获取器实例"""
    global _fetcher
    if _fetcher is None:
        _fetcher = FundamentalDataFetcher()
    return _fetcher
