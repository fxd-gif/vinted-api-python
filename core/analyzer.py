"""Profit analysis for Vinted items."""

import asyncio
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from loguru import logger

from core.scraper import get_scraper


@dataclass
class ProfitAnalysis:
    """Profit analysis result."""
    item_price: float  # EUR
    estimated_market_price: float  # EUR
    vinted_fees: float  # EUR (approx 5% protection fee + shipping)
    shipping_cost: float  # EUR
    potential_profit: float  # EUR
    profit_margin: float  # Percentage
    confidence_score: float  # 0-1
    comparable_items: int  # Number of items used for estimation
    recommendation: str  # "buy", "watch", "skip"


class ProfitAnalyzer:
    """Analyzes potential profit for Vinted items."""
    
    def __init__(self, domain: str = "vinted.de"):
        self.domain = domain
        self.scraper = get_scraper(domain)
    
    async def analyze_item(
        self, 
        item_data: Dict[str, Any],
        force_refresh: bool = False
    ) -> ProfitAnalysis:
        """Analyze profit potential for an item."""
        
        # Extract item details
        item_price = float(item_data.get("price", 0))
        title = item_data.get("title", "")
        brand = item_data.get("brand_title", "")
        size = item_data.get("size_title", "")
        
        # Vinted fees (approximate)
        protection_fee_rate = 0.05  # 5% buyer protection fee
        protection_fee = item_price * protection_fee_rate
        shipping_cost = 4.50  # Standard shipping estimate
        
        # Estimate market price by searching comparable sold items
        market_price, confidence, comparables = await self._estimate_market_price(
            title=title,
            brand=brand,
            size=size
        )
        
        # Calculate profit
        total_cost = item_price + protection_fee + shipping_cost
        potential_profit = market_price - total_cost
        profit_margin = (potential_profit / item_price) * 100 if item_price > 0 else 0
        
        # Recommendation logic
        if potential_profit > 20 and profit_margin > 40 and confidence > 0.6:
            recommendation = "buy"
        elif potential_profit > 10 and profit_margin > 25 and confidence > 0.5:
            recommendation = "watch"
        else:
            recommendation = "skip"
        
        return ProfitAnalysis(
            item_price=item_price,
            estimated_market_price=market_price,
            vinted_fees=protection_fee,
            shipping_cost=shipping_cost,
            potential_profit=potential_profit,
            profit_margin=profit_margin,
            confidence_score=confidence,
            comparable_items=comparables,
            recommendation=recommendation
        )
    
    async def _estimate_market_price(
        self,
        title: str,
        brand: str,
        size: str
    ) -> tuple[float, float, int]:
        """Estimate market price by searching comparable items."""
        
        try:
            # Search for similar items currently listed
            keywords = self._extract_keywords(title)
            search_query = " ".join([brand] + keywords[:3]) if brand else " ".join(keywords[:4])
            
            comparable_items = await self.scraper.search_items(
                search_text=search_query,
                per_page=20
            )
            
            if not comparable_items:
                # No comparables found, return conservative estimate
                return 0, 0.0, 0
            
            # Filter items with same brand and similar size
            similar_items = []
            for item in comparable_items:
                item_brand = item.get("brand_title", "").lower()
                item_size = item.get("size_title", "")
                
                # Check brand match
                if brand and brand.lower() not in item_brand:
                    continue
                
                # Check size match (flexible matching)
                if size and not self._size_matches(size, item_size):
                    continue
                
                price = float(item.get("price", 0))
                if price > 0:
                    similar_items.append(price)
            
            if not similar_items:
                # Use all items if no exact matches
                prices = [float(item.get("price", 0)) for item in comparable_items if float(item.get("price", 0)) > 0]
            else:
                prices = similar_items
            
            if not prices:
                return 0, 0.0, 0
            
            # Calculate median price (more robust than mean)
            prices.sort()
            n = len(prices)
            
            if n % 2 == 0:
                median_price = (prices[n//2 - 1] + prices[n//2]) / 2
            else:
                median_price = prices[n//2]
            
            # Remove outliers (prices outside 1.5 IQR)
            q1 = prices[n//4] if n >= 4 else prices[0]
            q3 = prices[3*n//4] if n >= 4 else prices[-1]
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            filtered_prices = [p for p in prices if lower_bound <= p <= upper_bound]
            
            if filtered_prices:
                estimated_price = sum(filtered_prices) / len(filtered_prices)
            else:
                estimated_price = median_price
            
            # Confidence based on number of comparables
            confidence = min(0.9, 0.3 + (n / 20) * 0.6)  # Max 0.9 at 20+ items
            
            return estimated_price, confidence, n
        
        except Exception as e:
            logger.error(f"Error estimating market price: {e}")
            return 0, 0.0, 0
    
    def _extract_keywords(self, title: str) -> List[str]:
        """Extract important keywords from title."""
        # Remove common words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
            "neu", "neue", "neuer", "neues", "mit", "und", "oder", "für", "von",
            "die", "der", "das", "den", "dem", "ein", "eine", "einer", "eines"
        }
        
        words = title.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return keywords
    
    def _size_matches(self, size1: str, size2: str) -> bool:
        """Check if two sizes match (flexible matching)."""
        # Normalize sizes
        s1 = size1.lower().replace(" ", "").replace(".", "")
        s2 = size2.lower().replace(" ", "").replace(".", "")
        
        # Direct match
        if s1 == s2:
            return True
        
        # Handle EU sizes (e.g., "EU42" vs "42")
        if "eu" in s1 and s1.replace("eu", "") == s2:
            return True
        if "eu" in s2 and s2.replace("eu", "") == s1:
            return True
        
        # Handle US/UK sizes
        if s1.startswith(("us", "uk")) and s1[2:] in s2:
            return True
        if s2.startswith(("us", "uk")) and s2[2:] in s1:
            return True
        
        return False
    
    async def analyze_batch(
        self,
        items: List[Dict[str, Any]]
    ) -> List[tuple[Dict[str, Any], ProfitAnalysis]]:
        """Analyze multiple items in parallel."""
        tasks = [self.analyze_item(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        analyses = []
        for item, result in zip(items, results):
            if isinstance(result, Exception):
                logger.error(f"Analysis failed for item {item.get('id')}: {result}")
                continue
            analyses.append((item, result))
        
        return analyses
