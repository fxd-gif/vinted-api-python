# 🔥 Vinted API Python

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.109+-00a393.svg?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/async-await-orange.svg?style=for-the-badge" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge" />
</p>

<p align="center">
  <b>Unofficial Python API for Vinted</b><br>
  Search listings • Analyze deals • Find profitable items • Automated alerts
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-api-endpoints">API</a> •
  <a href="#-installation">Install</a> •
  <a href="#-examples">Examples</a>
</p>

---

## 🚀 Features

- ⚡ **Async Support** - Lightning fast concurrent requests with `asyncio` + `httpx`
- 🔍 **Advanced Search** - Filter by price, brand, size, condition, location
- 💰 **Profit Analysis** - Automatic market price comparison & ROI calculation  
- 🔄 **Proxy Rotation** - Built-in proxy support to avoid rate limits
- 🛡️ **Anti-Detection** - Smart request throttling, header rotation, cookie persistence
- 🌐 **Multi-Domain** - Works with all Vinted domains (DE, FR, UK, PL, etc.)
- 📊 **FastAPI Backend** - REST API with auto-generated docs
- 🔌 **WebSocket Ready** - Real-time deal alerts

---

## 📦 Installation

```bash
# Clone repository
git clone https://github.com/Fxd-gif/vinted-api-python.git
cd vinted-api-python

# Install dependencies
pip install -r requirements.txt

# Or install as package
pip install -e .
```

### Requirements
- Python 3.9+
- httpx
- fake-useragent
- beautifulsoup4
- FastAPI (for API server)

---

## 🎯 Quick Start

### As Python Library

```python
import asyncio
from core.scraper import VintedScraper
from core.analyzer import ProfitAnalyzer

async def main():
    # Initialize scraper
    scraper = VintedScraper(domain="vinted.de")
    analyzer = ProfitAnalyzer()
    
    # Search for items
    print("🔍 Searching for deals...")
    items = await scraper.search_items(
        search_text="Ralph Lauren",
        price_to=5000,  # 50€
        per_page=10
    )
    
    # Analyze profit potential
    for item in items[:3]:
        analysis = await analyzer.analyze_item(item)
        
        print(f"\n👕 {item['title']}")
        print(f"💶 Price: {item['price']}€")
        print(f"📈 Est. Resale: {analysis.estimated_market_price:.2f}€")
        print(f"💰 Profit: {analysis.potential_profit:.2f}€ ({analysis.profit_margin:.0f}%)")
        print(f"🎯 Recommendation: {analysis.recommendation}")
        print(f"🔗 {item['url']}")

asyncio.run(main())
```

**Output:**
```
🔍 Searching for deals...

👕 Ralph Lauren Pullover pink/lila
💶 Price: 19.00€
📈 Est. Resale: 50.00€
💰 Profit: 25.55€ (134%)
🎯 Recommendation: BUY
🔗 https://www.vinted.de/items/123456...
```

### Run API Server

```bash
# Start FastAPI server
python run.py

# Or with uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Server runs at `http://localhost:8000`

API docs auto-generated at: `http://localhost:8000/docs`

---

## 🌐 API Endpoints

### Search Items
```http
GET /search?q=nike&price_to=50&per_page=24
```

**Parameters:**
- `q` - Search query (required)
- `brand_id` - Filter by brand ID
- `price_from` - Minimum price (cents)
- `price_to` - Maximum price (cents)
- `per_page` - Results per page (1-50)

**Response:**
```json
{
  "items": [
    {
      "id": "123456789",
      "title": "Nike Air Max 90",
      "price": "45.00",
      "currency": "EUR",
      "brand_title": "Nike",
      "url": "https://www.vinted.de/items/123456789-nike-air-max",
      "photo": { "url": "..." }
    }
  ],
  "total": 24,
  "query": "nike"
}
```

### Get Item Details
```http
GET /item/123456789
```

### Analyze Profit
```http
GET /item/123456789/analyze
```

**Response:**
```json
{
  "item": {
    "id": "123456789",
    "title": "Nike Air Max 90",
    "price": 45.00
  },
  "analysis": {
    "market_price": 85.00,
    "profit_potential": 35.25,
    "profit_margin": 78.3,
    "recommendation": "BUY"
  }
}
```

