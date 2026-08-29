"""Minimal stub router for OCR endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "ocr"}
