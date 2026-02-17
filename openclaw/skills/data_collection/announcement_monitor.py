"""
Announcement monitor for DART (Korea) and other sources
"""
import asyncio
from typing import Dict, List, Any
from datetime import datetime
from loguru import logger
from utils.api_client import APIClient


class AnnouncementMonitor:
    """
    Monitors corporate announcements from DART API
    
    DART: Korean Financial Supervisory Service
    Rate Limit: 240 requests/day
    Check Interval: 1 hour
    """
    
    def __init__(self, dart_api_key: str = ""):
        """
        Initialize announcement monitor
        
        Args:
            dart_api_key: DART API key
        """
        self.dart_api_key = dart_api_key
        self.announcements_cache: List[Dict[str, Any]] = []
        self.request_count = 0
    
    async def fetch_dart_announcements(
        self,
        corp_codes: Optional[List[str]] = None,
        begin_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch announcements from DART
        
        Args:
            corp_codes: List of corporation codes
            begin_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)
        
        Returns:
            List of announcements
        """
        if not self.dart_api_key:
            logger.warning("DART API key not configured, using mock data")
            return self._generate_mock_announcements()
        
        try:
            # Use today's date if not specified
            if not end_date:
                end_date = datetime.now().strftime("%Y%m%d")
            if not begin_date:
                begin_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
            
            params = {
                "crtfc_key": self.dart_api_key,
                "bgn_de": begin_date,
                "end_de": end_date,
                "page_count": 100
            }
            
            if corp_codes:
                params["corp_code"] = ",".join(corp_codes)
            
            async with APIClient("https://opendart.fss.or.kr/api") as client:
                response = await client.get("/list.json", params=params)
                
                if response.get("status") != "000":
                    logger.error(f"DART API error: {response.get('message')}")
                    return []
                
                announcements = []
                for item in response.get("list", []):
                    announcements.append({
                        "corp_name": item.get("corp_name", ""),
                        "corp_code": item.get("corp_code", ""),
                        "report_name": item.get("report_nm", ""),
                        "receive_date": item.get("rcept_dt", ""),
                        "submitter": item.get("flr_nm", ""),
                        "description": item.get("rm", ""),
                        "source": "dart",
                        "timestamp": datetime.now().isoformat()
                    })
                
                self.request_count += 1
                logger.info(f"Fetched {len(announcements)} announcements from DART")
                return announcements
        
        except Exception as e:
            logger.error(f"Failed to fetch DART announcements: {e}")
            return self._generate_mock_announcements()
    
    async def monitor_announcements(
        self,
        corp_codes: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Monitor for new announcements
        
        Args:
            corp_codes: List of corporation codes to monitor
        
        Returns:
            List of new announcements
        """
        announcements = await self.fetch_dart_announcements(corp_codes)
        
        # Filter for significant announcements
        significant = self._filter_significant(announcements)
        
        # Cache results
        self.announcements_cache = significant
        
        return significant
    
    def _filter_significant(
        self,
        announcements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter for significant announcements"""
        # Keywords indicating significant events
        significant_keywords = [
            "합병", "인수", "배당", "증자", "감자",  # Korean
            "merger", "acquisition", "dividend", "capital",  # English
            "실적", "공시", "거래정지", "투자", "경영"
        ]
        
        significant = []
        for announcement in announcements:
            report_name = announcement.get("report_name", "").lower()
            description = announcement.get("description", "").lower()
            
            for keyword in significant_keywords:
                if keyword in report_name or keyword in description:
                    significant.append(announcement)
                    break
        
        return significant
    
    def _generate_mock_announcements(self) -> List[Dict[str, Any]]:
        """Generate mock announcements for testing"""
        return [
            {
                "corp_name": "Mock Corporation A",
                "corp_code": "00000001",
                "report_name": "Quarterly Earnings Report",
                "receive_date": datetime.now().strftime("%Y%m%d"),
                "submitter": "CFO",
                "description": "Mock earnings announcement",
                "source": "dart",
                "timestamp": datetime.now().isoformat(),
                "mock": True
            },
            {
                "corp_name": "Mock Corporation B",
                "corp_code": "00000002",
                "report_name": "Dividend Announcement",
                "receive_date": datetime.now().strftime("%Y%m%d"),
                "submitter": "Board of Directors",
                "description": "Mock dividend announcement",
                "source": "dart",
                "timestamp": datetime.now().isoformat(),
                "mock": True
            }
        ]
    
    def get_cached_announcements(self) -> List[Dict[str, Any]]:
        """Get cached announcements"""
        return self.announcements_cache.copy()


# Import for date handling
from datetime import timedelta