### List Brands
```http
GET /brands
```

### List Categories
```http
GET /catalogs
```

---

## 💡 Examples

### Find Deals Under Budget

```python
async def find_budget_deals(budget_eur=30):
    """Find items under €30 with high resale potential."""
    scraper = VintedScraper()
    analyzer = ProfitAnalyzer()
    
    items = await scraper.search_items(
        search_text="vintage",
        price_to=budget_eur * 100,
        per_page=50
    )
    
    deals = []
    for item in items:
        analysis = await analyzer.analyze_item(item)
        if analysis.profit_margin > 50:  # 50%+ profit
            deals.append({
                "item": item,
                "analysis": analysis
            })
    
    # Sort by profit
    deals.sort(key=lambda x: x['analysis'].potential_profit, reverse=True)
    return deals[:10]
```

### Monitor New Listings

```python
import asyncio

async def monitor_listings(keyword, interval=60):
    """Monitor Vinted for new listings every minute."""
    scraper = VintedScraper()
    seen_ids = set()
    
    while True:
        items = await scraper.search_items(
            search_text=keyword,
            per_page=10
        )
        
        for item in items:
            if item['id'] not in seen_ids:
                seen_ids.add(item['id'])
                print(f"🆕 New: {item['title']} - {item['price']}€")
        
        await asyncio.sleep(interval)

# Run monitor
asyncio.run(monitor_listings("nike dunk"))
```

### Use with Proxies

```python
from core.proxy_rotator import ProxyRotator

# Load free proxies
rotator = ProxyRotator()
await rotator.load_free_proxies()

# Or use your own proxy
scraper = VintedScraper(
    domain="vinted.de",
    proxy="http://user:pass@proxy:8080"
)
```

---

## 🛡️ Rate Limiting & Best Practices

The scraper includes built-in protections:

- ⏱️ **Random delays** (1-3s between requests)
- 🎭 **User-Agent rotation** (real browser strings)
- 🍪 **Cookie persistence** (maintains session)
- 🔄 **Automatic retry** (exponential backoff)

**Be respectful:**
- Don't hammer the servers with requests
- Use reasonable delays
- Consider their infrastructure

---

## 🌍 Supported Domains

| Domain | Country |
|--------|---------|
| `vinted.de` | 🇩🇪 Germany |
| `vinted.fr` | 🇫🇷 France |
| `vinted.co.uk` | 🇬🇧 UK |
| `vinted.pl` | 🇵🇱 Poland |
| `vinted.it` | 🇮🇹 Italy |
| `vinted.es` | 🇪🇸 Spain |
| `vinted.nl` | 🇳🇱 Netherlands |
| `vinted.com` | 🇺🇸 USA |

---

## 🔧 Advanced Configuration

```python
from core.scraper import VintedScraper

# Custom configuration
scraper = VintedScraper(
    domain="vinted.de",
    min_request_interval=3.0,  # Seconds between requests
    max_retries=5,
    timeout=30
)
```

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Ideas for contributions:**
- More marketplace integrations (Depop, Poshmark, eBay)
- Better profit analysis algorithms
- Machine learning for price prediction
- Telegram/Discord bot integration
- Chrome extension

---

## ⚠️ Disclaimer

This is an **unofficial** API wrapper. Not affiliated with or endorsed by Vinted.

- Use responsibly and respect rate limits
- Don't overwhelm their servers
- This is for educational purposes
- Always comply with Vinted's Terms of Service

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file

---

## 🌟 Star History

If you find this useful, please consider starring the repo!

[![Star History Chart](https://api.star-history.com/svg?repos=Fxd-gif/vinted-api-python&type=Date)](https://star-history.com/#Fxd-gif/vinted-api-python&Date)

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/Fxd-gif">Fxd-gif</a>
</p>

<p align="center">
  <a href="https://github.com/Fxd-gif/vinted-api-python/stargazers">⭐ Star this repo</a> •
  <a href="https://github.com/Fxd-gif/vinted-api-python/issues">🐛 Report bug</a> •
  <a href="https://github.com/Fxd-gif/vinted-api-python/fork">🔀 Fork it</a>
</p>
