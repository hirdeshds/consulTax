"""Minimal stub router for rules diff endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/rules-diff", tags=["rules-diff"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "rules_diff"}
