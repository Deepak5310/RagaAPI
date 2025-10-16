# Web Scraping API

A FastAPI-based web scraping service using BeautifulSoup.

## Features

- FastAPI backend
- BeautifulSoup for web scraping
- CORS enabled
- API documentation with Swagger UI

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Linux/Mac
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

4. Access the API:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### POST /scrape
Scrape a website and return the content.

**Request Body:**
```json
{
  "url": "https://example.com",
  "selector": "h1"  // Optional CSS selector
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "title": "Example Domain",
    "url": "https://example.com",
    "status_code": 200,
    "elements": ["Example Domain"]
  }
}
```

### GET /health
Health check endpoint.

## Development

The API is ready for further customization and feature additions.
