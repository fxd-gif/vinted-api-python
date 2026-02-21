"""Vinted API scraper with proxy rotation and anti-bot measures."""

import asyncio
import random
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
from urllib.parse import urlencode
import httpx
from fake_useragent import UserAgent
from loguru import logger

from core.config import get_settings, BROWSER_HEADERS, VINTED_DOMAINS
from core.models import Proxy
from core.proxy_rotator import get_proxy_rotator

settings = get_settings()
ua = UserAgent()


class VintedScraper:
    """Scraper for Vinted's internal API."""
    
    def __init__(self, domain: str = "vinted.de"):
        self.domain = domain
        self.base_url = f"https://www.{domain}"
        self.api_base = f"{self.base_url}/api/v2"
        self.proxy_rotator = get_proxy_rotator()
        self.last_request_time = 0
        self.min_request_interval = 2.0  # Minimum seconds between requests
        self._lock = asyncio.Lock()
        
        # Session state
        self.cookies: Dict[str, str] = {}
        self.csrf_token: Optional[str] = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Generate realistic browser headers."""
        headers = BROWSER_HEADERS.copy()
        headers["User-Agent"] = ua.random
        headers["Referer"] = self.base_url
        headers["Origin"] = self.base_url
        
        if self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        
        return headers
    
    async def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        async with self._lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_request_interval:
                wait = self.min_request_interval - elapsed + random.uniform(0.5, 1.5)
                await asyncio.sleep(wait)
            self.last_request_time = time.time()
    
    async def _make_request(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None,
        retries: int = 0
    ) -> Optional[Dict]:
        """Make a request to Vinted API with proxy rotation."""
        await self._wait_for_rate_limit()
        
        url = f"{self.api_base}/{endpoint}"
        proxy = self.proxy_rotator.get_next_proxy()
        proxy_url = proxy.url if proxy else None
        
        headers = self._get_headers()
        
        try:
            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                headers=headers,
                cookies=self.cookies
            ) as client:
                response = await client.get(
                    url,
                    params=params,
                    proxy=proxy_url
                )
                
                # Update cookies
                self.cookies.update(response.cookies)
                
                if response.status_code == 200:
                    if proxy:
                        self.proxy_rotator.report_success(proxy)
                    return response.json()
                
                elif response.status_code == 403:
                    # Blocked by anti-bot
                    logger.warning(f"Blocked by anti-bot (403) for {endpoint}")
                    if proxy:
                        self.proxy_rotator.report_failure(proxy)
                    
                    if retries < settings.max_retries:
                        await asyncio.sleep(settings.retry_delay * (retries + 1))
                        return await self._make_request(endpoint, params, retries + 1)
                    return None
                
                elif response.status_code == 429:
                    # Rate limited
                    logger.warning(f"Rate limited (429) for {endpoint}")
                    if proxy:
                        self.proxy_rotator.report_failure(proxy)
                    
                    if retries < settings.max_retries:
                        await asyncio.sleep(settings.retry_delay * 2 * (retries + 1))
                        return await self._make_request(endpoint, params, retries + 1)
                    return None
                
                else:
                    logger.warning(f"Unexpected status {response.status_code} for {endpoint}")
                    return None
        
        except httpx.TimeoutException:
            logger.warning(f"Timeout for {endpoint}")
            if proxy:
                self.proxy_rotator.report_failure(proxy)
            if retries < settings.max_retries:
                return await self._make_request(endpoint, params, retries + 1)
            return None
        
        except Exception as e:
            logger.error(f"Request error for {endpoint}: {e}")
            if proxy:
                self.proxy_rotator.report_failure(proxy)
            return None
    
    async def search_items(
        self,
        search_text: Optional[str] = None,
        catalog_ids: Optional[List[int]] = None,
        brand_ids: Optional[List[int]] = None,
        price_from: Optional[int] = None,
        price_to: Optional[int] = None,
        size_ids: Optional[List[int]] = None,
        status_ids: Optional[List[int]] = None,
        page: int = 1,
        per_page: int = 24
    ) -> List[Dict[str, Any]]:
        """Search for items on Vinted."""
        params = {
            "page": page,
            "per_page": per_page,
        }
        
        if search_text:
            params["search_text"] = search_text
        if catalog_ids:
            params["catalog_ids"] = ",".join(map(str, catalog_ids))
        if brand_ids:
            params["brand_ids"] = ",".join(map(str, brand_ids))
        if price_from:
            params["price_from"] = price_from
        if price_to:
            params["price_to"] = price_to
        if size_ids:
            params["size_ids"] = ",".join(map(str, size_ids))
        if status_ids:
            params["status_ids"] = ",".join(map(str, status_ids))
        
        data = await self._make_request("catalog/items", params)
        
        if data and "items" in data:
            return data["items"]
        return []
    
    async def get_item_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific item."""
        data = await self._make_request(f"items/{item_id}")
        
        if data and "item" in data:
            return data["item"]
        return None
    
    async def get_member_items(self, member_id: str, page: int = 1) -> List[Dict[str, Any]]:
        """Get all items from a specific member."""
        params = {"page": page, "per_page": 24}
        data = await self._make_request(f"wardrobe/{member_id}/items", params)
        
        if data and "items" in data:
            return data["items"]
        return []
    
    async def get_member_info(self, member_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a member."""
        data = await self._make_request(f"users/{member_id}")
        
        if data and "user" in data:
            return data["user"]
        return None
    
    async def get_brands(self) -> List[Dict[str, Any]]:
        """Get list of available brands."""
        data = await self._make_request("catalog/brands")
        
        if data:
            return data.get("brands", [])
        return []
    
    async def get_catalogs(self) -> List[Dict[str, Any]]:
        """Get list of catalog categories."""
        data = await self._make_request("catalogs")
        
        if data:
            return data.get("catalogs", [])
        return []


# Cache for scraper instances
_scraper_instances: Dict[str, VintedScraper] = {}


def get_scraper(domain: str = "vinted.de") -> VintedScraper:
    """Get or create a scraper instance for a domain."""
    if domain not in _scraper_instances:
        _scraper_instances[domain] = VintedScraper(domain)
    return _scraper_instances[domain]
