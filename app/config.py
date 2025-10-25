"""Configuration settings for the backend API"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables"""

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    REQUEST_TIMEOUT: int = 30
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    CACHE_TTL_SECONDS: int = 300
    HTTP_CONNECT_LIMIT: int = 20
    HTTP_CONNECT_LIMIT_PER_HOST: int = 10
    LOG_LEVEL: str = "INFO"

    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        case_sensitive = True


settings = Settings()
