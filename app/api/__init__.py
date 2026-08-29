"""API routers package for consulTax."""

from app.api.rules_diff import router as rules_diff_router
from app.api.session import router as session_router
from app.api.simulate import router as simulate_router

__all__ = [
    "session_router",
    "simulate_router",
    "rules_diff_router",
]
