"""Data models for Actress Gallery API"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ScraperSource(str, Enum):
    RAGALAHARI = "ragalahari"


class Actress(BaseModel):
    id: str
    name: str
    thumbnail: str
    age: Optional[int] = None
    nationality: Optional[str] = None
    profession: Optional[str] = None
    source: ScraperSource


class Album(BaseModel):
    name: str
    url: str
    thumbnail: Optional[str] = None


class ActressDetail(BaseModel):
    id: str
    name: str
    images: List[str] = Field(default_factory=list)
    albums: List[Album] = Field(default_factory=list)
    age: Optional[int] = None
    birth_date: Optional[str] = None
    nationality: Optional[str] = None
    profession: Optional[str] = None
    height: Optional[str] = None
    bio: Optional[str] = None
    known_for: List[str] = Field(default_factory=list)
    social_media: dict = Field(default_factory=dict)
    source: ScraperSource
    last_updated: datetime = Field(default_factory=datetime.now)
