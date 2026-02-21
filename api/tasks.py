"""Background tasks for monitoring searches."""

import asyncio
from datetime import datetime
from loguru import logger

from core.models import Search, Item, SearchStatus, get_db_session
from core.scraper import get_scraper
from core.analyzer import ProfitAnalyzer
from api.websocket import manager


async def start_search_monitoring(search_id: int):
    """Start monitoring a search in the background."""
    logger.info(f"Starting monitoring for search {search_id}")
    
    while True:
        try:
            # Get fresh database session
            db = get_db_session()
            
            try:
                search = db.query(Search).filter(Search.id == search_id).first()
                
                if not search or search.status != SearchStatus.ACTIVE:
                    logger.info(f"Search {search_id} stopped or not found")
                    break
                
                # Perform search on Vinted
                await perform_search_check(db, search)
                
                # Update last check time
                search.last_check_at = datetime.utcnow()
                db.commit()
                
            finally:
                db.close()
            
            # Wait before next check
            await asyncio.sleep(search.check_interval)
            
        except Exception as e:
            logger.error(f"Error in monitoring task for search {search_id}: {e}")
            await asyncio.sleep(60)  # Wait before retrying


async def perform_search_check(db, search: Search):
    """Perform a single search check on Vinted."""
    domain = f"vinted.{search.country_code}" if search.country_code != "uk" else "vinted.co.uk"
    scraper = get_scraper(domain)
    analyzer = ProfitAnalyzer(domain)
    
    logger.info(f"Checking search '{search.name}' on {domain}")
    
    try:
        # Convert status IDs
        status_map = {
            "New with tags": [6],
            "New without tags": [1],
            "Very good": [2],
            "Good": [3],
            "Satisfactory": [4]
        }
        status_ids = []
        for condition in search.conditions:
            status_ids.extend(status_map.get(condition, []))
        
        # Search for items
        items = await scraper.search_items(
            search_text=search.keywords,
            catalog_ids=search.catalog_ids if search.catalog_ids else None,
            brand_ids=search.brand_ids if search.brand_ids else None,
            price_from=search.price_from,
            price_to=search.price_to,
            size_ids=search.size_ids if search.size_ids else None,
            status_ids=status_ids if status_ids else None,
            per_page=24
        )
        
        logger.info(f"Found {len(items)} items for search '{search.name}'")
        
        # Process each item
        new_items_count = 0
        for item_data in items:
            vinted_id = str(item_data.get("id"))
            
            # Check if already exists
            existing = db.query(Item).filter(Item.vinted_id == vinted_id).first()
            if existing:
                continue
            
            # Analyze profit potential
            try:
                analysis = await analyzer.analyze_item(item_data)
            except Exception as e:
                logger.warning(f"Analysis failed for item {vinted_id}: {e}")
                analysis = None
            
            # Create new item record
            photo_urls = []
            photos = item_data.get("photos", [])
            for photo in photos:
                url = photo.get("url", "")
                if url:
                    # Get high-res version
                    photo_urls.append(url.replace("thumbs", "f800"))
            
            user_data = item_data.get("user", {})
            item_url = item_data.get("url", f"https://www.{domain}/items/{vinted_id}")
            
            new_item = Item(
                vinted_id=vinted_id,
                title=item_data.get("title", "Unknown"),
                description=item_data.get("description", ""),
                price=int(float(item_data.get("price", 0)) * 100),  # Convert to cents
                currency=item_data.get("currency", "EUR"),
                brand=item_data.get("brand_title"),
                size=item_data.get("size_title"),
                condition=item_data.get("status", ""),
                url=item_url,
                image_urls=photo_urls,
                seller_id=str(user_data.get("id")),
                seller_username=user_data.get("login"),
                seller_rating=user_data.get("positive_feedback_count"),
                seller_location=user_data.get("city"),
                vinted_created_at=datetime.fromisoformat(item_data.get("created_at").replace("Z", "+00:00")) if item_data.get("created_at") else None,
                search_id=search.id,
                is_available=True
            )
            
            # Add analysis if available
            if analysis:
                new_item.market_price = int(analysis.estimated_market_price * 100) if analysis.estimated_market_price else None
                new_item.profit_potential = int(analysis.potential_profit * 100) if analysis.potential_profit else None
                new_item.profit_margin = analysis.profit_margin
                new_item.analysis_confidence = analysis.confidence_score
            
            db.add(new_item)
            new_items_count += 1
            
            # Notify via WebSocket if profitable
            if analysis and analysis.recommendation in ["buy", "watch"]:
                await manager.broadcast({
                    "type": "new_item",
                    "search_id": search.id,
                    "search_name": search.name,
                    "item": {
                        "id": vinted_id,
                        "title": new_item.title,
                        "price": new_item.price / 100,
                        "brand": new_item.brand,
                        "url": new_item.url,
                        "profit_potential": new_item.profit_potential / 100 if new_item.profit_potential else None,
                        "profit_margin": new_item.profit_margin,
                        "recommendation": analysis.recommendation
                    }
                })
        
        # Update search stats
        search.total_items_found += new_items_count
        search.new_items_today += new_items_count
        
        db.commit()
        
        logger.info(f"Added {new_items_count} new items for search '{search.name}'")
        
    except Exception as e:
        logger.error(f"Error performing search check: {e}")
        raise
