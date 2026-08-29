"""Minimal stub router for session endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/session", tags=["session"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "session"}
