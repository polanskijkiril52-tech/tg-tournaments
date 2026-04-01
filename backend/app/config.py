from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Security
    JWT_SECRET: str = "dev-change-me"  # ⚠️ override in production
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 60 * 60 * 24  # 24h

    # Database
    DATABASE_URL: str = "sqlite:///./app.db"  # ⚠️ override with Postgres on Render

    # CORS
    # Comma-separated list of allowed origins. Use "*" only for quick testing.
    ALLOWED_ORIGINS: str = "*"

    # Telegram Mini App security
    # Token of the Telegram bot that owns this Mini App (used to validate initData)
    TELEGRAM_BOT_TOKEN: str | None = None

    # Strict admin (only one person): Telegram user id of the admin
    ADMIN_TELEGRAM_ID: int | None = None

    class Config:
        env_file = ".env"


settings = Settings()
