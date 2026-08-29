"""Minimal stub router for tax simulator endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/simulate", tags=["simulate"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "simulate"}
