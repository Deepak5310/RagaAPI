"""FastAPI backend for Actress Gallery application"""

from typing import List
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.models import Actress, ActressDetail
from app.scraper import ActressScraper
from app.config import settings

app = FastAPI(title="Actress Gallery API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

scraper = ActressScraper()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Actress Gallery API", "version": "2.0.0", "status": "active"}


@app.get("/api/actress/{actress_id}", response_model=ActressDetail)
async def get_actress_detail(actress_id: str):
    """Get complete actress profile with images and albums"""
    if not actress_id.startswith('rh_'):
        raise HTTPException(
            status_code=400,
            detail="Only Ragalahari actresses supported (rh_ prefix)"
        )

    actress_detail = await scraper.get_ragalahari_actress_detail(actress_id)
    if not actress_detail:
        raise HTTPException(status_code=404, detail="Actress not found")

    return actress_detail


@app.get("/api/search", response_model=List[Actress])
async def search_actresses(
    query: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100)
):
    """Search actresses by name"""
    query_lower = query.lower()
    results = []

    first_char = query_lower[0]
    if first_char.isalpha():
        letter_actresses = await scraper.scrape_ragalahari_by_letter(first_char)
        results = [a for a in letter_actresses if query_lower in a.name.lower()]

    if len(results) < limit:
        latest_actresses = await scraper.scrape_ragalahari_latest()
        result_ids = {r.id for r in results}
        for actress in latest_actresses:
            if query_lower in actress.name.lower() and actress.id not in result_ids:
                results.append(actress)
                if len(results) >= limit:
                    break

    return results[:limit]


@app.get("/api/ragalahari/latest", response_model=List[Actress])
async def get_ragalahari_latest():
    """Get latest 20 galleries from Ragalahari"""
    return await scraper.scrape_ragalahari_latest()


@app.get("/api/ragalahari/letter/{letter}", response_model=List[Actress])
async def get_ragalahari_by_letter(letter: str):
    """Get actresses by first letter (A-Z browsing)"""
    if len(letter) != 1 or not letter.isalpha():
        raise HTTPException(status_code=400, detail="Letter must be a single alphabetic character")
    if letter.lower() == 'q':
        raise HTTPException(status_code=400, detail="Letter Q is not available on Ragalahari")

    return await scraper.scrape_ragalahari_by_letter(letter)


@app.get("/api/actress/{actress_id}/albums", response_model=List[dict])
async def get_actress_albums(actress_id: str):
    """Get all albums for an actress"""
    if not actress_id.startswith('rh_'):
        raise HTTPException(
            status_code=400,
            detail="Albums only available for Ragalahari actresses (rh_ prefix)"
        )

    return await scraper.get_ragalahari_actress_albums(actress_id)


@app.get("/api/album/photos", response_model=List[str])
async def get_album_photos(album_url: str = Query(...)):
    """Get all high-quality photos from an album"""
    if 'ragalahari.com' not in album_url:
        raise HTTPException(status_code=400, detail="Only Ragalahari album URLs are supported")

    return await scraper.get_ragalahari_album_photos(album_url)


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
