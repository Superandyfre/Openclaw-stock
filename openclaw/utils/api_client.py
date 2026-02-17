"""
API Client utility for OpenClaw Trading System
"""
import aiohttp
from typing import Dict, Any, Optional
from loguru import logger


class APIClient:
    """Generic async API client"""
    
    def __init__(self, base_url: str = "", headers: Optional[Dict[str, str]] = None):
        """
        Initialize API client
        
        Args:
            base_url: Base URL for API requests
            headers: Default headers for requests
        """
        self.base_url = base_url
        self.headers = headers or {}
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make GET request
        
        Args:
            endpoint: API endpoint
            params: Query parameters
        
        Returns:
            Response JSON data
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        url = f"{self.base_url}{endpoint}"
        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"GET request failed: {url} - {e}")
            raise
    
    async def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make POST request
        
        Args:
            endpoint: API endpoint
            data: Request body data
        
        Returns:
            Response JSON data
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
        
        url = f"{self.base_url}{endpoint}"
        try:
            async with self.session.post(url, json=data) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"POST request failed: {url} - {e}")
            raise
