# Vinted API

Unofficial Python API & FastAPI backend for Vinted marketplace.

## Features

- 🔍 **Search Items** - Query Vinted catalog with filters
- 💰 **Profit Analysis** - Calculate resale value and margins
- 🔄 **Proxy Rotation** - Built-in proxy support
- ⚡ **Async** - Fast concurrent requests
- 🛡️ **Rate Limiting** - Smart delays to avoid blocks

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```bash
# Run API server
python run.py

# Or with uvicorn
uvicorn main:app --reload
```

## API Endpoints

```
GET /search?q=nike&price_to=50
GET /item/123456
GET /item/123456/analyze
GET /brands
GET /catalogs
```

## Usage Example

```python
import asyncio
from core.scraper import VintedScraper
from core.analyzer import ProfitAnalyzer

async def main():
    scraper = VintedScraper("vinted.de")
    analyzer = ProfitAnalyzer()
    
    # Search
    items = await scraper.search_items("Ralph Lauren", price_to=5000)
    
    # Analyze
    for item in items[:3]:
        analysis = await analyzer.analyze_item(item)
        print(f"Profit: {analysis.potential_profit:.2f}€")

asyncio.run(main())
```

## Disclaimer

For educational purposes. Respect Vinted's Terms of Service.

## License

MIT
