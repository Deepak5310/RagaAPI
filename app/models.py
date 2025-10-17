"""
Data models for Actress Gallery API
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ScraperSource(str, Enum):
    """Available scraper sources"""
    RAGALAHARI = "ragalahari"
    # Add more sources as needed
    # IMDB = "imdb"
    # TMDB = "tmdb"


class Actress(BaseModel):
    """Basic actress information for list view"""
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Actress name")
    thumbnail: str = Field(..., description="Thumbnail image URL")
    age: Optional[int] = Field(None, description="Age")
    nationality: Optional[str] = Field(None, description="Nationality")
    profession: Optional[str] = Field(None, description="Profession")
    source: ScraperSource = Field(..., description="Data source")

    class Config:
        """Pydantic model configuration with example schema"""
        json_schema_extra = {
            "example": {
                "id": "actress_001",
                "name": "Jane Doe",
                "thumbnail": "https://example.com/jane-thumbnail.jpg",
                "age": 28,
                "nationality": "USA",
                "profession": "Actress",
                "source": "sample"
            }
        }


class Album(BaseModel):
    """Photo album/gallery information"""
    name: str = Field(..., description="Album/Gallery name")
    url: str = Field(..., description="Album URL")
    thumbnail: Optional[str] = Field(None, description="Album thumbnail image")


class ActressDetail(BaseModel):
    """Detailed actress information"""
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Actress name")
    images: List[str] = Field(default_factory=list, description="List of image URLs")
    albums: List[Album] = Field(default_factory=list, description="Photo galleries/albums")
    age: Optional[int] = Field(None, description="Age")
    birth_date: Optional[str] = Field(None, description="Date of birth")
    nationality: Optional[str] = Field(None, description="Nationality")
    profession: Optional[str] = Field(None, description="Profession")
    height: Optional[str] = Field(None, description="Height")
    bio: Optional[str] = Field(None, description="Biography")
    known_for: List[str] = Field(default_factory=list, description="Notable works")
    social_media: dict = Field(default_factory=dict, description="Social media links")
    source: ScraperSource = Field(..., description="Data source")
    last_updated: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )

    class Config:
        """Pydantic model configuration with example schema"""
        json_schema_extra = {
            "example": {
                "id": "actress_001",
                "name": "Jane Doe",
                "images": [
                    "https://example.com/jane-1.jpg",
                    "https://example.com/jane-2.jpg"
                ],
                "age": 28,
                "birth_date": "1997-05-15",
                "nationality": "USA",
                "profession": "Actress",
                "height": "5'7\"",
                "bio": "Talented actress known for diverse roles",
                "known_for": ["Movie A", "Movie B", "Series C"],
                "social_media": {
                    "instagram": "https://instagram.com/janedoe",
                    "twitter": "https://twitter.com/janedoe"
                },
                "source": "sample",
                "last_updated": "2025-10-16T00:00:00"
            }
        }


class SearchResult(BaseModel):
    """Search result model"""
    query: str
    results: List[Actress]
    total: int
