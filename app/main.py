"""Main entrypoint for the consulTax FastAPI application."""

from fastapi import FastAPI
from app.api.qa import router as qa_router
from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="1.0.0"
)

# Register the QA / conversational assistant router
app.include_router(qa_router, prefix="/api")


@app.get("/")
def read_root():
    """Root endpoint to check API health."""
    return {
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "status": "healthy"
    }
