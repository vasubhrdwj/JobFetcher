from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://vjob:vjob_dev@localhost:5432/vjob"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    CORS_ORIGINS: str = "http://localhost:5173"
    SCRAPE_INTERVAL_HOURS: int = 3
    SCRAPE_CONCURRENCY: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()