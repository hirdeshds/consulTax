import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Tax Assistant")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    COHERE_API_KEY: str | None = os.getenv("COHERE_API_KEY")
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")

    COHERE_MODEL: str = os.getenv("COHERE_MODEL", "command-r-plus")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    SESSION_TTL_SECONDS: int = int(
        os.getenv("SESSION_TTL_SECONDS", "1800")
    )

    SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY: str | None = os.getenv("SUPABASE_ANON_KEY")

    SENTRY_DSN: str | None = os.getenv("SENTRY_DSN")


settings = Settings()