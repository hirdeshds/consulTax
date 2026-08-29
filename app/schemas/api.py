"""API request and response schemas for consulTax."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.domain import DocumentData, RuleResult, TaxDocument, TaxProfile, TaxRegime

# Hard constraint: disclaimer must appear in every API response payload, not just docs.
DISCLAIMER = (
    "consulTax is an AI-powered advisory tool and is NOT a certified tax authority. "
    "All recommendations are based on the information you provide and the rules configured "
    "in the system. They may not account for all individual circumstances. "
    "Always consult a qualified Chartered Accountant (CA) or registered tax professional "
    "before making any filing decisions. No real financial data is collected or stored."
)


class AnalyzeRequest(BaseModel):
    document: Optional[TaxDocument] = None
    tax_profile: Optional[TaxProfile] = None
    sessionId: Optional[str] = Field(default=None, min_length=1)
    financial_year: Optional[str] = None
    include_recommendations: bool = True


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
    deductions: List[DeductionResult] = Field(default_factory=list)
    schemes: List[SchemeResult] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    tax_profile: Optional[TaxProfile] = None
    recommended_regime: Optional[TaxRegime] = None
    old_regime_liability: Optional[float] = None
    new_regime_liability: Optional[float] = None
    potential_savings: Optional[float] = None
    applied_rules: List[RuleResult] = Field(default_factory=list)
    optimization_tips: List[str] = Field(default_factory=list)
    disclaimer: str = Field(default=DISCLAIMER, description="Regulatory disclaimer — not a certified tax authority")


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the sender: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Text content of the message")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    """API request payload for tax assistant conversational interaction."""

    session_id: Optional[str] = Field(None, description="Unique session identifier for multi-turn conversations")
    message: str = Field(..., min_length=1, description="User's query or prompt to the tax assistant")
    tax_profile: Optional[TaxProfile] = Field(None, description="Taxpayer profile context for personalized responses")
    document_ids: Optional[List[str]] = Field(default_factory=list, description="IDs of relevant documents for grounded QA")
    history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Prior conversation messages")
    preferred_language: str = Field(default="en", description="Preferred response language (e.g., 'en', 'hi')")
    stream: bool = Field(default=False, description="Whether to stream the response chunks")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context or client metadata")


class ChatCitation(BaseModel):
    source_title: str
    source_section: Optional[str] = None
    snippet: Optional[str] = None
    url: Optional[str] = None


class ChatResponse(BaseModel):
    """API response schema for chat interactions."""

    session_id: str
    reply: str
    citations: List[ChatCitation] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)
    rule_results: List[RuleResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = Field(default=DISCLAIMER, description="Regulatory disclaimer — not a certified tax authority")


class OCRUploadResponse(BaseModel):
    document: DocumentData
    status: str = "success"
    message: Optional[str] = None
    disclaimer: str = Field(default=DISCLAIMER, description="Regulatory disclaimer — not a certified tax authority")


class SimulateRequest(BaseModel):
    tax_profile: TaxProfile
    adjustments: Dict[str, Any] = Field(default_factory=dict)
    target_regime: Optional[TaxRegime] = None


class SimulateResponse(BaseModel):
    original_liability: float
    projected_liability: float
    net_savings: float
    rule_breakdown: List[RuleResult] = Field(default_factory=list)
    disclaimer: str = Field(default=DISCLAIMER, description="Regulatory disclaimer — not a certified tax authority")

