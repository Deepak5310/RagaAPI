from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from bs4 import BeautifulSoup
import requests
from typing import Optional, Dict, Any

app = FastAPI(
    title="Web Scraping API",
    description="A FastAPI-based web scraping service using BeautifulSoup",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request models
class ScrapeRequest(BaseModel):
    url: HttpUrl
    selector: Optional[str] = None

# Response models
class ScrapeResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@app.get("/")
async def root():
    return {
        "message": "Web Scraping API",
        "status": "running",
        "docs": "/docs"
    }

@app.post("/scrape", response_model=ScrapeResponse)
async def scrape_website(request: ScrapeRequest):
    """
    Scrape a website and return the content
    """
    try:
        # Send GET request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(str(request.url), headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Basic scraping logic
        data = {
            "title": soup.title.string if soup.title else None,
            "url": str(request.url),
            "status_code": response.status_code
        }
        
        # If selector is provided, get specific elements
        if request.selector:
            elements = soup.select(request.selector)
            data["elements"] = [elem.get_text(strip=True) for elem in elements]
        
        return ScrapeResponse(success=True, data=data)
    
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Request failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
