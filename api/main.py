"""Main FastAPI application."""

import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from core.config import get_settings
from core.models import init_db, get_db, Search, Item, SearchStatus
from core.proxy_rotator import get_proxy_rotator
from core.scraper import get_scraper
from core.analyzer import ProfitAnalyzer
from api.schemas import (
    SearchCreate, SearchUpdate, SearchResponse, SearchListResponse,
    ItemResponse, ItemListResponse, HealthResponse, StatsResponse
)
from api.websocket import ConnectionManager

# Initialize settings
settings = get_settings()
start_time = time.time()

# Initialize connection manager for WebSocket
manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    init_db()
    
    # Load and validate proxies
    proxy_rotator = get_proxy_rotator()
    await proxy_rotator.load_free_proxies()
    
    print(f"Loaded {proxy_rotator.get_proxy_count()['total']} proxies")
    
    yield
    
    # Shutdown
    print("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Vinted Sniper API",
    description="API for monitoring Vinted listings and finding profitable resale opportunities",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "name": "Vinted Sniper API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    proxy_stats = get_proxy_rotator().get_proxy_count()
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        proxy_stats=proxy_stats
    )


@app.get("/stats", response_model=StatsResponse, tags=["Stats"])
async def get_stats(db: Session = Depends(get_db)):
    """Get system statistics."""
    total_searches = db.query(Search).count()
    active_searches = db.query(Search).filter(Search.status == SearchStatus.ACTIVE).count()
    total_items = db.query(Item).count()
    
    # Items discovered today
    from sqlalchemy import func
    from datetime import date
    today = date.today()
    items_today = db.query(Item).filter(
        func.date(Item.discovered_at) == today
    ).count()
    
    proxy_stats = get_proxy_rotator().get_proxy_count()
    uptime = time.time() - start_time
    
    return StatsResponse(
        total_searches=total_searches,
        active_searches=active_searches,
        total_items=total_items,
        items_today=items_today,
        proxy_stats=proxy_stats,
        uptime_seconds=uptime
    )


# Search endpoints

@app.post("/searches", response_model=SearchResponse, status_code=201, tags=["Searches"])
async def create_search(
    search_data: SearchCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new search configuration."""
    search = Search(
        name=search_data.name,
        description=search_data.description,
        keywords=search_data.keywords,
        brand_ids=search_data.brand_ids or [],
        catalog_ids=search_data.catalog_ids or [],
        size_ids=search_data.size_ids or [],
        price_from=search_data.price_from,
        price_to=search_data.price_to,
        conditions=search_data.conditions or [],
        country_code=search_data.country_code,
        seller_min_rating=search_data.seller_min_rating,
        check_interval=search_data.check_interval,
        status=SearchStatus.ACTIVE
    )
    
    db.add(search)
    db.commit()
    db.refresh(search)
    
    # Start background monitoring task
    from api.tasks import start_search_monitoring
    background_tasks.add_task(start_search_monitoring, search.id)
    
    return search.to_dict()


@app.get("/searches", response_model=SearchListResponse, tags=["Searches"])
async def list_searches(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all searches with optional filtering."""
    query = db.query(Search)
    
    if status:
        query = query.filter(Search.status == status)
    
    total = query.count()
    searches = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return SearchListResponse(
        searches=[s.to_dict() for s in searches],
        total=total,
        page=page,
        per_page=per_page
    )


@app.get("/searches/{search_id}", response_model=SearchResponse, tags=["Searches"])
async def get_search(search_id: int, db: Session = Depends(get_db)):
    """Get a specific search by ID."""
    search = db.query(Search).filter(Search.id == search_id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    return search.to_dict()


@app.patch("/searches/{search_id}", response_model=SearchResponse, tags=["Searches"])
async def update_search(
    search_id: int,
    search_data: SearchUpdate,
    db: Session = Depends(get_db)
):
    """Update a search configuration."""
    search = db.query(Search).filter(Search.id == search_id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    
    if search_data.name is not None:
        search.name = search_data.name
    if search_data.description is not None:
        search.description = search_data.description
    if search_data.status is not None:
        search.status = search_data.status
    if search_data.check_interval is not None:
        search.check_interval = search_data.check_interval
    
    db.commit()
    db.refresh(search)
    
    return search.to_dict()


@app.delete("/searches/{search_id}", status_code=204, tags=["Searches"])
async def delete_search(search_id: int, db: Session = Depends(get_db)):
    """Delete a search and all its items."""
    search = db.query(Search).filter(Search.id == search_id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    
    db.delete(search)
    db.commit()
    
    return {"message": "Search deleted"}


# Item endpoints

@app.get("/searches/{search_id}/items", response_model=ItemListResponse, tags=["Items"])
async def get_search_items(
    search_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    min_profit: Optional[float] = None,
    recommendation: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get items found by a specific search."""
    search = db.query(Search).filter(Search.id == search_id).first()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    
    query = db.query(Item).filter(Item.search_id == search_id)
    
    # Apply filters
    if min_profit is not None:
        query = query.filter(Item.profit_potential >= min_profit * 100)  # Convert to cents
    if recommendation:
        # This is a simplification - in reality you'd store the recommendation
        pass
    
    total = query.count()
    items = query.order_by(Item.discovered_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    
    return ItemListResponse(
        items=[i.to_dict() for i in items],
        total=total,
        page=page,
        per_page=per_page,
        has_more=page * per_page < total
    )


@app.get("/items/{item_id}", response_model=ItemResponse, tags=["Items"])
async def get_item(item_id: int, db: Session = Depends(get_db)):
    """Get detailed information about an item."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item.to_dict()


@app.post("/items/{item_id}/refresh", tags=["Items"])
async def refresh_item_analysis(item_id: int, db: Session = Depends(get_db)):
    """Refresh profit analysis for an item."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Re-analyze
    scraper = get_scraper(item.search.country_code)
    item_data = await scraper.get_item_details(item.vinted_id)
    
    if item_data:
        analyzer = ProfitAnalyzer(item.search.country_code)
        analysis = await analyzer.analyze_item(item_data)
        
        item.market_price = int(analysis.estimated_market_price * 100) if analysis.estimated_market_price else None
        item.profit_potential = int(analysis.potential_profit * 100) if analysis.potential_profit else None
        item.profit_margin = analysis.profit_margin
        item.analysis_confidence = analysis.confidence_score
        
        db.commit()
        db.refresh(item)
    
    return item.to_dict()


# Catalog endpoints

@app.get("/catalogs/brands", tags=["Catalog"])
async def get_brands(domain: str = "vinted.de"):
    """Get list of available brands from Vinted."""
    scraper = get_scraper(domain)
    brands = await scraper.get_brands()
    return {"brands": brands}


@app.get("/catalogs/categories", tags=["Catalog"])
async def get_categories(domain: str = "vinted.de"):
    """Get list of catalog categories from Vinted."""
    scraper = get_scraper(domain)
    catalogs = await scraper.get_catalogs()
    return {"categories": catalogs}


# WebSocket for real-time updates

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time notifications."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, wait for client messages
            data = await websocket.receive_text()
            # Echo back or handle commands
            await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
