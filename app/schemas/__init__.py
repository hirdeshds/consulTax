<<<<<<< HEAD
from app.schemas.api import (
    AnalyzeRequest,
    AnalyzeResponse,
    DeductionResult,
    SchemeResult,
)

from app.schemas.domain import (
    Expenses,
    Income,
    Investments,
    TaxDocument,
)

__all__ = [
    "AnalyzeRequest",
    "AnalyzeResponse",
    "DeductionResult",
    "SchemeResult",
    "Expenses",
    "Income",
    "Investments",
    "TaxDocument",
]
=======
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
>>>>>>> 792571d431b0516ede938b56d17e846fa889d0c1
