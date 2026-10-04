from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = "postgresql+psycopg://user:pass@localhost:5432/securerag"
    JWT_SECRET: str = "change-me"
    JWT_EXPIRE_MINUTES: int = 60
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"
    RERANK_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RATE_LIMIT_PER_MIN: int = 20
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 120
    TOP_K_CANDIDATES: int = 20
    TOP_K_FINAL: int = 5

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
