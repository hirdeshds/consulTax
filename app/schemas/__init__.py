"""Schemas package exporting domain and API models."""

from app.schemas.api import (
    AnalyzeRequest,
    AnalyzeResponse,
    ChatCitation,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    OCRUploadResponse,
    SimulateRequest,
    SimulateResponse,
)
from app.schemas.domain import (
    DeductionDetails,
    DocumentData,
    DocumentType,
    IncomeDetails,
    RuleCategory,
    RuleResult,
    TaxProfile,
    TaxRegime,
)

__all__ = [
    "TaxProfile",
    "DocumentData",
    "RuleResult",
    "TaxRegime",
    "DocumentType",
    "RuleCategory",
    "IncomeDetails",
    "DeductionDetails",
    "ChatRequest",
    "ChatResponse",
    "ChatMessage",
    "ChatCitation",
    "AnalyzeRequest",
    "AnalyzeResponse",
    "OCRUploadResponse",
    "SimulateRequest",
    "SimulateResponse",
]
