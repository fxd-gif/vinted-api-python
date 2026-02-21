"""Pydantic models for API request/response validation."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator


class SearchCreate(BaseModel):
    """Model for creating a new search."""
    name: str = Field(..., min_length=1, max_length=255, description="Search name")
    description: Optional[str] = Field(None, max_length=1000)
    
    # Search filters
    keywords: Optional[str] = Field(None, description="Search keywords")
    brand_ids: Optional[List[int]] = Field(default_factory=list)
    catalog_ids: Optional[List[int]] = Field(default_factory=list)
    size_ids: Optional[List[int]] = Field(default_factory=list)
    price_from: Optional[int] = Field(None, ge=0, description="Minimum price in cents")
    price_to: Optional[int] = Field(None, ge=0, description="Maximum price in cents")
    conditions: Optional[List[str]] = Field(default_factory=list)
    country_code: str = Field(default="de", min_length=2, max_length=10)
    seller_min_rating: Optional[int] = Field(None, ge=0)
    
    # Monitoring settings
    check_interval: int = Field(default=30, ge=10, le=3600, description="Check interval in seconds")
    
    @validator('price_to')
    def price_to_greater_than_from(cls, v, values):
        if v is not None and values.get('price_from') is not None:
            if v < values['price_from']:
                raise ValueError('price_to must be greater than or equal to price_from')
        return v


class SearchUpdate(BaseModel):
    """Model for updating a search."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[str] = Field(None, regex="^(active|paused|stopped)$")
    check_interval: Optional[int] = Field(None, ge=10, le=3600)


class SearchResponse(BaseModel):
    """Model for search response."""
    id: int
    name: str
    description: Optional[str]
    keywords: Optional[str]
    brand_ids: List[int]
    catalog_ids: List[int]
    size_ids: List[int]
    price_from: Optional[int]
    price_to: Optional[int]
    conditions: List[str]
    country_code: str
    seller_min_rating: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime
    last_check_at: Optional[datetime]
    check_interval: int
    total_items_found: int
    new_items_today: int
    
    class Config:
        from_attributes = True


class SellerInfo(BaseModel):
    """Seller information."""
    id: Optional[str]
    username: Optional[str]
    rating: Optional[int]
    location: Optional[str]


class ItemAnalysis(BaseModel):
    """Profit analysis for an item."""
    market_price: Optional[float]
    profit_potential: Optional[float]
    profit_margin: Optional[float]
    confidence: Optional[float]
    recommendation: Optional[str]


class ItemResponse(BaseModel):
    """Model for item response."""
    id: int
    vinted_id: str
    title: str
    description: Optional[str]
    price: float
    currency: str
    original_price: Optional[float]
    brand: Optional[str]
    size: Optional[str]
    condition: Optional[str]
    color: Optional[str]
    url: str
    image_urls: List[str]
    seller: SellerInfo
    is_available: bool
    vinted_created_at: Optional[datetime]
    discovered_at: datetime
    analysis: ItemAnalysis
    
    class Config:
        from_attributes = True


class ItemListResponse(BaseModel):
    """Paginated item list response."""
    items: List[ItemResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


class SearchListResponse(BaseModel):
    """Paginated search list response."""
    searches: List[SearchResponse]
    total: int
    page: int
    per_page: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str = "1.0.0"
    timestamp: datetime
    proxy_stats: dict


class StatsResponse(BaseModel):
    """System statistics response."""
    total_searches: int
    active_searches: int
    total_items: int
    items_today: int
    proxy_stats: dict
    uptime_seconds: float
