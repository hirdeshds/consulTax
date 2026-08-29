"""Domain schemas and core data models for consulTax."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Income(BaseModel):
    salary: float = Field(default=0, ge=0)
    business_income: float = Field(default=0, ge=0)
    rental_income: float = Field(default=0, ge=0)
    other_income: float = Field(default=0, ge=0)


class Expenses(BaseModel):
    medical: float = Field(default=0, ge=0)
    education: float = Field(default=0, ge=0)
    insurance: float = Field(default=0, ge=0)
    other: float = Field(default=0, ge=0)


class Investments(BaseModel):
    section_80c: float = Field(default=0, ge=0)
    health_insurance: float = Field(default=0, ge=0)
    home_loan_interest: float = Field(default=0, ge=0)
    other: float = Field(default=0, ge=0)


class TaxDocument(BaseModel):
    income: Income = Field(default_factory=Income)
    expenses: Expenses = Field(default_factory=Expenses)
    investments: Investments = Field(default_factory=Investments)


class TaxRegime(str, Enum):
    OLD = "old"
    NEW = "new"


class DocumentType(str, Enum):
    FORM_16 = "form_16"
    SALARY_SLIP = "salary_slip"
    FORM_26AS = "form_26as"
    AIS = "ais"
    INVESTMENT_PROOF = "investment_proof"
    RENT_RECEIPT = "rent_receipt"
    HOME_LOAN_CERTIFICATE = "home_loan_certificate"
    INSURANCE_PREMIUM = "insurance_premium"
    DONATION_RECEIPT = "donation_receipt"
    OTHER = "other"


class RuleCategory(str, Enum):
    DEDUCTION = "deduction"
    EXEMPTION = "exemption"
    REBATE = "rebate"
    SURCHARGE = "surcharge"
    CESS = "cess"
    TAX_SLAB = "tax_slab"
    COMPLIANCE = "compliance"


class IncomeDetails(BaseModel):
    salary: float = 0.0
    house_property: float = 0.0
    capital_gains_short_term: float = 0.0
    capital_gains_long_term: float = 0.0
    business_profession: float = 0.0
    other_sources: float = 0.0
    exempt_income: float = 0.0


class DeductionDetails(BaseModel):
    section_80c: float = 0.0
    section_80ccc: float = 0.0
    section_80ccd_1: float = 0.0
    section_80ccd_1b: float = 0.0
    section_80ccd_2: float = 0.0
    section_80d: float = 0.0
    section_80dd: float = 0.0
    section_80ddb: float = 0.0
    section_80e: float = 0.0
    section_80ee: float = 0.0
    section_80eea: float = 0.0
    section_80g: float = 0.0
    section_80gg: float = 0.0
    section_80tta: float = 0.0
    section_80ttb: float = 0.0
    section_80u: float = 0.0
    section_24b: float = 0.0
    standard_deduction: float = 0.0
    hra_exemption: float = 0.0
    lta_exemption: float = 0.0
    other_deductions: Dict[str, float] = Field(default_factory=dict)


class TaxProfile(BaseModel):
    """Core domain model representing a taxpayer's complete profile and financial details."""

    profile_id: Optional[str] = None
    user_id: Optional[str] = None
    financial_year: str = "2024-2025"
    assessment_year: str = "2025-2026"
    regime_preference: TaxRegime = TaxRegime.NEW
    age: Optional[int] = None
    is_senior_citizen: bool = False
    is_super_senior_citizen: bool = False
    residential_status: str = "resident"
    income: IncomeDetails = Field(default_factory=IncomeDetails)
    deductions: DeductionDetails = Field(default_factory=DeductionDetails)
    gross_total_income: float = 0.0
    total_deductions: float = 0.0
    net_taxable_income: float = 0.0
    total_tax_liability: float = 0.0
    tax_paid_tds: float = 0.0
    tax_paid_advance: float = 0.0
    tax_paid_self_assessment: float = 0.0
    refund_or_due_amount: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentData(BaseModel):
    """Domain model for parsed document data extracted via OCR or user upload."""

    document_id: str
    document_type: DocumentType = DocumentType.OTHER
    filename: Optional[str] = None
    content_type: Optional[str] = None
    raw_text: Optional[str] = None
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    is_validated: bool = False
    validation_errors: List[str] = Field(default_factory=list)
    parsed_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RuleResult(BaseModel):
    """Domain model representing the evaluation outcome of an individual tax rule/scheme."""

    rule_id: str
    rule_name: str
    category: RuleCategory = RuleCategory.DEDUCTION
    is_applicable: bool = True
    is_eligible: bool = True
    max_limit: Optional[float] = None
    claimed_amount: float = 0.0
    eligible_amount: float = 0.0
    potential_savings: float = 0.0
    tax_regime: Optional[TaxRegime] = None
    legal_section: Optional[str] = None
    description: Optional[str] = None
    recommendations: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
 