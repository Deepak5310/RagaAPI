"""
Configuration settings for the backend API
"""

from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # API Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # Scraper Settings
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    # Cache Settings
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 3600  # 1 hour

    # CORS Settings
    ALLOWED_ORIGINS: List[str] = ["*"]

    class Config:
        """Pydantic settings configuration"""
        env_file = ".env"
        case_sensitive = True


settings = Settings()
