from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.domain import TaxDocument


class AnalyzeRequest(BaseModel):
    document: TaxDocument
    sessionId: str = Field(min_length=1)


class DeductionResult(BaseModel):
    title: str
    amount: float = Field(ge=0)
    ruleId: str
    reason: str = Field(min_length=1)
    confidence: Literal["confirmed", "flagged"]


class SchemeResult(BaseModel):
    title: str
    ruleId: str
    reason: str = Field(min_length=1)
    confidence: Literal["confirmed", "flagged"]


class AnalyzeResponse(BaseModel):
    deductions: list[DeductionResult]
    schemes: list[SchemeResult]
    warnings: list[str] = []