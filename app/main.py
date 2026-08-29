"""Main entrypoint for the consulTax FastAPI application."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

# Import API Routers
from app.api.qa import router as qa_router
from app.api.analyze import router as analyze_router
from app.api.ocr import router as ocr_router
from app.api.simulate import router as simulate_router
from app.api.session import router as session_router
from app.api.export import router as export_router
from app.api.rules_diff import router as rules_diff_router

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="1.0.0"
)

# 1. Mount CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. Register Global Unhandled Exception Middleware / Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Formats and handles unexpected internal runtime errors gracefully."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred during processing.",
            "error": str(exc) if settings.DEBUG else "Internal Server Error"
        }
    )


# 3. Register All Routers under the /api Prefix
app.include_router(qa_router, prefix="/api")
app.include_router(analyze_router, prefix="/api")
app.include_router(ocr_router, prefix="/api")
app.include_router(simulate_router, prefix="/api")
app.include_router(session_router, prefix="/api")
app.include_router(export_router, prefix="/api")
app.include_router(rules_diff_router, prefix="/api")


@app.get("/")
def read_root():
    """Root endpoint to check API health."""
    return {
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "status": "healthy"
    }
