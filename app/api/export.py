"""Minimal stub router for export endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "export"}
