# RagaAPI

FastAPI-based async web scraper for Ragalahari.com actress galleries. Fetches latest galleries, browse A-Z, albums, and high-quality images.

## Features

- � Async scraping with aiohttp & BeautifulSoup4
- � Auto HD image conversion (`t.jpg` → `.jpg`)
- 🔄 In-memory caching for performance
- � Album pagination support
- 🎯 Two scraping modes (Latest/Browse)
- � Auto-generated API docs

## Quick Start

```bash
# Clone & setup
git clone https://github.com/Deepak5310/RagaAPI.git
cd RagaAPI
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install & run
pip install -r requirements.txt
python main.py

# Access at http://localhost:8000/docs
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/api/ragalahari/latest` | GET | Latest 20 galleries |
| `/api/ragalahari/letter/{a-z}` | GET | Browse by first letter |
| `/api/actress/{id}` | GET | Actress detail (images + albums) |
| `/api/actress/{id}/albums` | GET | Actress albums only |
| `/api/album/photos?album_url=...` | GET | All photos from album |
| `/api/search?query=...&limit=20` | GET | Search actresses |

### Example Usage

**Get latest galleries:**
```bash
curl http://localhost:8000/api/ragalahari/latest
```

**Browse by letter:**
```bash
curl http://localhost:8000/api/ragalahari/letter/s
```

**Get actress details:**
```bash
curl http://localhost:8000/api/actress/rh_174422
```

**Response format:**
```json
{
  "id": "rh_174422",
  "name": "Actress Name",
  "images": ["https://starzone.ragalahari.com/.../1.jpg"],
  "albums": [{"name": "Album", "url": "...", "thumbnail": "..."}],
  "source": "ragalahari"
}
```

**Search:**
```bash
curl "http://localhost:8000/api/search?query=samantha&limit=10"
```

**Album photos:**
```bash
curl "http://localhost:8000/api/album/photos?album_url=https://www.ragalahari.com/actress/174422/event.aspx"
```

## Configuration

Optional `.env` file (defaults in `app/config.py`):

```bash
HOST=0.0.0.0
PORT=8000
DEBUG=True
REQUEST_TIMEOUT=30
USER_AGENT="Mozilla/5.0..."
```

## Deployment

### Railway.app (Recommended)

Zero-config deployment - Railway auto-detects everything!

```bash
# 1. Push to GitHub
git push origin main

# 2. Deploy on Railway
# - Go to railway.app
# - Login with GitHub
# - New Project → Deploy from GitHub
# - Select RagaAPI → Auto-deploys!
```

**Free:** $5 credit/month | **URL:** `your-app.up.railway.app`

## How It Works

### Two Scraping Modes

1. **Latest Mode** (`/api/ragalahari/latest`)
   - Scrapes homepage
   - Returns images + albums in detail view

2. **Browse Mode** (`/api/ragalahari/letter/{a-z}`)
   - Scrapes A-Z pages
   - Returns albums only (no images)

### ID System

Format: `rh_{gallery_id}` (e.g., `/actress/174422/...` → `rh_174422`)

### Tech Stack

- FastAPI 0.104+ - Modern async framework
- aiohttp 3.12+ - Async HTTP client
- BeautifulSoup4 4.12+ - HTML parsing
- Pydantic 2.5+ - Data validation

## License

Educational purposes only. Respect Ragalahari.com's ToS.

---

**Made by [Deepak](https://github.com/Deepak5310)**
