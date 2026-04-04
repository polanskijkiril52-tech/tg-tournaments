from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    JWT_SECRET: str = "dev-change-me-please-change-this-secret"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 60 * 60 * 24

    DATABASE_URL: str = "sqlite:///./app.db"

    ALLOWED_ORIGINS: str = "*"

    TELEGRAM_BOT_TOKEN: str | None = None
    ADMIN_TELEGRAM_ID: int | None = None

    DEV_AUTH_ENABLED: bool = False


settings = Settings()
