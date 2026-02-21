"""Proxy management for rotating requests."""

import asyncio
import random
from datetime import datetime
from typing import List, Optional
import httpx
from loguru import logger

from core.config import get_settings
from core.models import Proxy, SessionLocal

settings = get_settings()


class ProxyRotator:
    """Manages a pool of proxies for request rotation."""
    
    def __init__(self):
        self.proxies: List[Proxy] = []
        self.current_index = 0
        self._lock = asyncio.Lock()
    
    async def load_free_proxies(self) -> int:
        """Load free proxies from public lists."""
        loaded = 0
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Try multiple free proxy sources
                sources = [
                    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
                    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
                    "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all",
                ]
                
                for url in sources:
                    try:
                        response = await client.get(url)
                        if response.status_code == 200:
                            proxy_lines = response.text.strip().split('\n')
                            
                            for line in proxy_lines:
                                line = line.strip()
                                if not line or ':' not in line:
                                    continue
                                
                                try:
                                    host, port = line.split(':')
                                    port = int(port)
                                    
                                    # Check if already exists
                                    if not any(p.host == host and p.port == port for p in self.proxies):
                                        proxy = Proxy(host=host, port=port, protocol="http")
                                        self.proxies.append(proxy)
                                        loaded += 1
                                except ValueError:
                                    continue
                            
                            logger.info(f"Loaded {len(proxy_lines)} proxies from {url}")
                    except Exception as e:
                        logger.warning(f"Failed to load from {url}: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Error loading free proxies: {e}")
        
        logger.info(f"Total free proxies loaded: {len(self.proxies)}")
        return loaded
    
    def get_next_proxy(self) -> Optional[Proxy]:
        """Get next proxy in rotation."""
        if not self.proxies:
            return None
        
        # Filter active proxies
        active_proxies = [p for p in self.proxies if p.is_active]
        if not active_proxies:
            return None
        
        # Weight by success rate
        weights = []
        for p in active_proxies:
            total = p.success_count + p.fail_count
            if total == 0:
                weights.append(1.0)  # New proxy
            else:
                weights.append(p.success_count / total)
        
        # Select weighted random proxy
        proxy = random.choices(active_proxies, weights=weights, k=1)[0]
        proxy.last_used_at = datetime.utcnow()
        
        return proxy
    
    def report_success(self, proxy: Proxy):
        """Report successful request with proxy."""
        proxy.success_count += 1
        proxy.last_success_at = datetime.utcnow()
    
    def report_failure(self, proxy: Proxy):
        """Report failed request with proxy."""
        proxy.fail_count += 1
        if proxy.fail_count > 5 and proxy.fail_count / (proxy.fail_count + proxy.success_count) > 0.8:
            proxy.is_active = False
            logger.warning(f"Deactivated proxy {proxy.host}:{proxy.port} (success rate too low)")
    
    async def validate_proxies(self, sample_size: int = 10) -> int:
        """Validate a sample of proxies by making test requests."""
        if not self.proxies:
            return 0
        
        test_url = f"https://www.{settings.vinted_domain}"
        test_proxies = random.sample(self.proxies, min(sample_size, len(self.proxies)))
        valid_count = 0
        
        async with httpx.AsyncClient(timeout=settings.proxy_timeout) as client:
            for proxy in test_proxies:
                try:
                    response = await client.get(
                        test_url,
                        proxy=proxy.url,
                        follow_redirects=True
                    )
                    if response.status_code == 200:
                        proxy.is_active = True
                        proxy.last_success_at = datetime.utcnow()
                        valid_count += 1
                    else:
                        proxy.fail_count += 1
                except Exception as e:
                    proxy.fail_count += 1
                    if proxy.fail_count > 3:
                        proxy.is_active = False
        
        logger.info(f"Proxy validation: {valid_count}/{len(test_proxies)} working")
        return valid_count
    
    def get_proxy_count(self) -> dict:
        """Get proxy statistics."""
        total = len(self.proxies)
        active = sum(1 for p in self.proxies if p.is_active)
        return {"total": total, "active": active}


# Global proxy rotator instance
_proxy_rotator: Optional[ProxyRotator] = None


def get_proxy_rotator() -> ProxyRotator:
    """Get or create global proxy rotator."""
    global _proxy_rotator
    if _proxy_rotator is None:
        _proxy_rotator = ProxyRotator()
    return _proxy_rotator
