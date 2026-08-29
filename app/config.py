import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Tax Assistant")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    Cohare_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

    SESSION_TTL_SECONDS: int = int(
        os.getenv("SESSION_TTL_SECONDS", "1800")
    )

    REDIS_URL: str | None = os.getenv("REDIS_URL")

    SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY: str | None = os.getenv("SUPABASE_ANON_KEY")

    SENTRY_DSN: str | None = os.getenv("SENTRY_DSN")


settings = Settings()