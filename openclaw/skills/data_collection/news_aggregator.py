"""
News aggregator from multiple sources
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger
from ...utils.api_client import APIClient


class NewsAggregator:
    """
    Aggregates news from multiple sources
    
    Sources:
    - Naver News API (Korea)
    - CryptoPanic API (Crypto)
    
    Rate Limit: ~20 requests/day
    """
    
    def __init__(
        self,
        naver_client_id: str = "",
        naver_client_secret: str = "",
        cryptopanic_api_key: str = ""
    ):
        """
        Initialize news aggregator
        
        Args:
            naver_client_id: Naver API client ID
            naver_client_secret: Naver API client secret
            cryptopanic_api_key: CryptoPanic API key
        """
        self.naver_client_id = naver_client_id
        self.naver_client_secret = naver_client_secret
        self.cryptopanic_api_key = cryptopanic_api_key
        self.news_cache: List[Dict[str, Any]] = []
        self.request_count = 0
    
    async def fetch_naver_news(
        self,
        query: str,
        display: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fetch news from Naver
        
        Args:
            query: Search query
            display: Number of results
        
        Returns:
            List of news articles
        """
        if not self.naver_client_id or not self.naver_client_secret:
            logger.warning("Naver credentials not configured, using mock news")
            return self._generate_mock_news(query, "naver")
        
        try:
            headers = {
                "X-Naver-Client-Id": self.naver_client_id,
                "X-Naver-Client-Secret": self.naver_client_secret
            }
            
            async with APIClient("https://openapi.naver.com", headers) as client:
                response = await client.get(
                    "/v1/search/news.json",
                    params={"query": query, "display": display}
                )
                
                articles = []
                for item in response.get("items", []):
                    articles.append({
                        "title": item.get("title", "").replace("<b>", "").replace("</b>", ""),
                        "description": item.get("description", "").replace("<b>", "").replace("</b>", ""),
                        "link": item.get("link", ""),
                        "pub_date": item.get("pubDate", ""),
                        "source": "naver",
                        "timestamp": datetime.now().isoformat()
                    })
                
                self.request_count += 1
                logger.info(f"Fetched {len(articles)} articles from Naver for '{query}'")
                return articles
        
        except Exception as e:
            logger.error(f"Failed to fetch Naver news: {e}")
            return self._generate_mock_news(query, "naver")
    
    async def fetch_cryptopanic_news(
        self,
        currencies: Optional[List[str]] = None,
        filter_type: str = "rising"
    ) -> List[Dict[str, Any]]:
        """
        Fetch cryptocurrency news from CryptoPanic
        
        Args:
            currencies: List of currency codes (BTC, ETH, etc.)
            filter_type: Filter type (rising, hot, bullish, bearish)
        
        Returns:
            List of news articles
        """
        if not self.cryptopanic_api_key:
            logger.warning("CryptoPanic API key not configured, using mock news")
            return self._generate_mock_news("crypto", "cryptopanic")
        
        try:
            params = {
                "auth_token": self.cryptopanic_api_key,
                "filter": filter_type
            }
            
            if currencies:
                params["currencies"] = ",".join(currencies)
            
            async with APIClient("https://cryptopanic.com/api/v1") as client:
                response = await client.get("/posts/", params=params)
                
                articles = []
                for item in response.get("results", []):
                    articles.append({
                        "title": item.get("title", ""),
                        "description": item.get("title", ""),  # CryptoPanic doesn't have separate description
                        "link": item.get("url", ""),
                        "pub_date": item.get("published_at", ""),
                        "source": "cryptopanic",
                        "sentiment": item.get("votes", {}).get("kind", "neutral"),
                        "currencies": item.get("currencies", []),
                        "timestamp": datetime.now().isoformat()
                    })
                
                self.request_count += 1
                logger.info(f"Fetched {len(articles)} articles from CryptoPanic")
                return articles
        
        except Exception as e:
            logger.error(f"Failed to fetch CryptoPanic news: {e}")
            return self._generate_mock_news("crypto", "cryptopanic")
    
    async def fetch_relevant_news(
        self,
        stock_symbols: List[str],
        crypto_symbols: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch relevant news for monitored assets
        
        Args:
            stock_symbols: List of stock symbols
            crypto_symbols: List of crypto symbols
        
        Returns:
            Combined list of relevant news
        """
        all_news = []
        
        # Fetch stock news (limited queries)
        for symbol in stock_symbols[:3]:  # Limit to top 3 to save API calls
            news = await self.fetch_naver_news(symbol, display=5)
            all_news.extend(news)
            await asyncio.sleep(0.5)  # Rate limiting
        
        # Fetch crypto news
        crypto_codes = [s.split('-')[1] for s in crypto_symbols if '-' in s]
        crypto_news = await self.fetch_cryptopanic_news(crypto_codes[:5])
        all_news.extend(crypto_news)
        
        # Cache results
        self.news_cache = all_news
        
        return all_news
    
    def _generate_mock_news(self, query: str, source: str) -> List[Dict[str, Any]]:
        """Generate mock news for testing"""
        mock_titles = [
            f"{query} shows strong performance in recent trading",
            f"Analysts upgrade {query} rating to Buy",
            f"Market volatility affects {query} price movement",
            f"{query} announces new strategic partnership",
            f"Industry experts discuss {query} future outlook"
        ]
        
        return [
            {
                "title": title,
                "description": f"Mock news article about {query}",
                "link": f"https://example.com/news/{i}",
                "pub_date": datetime.now().isoformat(),
                "source": source,
                "timestamp": datetime.now().isoformat(),
                "mock": True
            }
            for i, title in enumerate(mock_titles[:3])
        ]
    
    def get_cached_news(self) -> List[Dict[str, Any]]:
        """Get cached news"""
        return self.news_cache.copy()
