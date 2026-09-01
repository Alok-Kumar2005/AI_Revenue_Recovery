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

    POSTGRESS_URL: str = "postgresql://postgres:postgres@localhost:5432/revenue_recovery"

    RZP_KEY: str = "rzp_test_mock"
    RZP_SECRET: str = "rzp_test_secret_mock"
    RZP_WEBHOOK_SECRET: str = "rzp_webhook_secret_mock"

    GEMINI_API_KEY: str = ""

    # Optional Redis URL for Celery broker.
    # Leave empty to run Celery in task_always_eager mode (no Redis required).
    REDIS_URL: str = ""

    # Base URL for public API endpoints and generated document links
    BASE_URL: str = "http://localhost:8000"

    # Allowed CORS origins
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # ── Messaging dispatchers ─────────────────────────────────────────────────
    # Gmail SMTP (Email)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = ""

    # CallMeBot (WhatsApp)
    CALLMEBOT_PHONE: str = ""
    CALLMEBOT_API_KEY: str = ""

    # Telegram Bot (Mobile Alerts / SMS)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Legacy SendGrid / Twilio configs for backwards compatibility
    SENDGRID_API_KEY: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""

    # When True all dispatchers log mock output instead of making real API calls.
    MOCK_DISPATCH: bool = False

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
