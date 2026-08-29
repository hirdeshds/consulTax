"""API request and response schemas for consulTax."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

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


class FrontendProfileInput(BaseModel):
    name: Optional[str] = "Taxpayer"
    financial_year: Optional[str] = "2024-25"
    age: Optional[int] = 30
    is_resident: Optional[bool] = True
    residential_location: Optional[str] = "metro"
    dependent_parents: Optional[bool] = False
    parent_is_senior: Optional[bool] = False
    children_count: Optional[int] = 0
    employment_income: Optional[float] = 0.0
    business_revenue: Optional[float] = 0.0
    business_expenses: Optional[float] = 0.0
    other_income: Optional[float] = 0.0
    rental_income: Optional[float] = 0.0
    dividend_income: Optional[float] = 0.0
    capital_gains: Optional[float] = 0.0
    basic_salary: Optional[float] = 0.0
    hra_received: Optional[float] = 0.0
    annual_rent_paid: Optional[float] = 0.0
    provident_fund: Optional[float] = 0.0
    elss_investment: Optional[float] = 0.0
    life_insurance_premium: Optional[float] = 0.0
    children_tuition_fees: Optional[float] = 0.0
    health_insurance_self_family: Optional[float] = 0.0
    health_insurance_parents: Optional[float] = 0.0
    parent_medical_spend: Optional[float] = 0.0
    home_loan_principal: Optional[float] = 0.0
    home_loan_interest: Optional[float] = 0.0
    education_loan_interest: Optional[float] = 0.0
    eligible_medical_treatment: Optional[float] = 0.0
    charity_donations: Optional[float] = 0.0
    tax_paid: Optional[float] = 0.0
    regime: Optional[str] = "new"


class AnalyzeRequest(BaseModel):
    profile: Optional[Union[FrontendProfileInput, Dict[str, Any]]] = None
    document: Optional[TaxDocument] = None
    tax_profile: Optional[TaxProfile] = None
    sessionId: Optional[str] = None
    session_id: Optional[str] = None
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


class FrontendTaxResult(BaseModel):
    gross_income: float = 0.0
    taxable_income: float = 0.0
    total_tax: float = 0.0
    tax_paid: float = 0.0
    payable: float = 0.0
    refund: float = 0.0
    regime: str = "new"
    rule_version: str = "2024-25"
    standard_deduction: float = 0.0
    deductions_claimed: float = 0.0
    deduction_breakdown: Dict[str, float] = Field(default_factory=dict)
    excluded_income: Dict[str, float] = Field(default_factory=dict)
    trace: List[str] = Field(default_factory=list)


class FrontendRecommendation(BaseModel):
    section: str
    title: str
    potential_deduction: Optional[float] = None
    estimated_tax_saving: Optional[float] = None
    reason: str
    conditions: str


class FrontendComparison(BaseModel):
    new: FrontendTaxResult
    old: FrontendTaxResult
    recommended_regime: str = "new"
    estimated_savings: float = 0.0
    reason: str = ""


class AnalyzeResponse(BaseModel):
    session_id: Optional[str] = None
    explanation: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    result: Optional[FrontendTaxResult] = None
    comparison: Optional[FrontendComparison] = None
    recommendations: List[FrontendRecommendation] = Field(default_factory=list)
    deductions: List[DeductionResult] = Field(default_factory=list)
    schemes: List[SchemeResult] = Field(default_factory=list)
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
    sessionId: Optional[str] = Field(None, description="CamelCase alias for session identifier")
    message: Optional[str] = Field(default=None, min_length=1, description="User's query or prompt to the tax assistant")
    question: Optional[str] = Field(default=None, min_length=1, description="Frontend alias for user question")
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
    answer: Optional[str] = None
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


class Form16Explainer(BaseModel):
    term: str
    meaning: str


class Form16SummaryResponse(BaseModel):
    summary: str
    summary_source: str
    key_figures: Dict[str, str] = Field(default_factory=dict)
    explainers: List[Form16Explainer] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    retrieved_chunks: int = 0
    disclaimer: str = Field(default=DISCLAIMER)


class SimulateRequest(BaseModel):
    tax_profile: Optional[TaxProfile] = None
    profile: Optional[Union[FrontendProfileInput, Dict[str, Any]]] = None
    adjustments: Dict[str, Any] = Field(default_factory=dict)
    target_regime: Optional[TaxRegime] = None


class SimulateResponse(BaseModel):
    original_liability: float
    projected_liability: float
    net_savings: float
    rule_breakdown: List[RuleResult] = Field(default_factory=list)
    disclaimer: str = Field(default=DISCLAIMER, description="Regulatory disclaimer — not a certified tax authority")
