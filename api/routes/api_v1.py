"""API routes for Vinted endpoints."""

from typing import Optional
from fastapi import APIRouter, Query

from core.scraper import get_scraper
from core.analyzer import ProfitAnalyzer

router = APIRouter()

@router.get("/search")
async def search_items(
    q: str,
    brand_id: Optional[int] = None,
    price_from: Optional[int] = None,
    price_to: Optional[int] = None,
    per_page: int = Query(24, ge=1, le=50)
):
    """Search Vinted items."""
    scraper = get_scraper("vinted.de")
    
    items = await scraper.search_items(
        search_text=q,
        brand_ids=[brand_id] if brand_id else None,
        price_from=price_from,
        price_to=price_to,
        per_page=per_page
    )
    
    return {
        "items": items,
        "total": len(items),
        "query": q
    }

@router.get("/item/{item_id}")
async def get_item(item_id: str):
    """Get item details."""
    scraper = get_scraper("vinted.de")
    item = await scraper.get_item_details(item_id)
    
    if not item:
        return {"error": "Item not found"}
    
    return item

@router.get("/item/{item_id}/analyze")
async def analyze_item(item_id: str):
    """Analyze profit potential."""
    scraper = get_scraper("vinted.de")
    analyzer = ProfitAnalyzer("vinted.de")
    
    item = await scraper.get_item_details(item_id)
    if not item:
        return {"error": "Item not found"}
    
    analysis = await analyzer.analyze_item(item)
    
    return {
        "item": {
            "id": item_id,
            "title": item.get("title"),
            "price": float(item.get("price", {}).get("amount", 0)),
        },
        "analysis": {
            "market_price": analysis.estimated_market_price,
            "profit_potential": analysis.potential_profit,
            "profit_margin": analysis.profit_margin,
            "recommendation": analysis.recommendation
        }
    }

@router.get("/brands")
async def get_brands():
    """List available brands."""
    scraper = get_scraper("vinted.de")
    brands = await scraper.get_brands()
    return {"brands": brands}

@router.get("/catalogs")
async def get_catalogs():
    """List categories."""
    scraper = get_scraper("vinted.de")
    catalogs = await scraper.get_catalogs()
    return {"catalogs": catalogs}
