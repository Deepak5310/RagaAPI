"""
Actress Gallery Backend API
FastAPI application for web scraping actress information
"""

from typing import List
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.models import Actress, ActressDetail
from app.scraper import ActressScraper
from app.config import settings

app = FastAPI(
    title="Actress Gallery API",
    description="Backend API for fetching actress information from multiple sources",
    version="1.0.0"
)

# CORS middleware for Flutter desktop app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Specify Flutter app's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scraper = ActressScraper()


@app.get("/")
async def root():
    """Root endpoint - API health check"""
    return {
        "message": "Actress Gallery API",
        "version": "1.0.0",
        "status": "active"
    }


@app.get("/api/actress/{actress_id}", response_model=ActressDetail)
async def get_actress_detail(actress_id: str):
    """
    Get detailed information about a specific actress

    Args:
        actress_id: Unique identifier for the actress (e.g., rh_174422 for Ragalahari)

    Returns:
        Detailed actress information including images and albums

    Raises:
        HTTPException: 400 if invalid ID format, 404 if not found, 500 on error
    """
    try:
        # Only support Ragalahari actresses
        if not actress_id.startswith('rh_'):
            raise HTTPException(
                status_code=400,
                detail="Only Ragalahari actresses supported (rh_ prefix)"
            )

        actress_detail = await scraper.get_ragalahari_actress_detail(actress_id)

        if not actress_detail:
            raise HTTPException(status_code=404, detail="Actress not found")

        return actress_detail
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching actress details: {str(e)}"
        ) from e


@app.get("/api/search", response_model=List[Actress])
async def search_actresses(
    query: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results")
):
    """
    Search for actresses by name across all galleries

    Searches in A-Z galleries starting with the first letter of query,
    then expands to latest galleries if needed.

    Args:
        query: Search query string
        limit: Maximum number of results

    Returns:
        List of matching actresses
    """
    try:
        query_lower = query.lower()
        results = []

        # First, search by letter (more efficient if query starts with a letter)
        first_char = query_lower[0]
        if first_char.isalpha():
            letter_actresses = await scraper.scrape_ragalahari_by_letter(first_char)
            results = [
                actress for actress in letter_actresses
                if query_lower in actress.name.lower()
            ]

        # If not enough results, also search latest galleries
        if len(results) < limit:
            latest_actresses = await scraper.scrape_ragalahari_latest()
            result_ids = {r.id for r in results}
            for actress in latest_actresses:
                if query_lower in actress.name.lower() and actress.id not in result_ids:
                    results.append(actress)
                    if len(results) >= limit:
                        break

        return results[:limit]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error searching actresses: {str(e)}"
        ) from e


@app.get("/api/ragalahari/latest", response_model=List[Actress])
async def get_ragalahari_latest():
    """
    Get latest actress galleries from Ragalahari.com

    This endpoint scrapes the main starzone page which shows the latest photo galleries.
    Perfect for home page/feed showing recent updates.

    Returns:
        List of actresses with their latest galleries
    """
    try:
        actresses = await scraper.scrape_ragalahari_latest()
        return actresses
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error scraping latest galleries: {str(e)}"
        ) from e


@app.get("/api/ragalahari/letter/{letter}", response_model=List[Actress])
async def get_ragalahari_by_letter(letter: str):
    """
    Get actresses from Ragalahari.com by letter (Browse A-Z)

    Uses the starzonesearch.aspx page (accessible via "View More Galleries" link)
    to browse all actresses by letter.

    Args:
        letter: Single letter (A-Z, excluding Q)

    Returns:
        List of actresses whose names start with the given letter
    """
    try:
        # Validate letter
        if len(letter) != 1 or not letter.isalpha():
            raise HTTPException(
                status_code=400,
                detail="Letter must be a single alphabetic character"
            )

        if letter.lower() == 'q':
            raise HTTPException(
                status_code=400,
                detail="Letter Q is not available on Ragalahari"
            )

        actresses = await scraper.scrape_ragalahari_by_letter(letter)
        return actresses
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error scraping Ragalahari: {str(e)}"
        ) from e


@app.get("/api/actress/{actress_id}/albums", response_model=List[dict])
async def get_actress_albums(actress_id: str):
    """
    Get list of photo albums/galleries for a specific actress

    NOTE: This endpoint is deprecated. Use /api/actress/{actress_id} instead
    which includes albums in the response.

    Args:
        actress_id: Actress ID (e.g., rh_1375)

    Returns:
        List of albums with name, url, and thumbnail
    """
    try:
        if not actress_id.startswith('rh_'):
            raise HTTPException(
                status_code=400,
                detail="Albums only available for Ragalahari actresses (rh_ prefix)"
            )

        albums = await scraper.get_ragalahari_actress_albums(actress_id)
        return albums
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching albums: {str(e)}"
        ) from e


@app.get("/api/album/photos", response_model=List[str])
async def get_album_photos(
    album_url: str = Query(..., description="Full URL to the album page")
):
    """
    Get all high-quality photos from a specific album/gallery

    Args:
        album_url: Full URL to the album page (e.g.,
        https://www.ragalahari.com/actress/12345/album-name.aspx)

    Returns:
        List of high-quality image URLs
    """
    try:
        if 'ragalahari.com' not in album_url:
            raise HTTPException(
                status_code=400,
                detail="Only Ragalahari album URLs are supported"
            )

        photos = await scraper.get_ragalahari_album_photos(album_url)
        return photos
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching album photos: {str(e)}"
        ) from e


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
