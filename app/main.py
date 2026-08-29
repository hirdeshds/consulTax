"""Main FastAPI application for consulTax backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.rules_diff import router as rules_diff_router
from app.api.session import router as session_router
from app.api.simulate import router as simulate_router
from app.audit.logger import audit_logger

app = FastAPI(
    title="consulTax API",
    description="Intelligent Tax Optimization, Simulation, and Advisory Engine",
    version="1.0.0",
)

# CORS middleware for frontend interactions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(session_router, prefix="/api")
app.include_router(simulate_router, prefix="/api")
app.include_router(rules_diff_router, prefix="/api")


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "app": "consulTax"}


@app.get("/api/audit/logs", tags=["Audit"])
def get_audit_logs(limit: int = 50, event_type: str = None, session_id: str = None):
    """Retrieve recent structured audit logs."""
    return audit_logger.get_recent_logs(limit=limit, event_type=event_type, session_id=session_id)
