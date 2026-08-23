import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.
    All database and third-party credentials are validated at startup.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    POSTGRESS_URL: str

    RZP_KEY: str
    RZP_SECRET: str
    RZP_WEBHOOK_SECRET: str

    GEMINI_API_KEY: str = ""

    # Optional Redis URL for Celery broker.
    # Leave empty to run Celery in task_always_eager mode (no Redis required).
    REDIS_URL: str = ""

    @property
    def DATABASE_URL(self) -> str:
        """
        Returns a psycopg2-compatible URL (postgresql+psycopg2://).
        Neon requires sslmode=require; the .env value may use plain
        'postgresql://' — we normalise that here.
        """
        url = self.POSTGRESS_URL
        # Ensure driver prefix is psycopg2-compatible for sync SQLAlchemy
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        return url

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """
        Returns an asyncpg-compatible URL (postgresql+asyncpg://).
        Used by the async SQLAlchemy engine.

        asyncpg does NOT accept 'sslmode' or 'channel_binding' in the query
        string — it uses a separate ssl= kwarg in connect_args instead.
        We strip both parameters here to avoid a TypeError at connection time.
        """
        url = self.POSTGRESS_URL
        for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
            if url.startswith(prefix):
                url = "postgresql+asyncpg://" + url[len(prefix):]
                break

        # Strip params that asyncpg does not accept
        for param in ("channel_binding=require", "sslmode=require", "sslmode=prefer"):
            url = url.replace(f"&{param}", "").replace(f"?{param}", "")

        # If stripping left a trailing '?', remove it
        url = url.rstrip("?").rstrip("&")
        return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# Convenience alias used across the codebase
settings = get_settings()
