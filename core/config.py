"""Vinted Sniper API - Core configuration and settings."""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Proxy settings
    proxy_mode: str = "free"  # free or paid
    proxy_list_url: str = "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt"
    proxy_timeout: int = 10
    
    # Database
    database_url: str = "sqlite:///./vinted_sniper.db"
    
    # Polling settings
    poll_interval: int = 30  # seconds
    max_retries: int = 3
    retry_delay: int = 5  # seconds
    
    # Rate limiting
    requests_per_minute: int = 20
    concurrent_requests: int = 3
    
    # Vinted settings
    vinted_domain: str = "vinted.de"
    vinted_items_per_page: int = 24
    
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/vinted_sniper.log"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Vinted domain mappings
VINTED_DOMAINS = {
    "pl": "vinted.pl",
    "fr": "vinted.fr",
    "at": "vinted.at",
    "be": "vinted.be",
    "cz": "vinted.cz",
    "de": "vinted.de",
    "dk": "vinted.dk",
    "es": "vinted.es",
    "fi": "vinted.fi",
    "gr": "vinted.gr",
    "hr": "vinted.hr",
    "hu": "vinted.hu",
    "it": "vinted.it",
    "lt": "vinted.lt",
    "lu": "vinted.lu",
    "nl": "vinted.nl",
    "pt": "vinted.pt",
    "ro": "vinted.ro",
    "se": "vinted.se",
    "sk": "vinted.sk",
    "uk": "vinted.co.uk",
    "com": "vinted.com",
}

# Request headers to mimic browser
BROWSER_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}
