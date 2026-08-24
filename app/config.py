"""
Application configuration using pydantic-settings.
Loads environment variables from .env file.
"""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "sqlite:///./recon.db"

    # AI / LLM
    GEMINI_API_KEY: Optional[str] = None

    # Reconciliation thresholds
    AI_CONFIDENCE_AUTO_MATCH: float = 0.9
    AI_CONFIDENCE_REVIEW: float = 0.7
    AMOUNT_TOLERANCE_PERCENT: float = 5.0
    DATE_TOLERANCE_DAYS: int = 2

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
