from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str = Field(default="")
    TELEGRAM_CHANNEL_ID: str = Field(default="")
    GROQ_API_KEY: str = Field(default="")
    
    # Defaults to local SQLite, but will be overridden by Railway's DATABASE_URL (PostgreSQL)
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./news.db")
    
    POLL_INTERVAL_HOURS: float = Field(default=3.0)
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile")

    # Time restrictions for publishing news
    PUBLISH_START_HOUR: int = Field(default=8)
    PUBLISH_END_HOUR: int = Field(default=22)
    TIMEZONE: str = Field(default="Europe/Kyiv")
    IGNORE_TIME_RESTRICTIONS: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
