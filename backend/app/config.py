"""Application configuration management using Pydantic Settings."""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server Settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    APP_NAME: str = "ShopAI Backend"
    ENVIRONMENT: str = "development"

    # PostgreSQL Database Settings (Primary & Default)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "shopai"

    # Direct database URL override (optional)
    DATABASE_URL: Optional[str] = None

    # Testing Mode flag (Only when explicitly set to True may isolated tests use SQLite)
    TESTING_MODE: bool = False

    # Local Ollama Configuration
    OLLAMA_API_KEY: str = ""
    OLLAMA_API_URL: str = "http://localhost:11434/api/chat"
    OLLAMA_MODEL: str = "llama3.2:latest"
    LAYA_DECIDE_URL: str = "http://localhost:5055/decide"

    # Dataset file path
    DATASET_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "poorvika_products.jsonl"
    )

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        """Returns the PostgreSQL connection URL formatted for SQLAlchemy with psycopg3."""
        if self.TESTING_MODE:
            return "sqlite:///:memory:"
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg://", 1)
            return url
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
