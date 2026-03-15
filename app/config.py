from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./inbound_bot.db"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-nano"

    # Encryption (Fernet key)
    ENCRYPTION_KEY: str = ""

    # Admin JWT
    ADMIN_JWT_SECRET: str = ""
    ADMIN_JWT_ALGORITHM: str = "HS256"
    ADMIN_JWT_EXPIRE_MINUTES: int = 480

    # Google OAuth / Calendar
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""

    # Resend (Email)
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "notifications@inbound-bot.com"

    # WhatsApp
    WHATSAPP_VERIFY_TOKEN: str = ""

    # Vapi (Voice AI)
    VAPI_API_KEY: str = ""

    # Application
    BASE_URL: str = "http://localhost:8000"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
