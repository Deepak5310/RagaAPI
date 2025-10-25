# RagaAPI - Gallery API

A FastAPI-based web scraping service for fetching actress gallery information from Ragalahari.com.

## Features

- 🚀 **FastAPI** backend with automatic OpenAPI documentation
- 🕷️ **Async web scraping** using aiohttp and BeautifulSoup4
- 📦 **In-memory caching** for improved performance
- 🔄 **CORS enabled** for cross-origin requests
- 📸 **High-quality image extraction** with automatic HD conversion
- 🎯 **Multiple scraping modes** (Latest galleries, Browse A-Z)
- 📱 **Album and photo management** per actress

## Project Structure

```
RagaAPI/
├── main.py              # FastAPI application and routes
├── app/
│   ├── __init__.py
│   ├── config.py        # Configuration settings
│   ├── models.py        # Pydantic data models
│   └── scraper.py       # Web scraping logic
├── requirements.txt     # Python dependencies
├── render.yaml          # Render.com deployment config
└── README.md
```

## Setup

### Prerequisites
- Python 3.11+
- pip

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/Deepak5310/RagaAPI.git
cd RagaAPI
```

2. **Create a virtual environment:**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Run the server:**
```bash
# Development mode with hot reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or using the main.py script
python main.py
```

5. **Access the API:**
- **API Base URL**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## API Endpoints

### 🏠 Root
```http
GET /
```
Health check endpoint.

**Response:**
```json
{
  "message": "Actress Gallery API",
  "version": "1.0.0",
  "status": "active"
}
```

---

### 🎬 Get Latest Galleries
```http
GET /api/ragalahari/latest
```
Fetch the latest actress galleries from Ragalahari.com home page.

**Response:**
```json
[
  {
    "id": "rh_174422",
    "name": "Actress Name",
    "thumbnail": "https://example.com/thumb.jpg",
    "age": null,
    "nationality": "Indian",
    "profession": "Actress",
    "source": "ragalahari"
  }
]
```

---

### 🔤 Browse by Letter
```http
GET /api/ragalahari/letter/{letter}
```
Get actresses whose names start with a specific letter (A-Z, excluding Q).

**Parameters:**
- `letter` (path): Single alphabetic character (e.g., "a", "m")

**Example:**
```http
GET /api/ragalahari/letter/s
```

---

### 👤 Get Actress Details
```http
GET /api/actress/{actress_id}
```
Get detailed information about a specific actress including images and albums.

**Parameters:**
- `actress_id` (path): Actress identifier (format: `rh_{id}`)

**Example:**
```http
GET /api/actress/rh_174422
```

**Response:**
```json
{
  "id": "rh_174422",
  "name": "Actress Name",
  "images": [
    "https://starzone.ragalahari.com/actress/174422/1.jpg",
    "https://starzone.ragalahari.com/actress/174422/2.jpg"
  ],
  "albums": [
    {
      "name": "Album Name",
      "url": "https://www.ragalahari.com/actress/174422/album-name.aspx",
      "thumbnail": "https://example.com/album-thumb.jpg"
    }
  ],
  "age": null,
  "birth_date": null,
  "nationality": "Indian",
  "profession": "Actress",
  "height": null,
  "bio": "Biography text...",
  "known_for": [],
  "social_media": {},
  "source": "ragalahari",
  "last_updated": "2025-10-18T12:00:00"
}
```

**Note:** Images are included only for actresses from "Latest" mode. Browse by letter returns only albums.

---

### 📷 Get Album Photos
```http
GET /api/album/photos?album_url={url}
```
Fetch all high-quality photos from a specific album.

**Query Parameters:**
- `album_url`: Full URL to the album page

**Example:**
```http
GET /api/album/photos?album_url=https://www.ragalahari.com/actress/174422/event-name.aspx
```

**Response:**
```json
[
  "https://starzone.ragalahari.com/actress/174422/1.jpg",
  "https://starzone.ragalahari.com/actress/174422/2.jpg",
  "https://starzone.ragalahari.com/actress/174422/3.jpg"
]
```

---

### 🔍 Search Actresses
```http
GET /api/search?query={text}&limit={number}
```
Search for actresses by name across all galleries.

**Query Parameters:**
- `query` (required): Search query (min 2 characters)
- `limit` (optional): Maximum results (1-100, default: 20)

**Example:**
```http
GET /api/search?query=samantha&limit=10
```

---

### 📁 Get Actress Albums (Deprecated)
```http
GET /api/actress/{actress_id}/albums
```
Get list of albums for an actress. **Use `/api/actress/{actress_id}` instead**, which includes albums in the response.

## Configuration

Configure via environment variables or `.env` file:

```bash
# API Settings
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Scraper Settings
REQUEST_TIMEOUT=30
MAX_RETRIES=3
USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Cache Settings
CACHE_ENABLED=true
CACHE_TTL=3600

# CORS Settings
ALLOWED_ORIGINS=["*"]
```

## Deployment

### Render.com

This project is configured for deployment on Render.com (see `render.yaml`).

1. Push to GitHub
2. Connect repository to Render
3. Deploy automatically using the provided configuration

**Live API**: Deployed at your Render.com URL

## Technical Details

### Scraping Strategy
- **Session pooling**: Reuses aiohttp sessions for efficiency
- **Image quality**: Automatically converts low-quality thumbnails (`t.jpg`) to HD images
- **URL normalization**: Handles protocol-relative and relative URLs
- **Ad filtering**: Removes Taboola ads and logo images
- **Caching**: In-memory cache for gallery URLs, slugs, and albums

### ID System
Actress IDs follow the format `rh_{gallery_id}`, where `gallery_id` is extracted from Ragalahari URLs:
- Format: `/actress/{id}/{gallery-name}.aspx`
- Example: `rh_174422` from `/actress/174422/event-photos.aspx`

### Two Scraping Modes
1. **Latest Mode**: Scrapes home page, returns images + albums in detail view
2. **Browse by Letter**: Scrapes A-Z pages, returns only albums (no images)

## Development

### Dependencies
- **FastAPI**: Modern async web framework
- **aiohttp**: Async HTTP client for scraping
- **BeautifulSoup4**: HTML parsing
- **Pydantic**: Data validation and settings management
- **uvicorn**: ASGI server

### Testing
Access the interactive API documentation at `/docs` to test all endpoints directly in your browser.

## Error Handling

The API returns appropriate HTTP status codes:
- `200`: Success
- `400`: Bad request (invalid parameters)
- `404`: Resource not found
- `500`: Server error

Example error response:
```json
{
  "detail": "Error message here"
}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## License

This project is for educational purposes. Please respect Ragalahari.com's terms of service and robots.txt when using this scraper.

## Author

**Deepak** - [GitHub](https://github.com/Deepak5310)

---

**Note**: This API is designed to work specifically with Ragalahari.com's structure. The scraping patterns may need updates if the website structure changes.
