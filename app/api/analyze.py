"""Router for tax profile and document analysis computations."""

from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.dual_check.validator import validate_ocr_vs_computed
from app.explanation.generator import generate_explanation
from app.rules_engine.evaluator import evaluate_tax_profile
from app.schemas.api import (
    AnalyzeRequest,
    AnalyzeResponse,
    DeductionResult,
    SchemeResult,
)
from app.schemas.domain import (
    DocumentData,
    RuleCategory,
    RuleResult,
    TaxDocument,
    TaxProfile,
    TaxRegime,
)
from app.services.unified_tax_service import (
    build_recommendations,
    calculate_single_regime,
    evaluate_8_schemes,
    generate_llm_explanation_sync,
    profile_dict_to_tax_profile,
)
from app.session import get_session_store, SessionStore

router = APIRouter(prefix="/analyze", tags=["analyze"])


def build_reason(rule: RuleResult) -> str:
    """Build a plain-language 'why' sentence for a rule result."""
    sect = f"{rule.legal_section}" if rule.legal_section else rule.rule_name
    claimed = rule.claimed_amount
    eligible = rule.eligible_amount
    limit = rule.max_limit
    savings = rule.potential_savings

    if limit and limit > 0 and claimed > 0:
        gap = max(0.0, limit - claimed)
        if gap > 0:
            extra_saving = round(gap * 0.30, 2)
            return (
                f"{sect} allows up to ₹{limit:,.0f}/year. "
                f"You claimed ₹{claimed:,.0f} — ₹{gap:,.0f} still unused. "
                f"Investing that gap could save an additional ₹{extra_saving:,.0f} in taxes."
            )
        else:
            return (
                f"{sect}: You have fully utilised the ₹{limit:,.0f} limit. "
                f"Total deduction applied: ₹{eligible:,.0f}."
            )

    if limit and limit > 0 and claimed == 0:
        extra_saving = round(limit * 0.30, 2)
        return (
            f"{sect} allows up to ₹{limit:,.0f}/year — you have not claimed this yet. "
            f"Claiming the full amount could save you up to ₹{extra_saving:,.0f} in taxes."
        )

    if claimed > 0:
        return (
            f"{sect}: ₹{eligible:,.0f} applied. "
            + (f"Potential tax saving: ₹{savings:,.0f}." if savings > 0 else "No upper limit applies.")
        )

    description = rule.description or f"Eligible deduction under {sect}"
    return description


def map_document_to_profile(doc: TaxDocument, profile: TaxProfile) -> None:
    """Maps fields from standard TaxDocument input into a TaxProfile."""
    profile.income.salary = doc.income.salary
    profile.income.business_profession = doc.income.business_income
    profile.income.house_property = doc.income.rental_income
    profile.income.other_sources = doc.income.other_income

    profile.deductions.section_80c = doc.investments.section_80c
    profile.deductions.section_80d = doc.investments.health_insurance
    profile.deductions.section_24b = doc.investments.home_loan_interest
    profile.deductions.hra_exemption = doc.investments.other


def map_session_documents_to_profile(documents: dict, profile: TaxProfile) -> None:
    """Maps fields from session DocumentData extracted_fields into a TaxProfile."""
    for doc in documents.values():
        ext = doc.extracted_fields
        if not ext:
            continue
        
        if "salary" in ext and ext["salary"] is not None:
            profile.income.salary = float(ext["salary"])
        if "business_income" in ext and ext["business_income"] is not None:
            profile.income.business_profession = float(ext["business_income"])
        if "rental_income" in ext and ext["rental_income"] is not None:
            profile.income.house_property = float(ext["rental_income"])
        if "other_income" in ext and ext["other_income"] is not None:
            profile.income.other_sources = float(ext["other_income"])
        elif "other_sources" in ext and ext["other_sources"] is not None:
            profile.income.other_sources = float(ext["other_sources"])

        if "section_80c" in ext and ext["section_80c"] is not None:
            profile.deductions.section_80c = float(ext["section_80c"])
        if "section_80d" in ext and ext["section_80d"] is not None:
            profile.deductions.section_80d = float(ext["section_80d"])
        if "section_24b" in ext and ext["section_24b"] is not None:
            profile.deductions.section_24b = float(ext["section_24b"])
        if "standard_deduction" in ext and ext["standard_deduction"] is not None:
            profile.deductions.standard_deduction = float(ext["standard_deduction"])
        if "hra_exemption" in ext and ext["hra_exemption"] is not None:
            profile.deductions.hra_exemption = float(ext["hra_exemption"])


@router.post("", response_model=AnalyzeResponse)
async def analyze_tax_assessment(
    request: AnalyzeRequest,
    session_store: SessionStore = Depends(get_session_store),
):
    """
    Unified tax analysis endpoint serving both API clients and web frontend.
    Computes both regimes, evaluates 8 schemes, calculates 'show why' trace,
    performs OCR dual check, and returns full comparison.
    """
    session_id = request.sessionId or request.session_id or str(uuid.uuid4())
    profile = None
    session = session_store.get_session(session_id)
    raw_p = request.profile if isinstance(request.profile, dict) else (request.profile.model_dump() if hasattr(request.profile, "model_dump") else {})

    # 1. Resolve Profile from web payload, domain profile, or session
    if request.profile:
        profile = profile_dict_to_tax_profile(raw_p)
    elif request.tax_profile:
        profile = request.tax_profile.model_copy(deep=True)
    elif session and session.tax_profile:
        profile = session.tax_profile.model_copy(deep=True)
    else:
        profile = TaxProfile(financial_year=request.financial_year or "2024-25")

    if request.financial_year:
        profile.financial_year = request.financial_year

    # 2. Map input document to profile if present
    if request.document:
        map_document_to_profile(request.document, profile)
    elif session and session.documents:
        map_session_documents_to_profile(session.documents, profile)

    # 3. Perform Rules Engine evaluation for both regimes
    fy = profile.financial_year or "2024-25"
    try:
        eval_res = evaluate_tax_profile(profile, version_or_fy=fy)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rules evaluation failed: {str(e)}",
        )

    # 4. Perform Dual-Check OCR validation
    warnings: List[str] = []
    if session and session.documents:
        for doc_id, doc_data in session.documents.items():
            check_result = validate_ocr_vs_computed(eval_res.tax_profile, doc_data)
            if not check_result.is_consistent:
                warnings.extend(check_result.discrepancies)

    # 5. Calculate Comprehensive Single Regimes & 8 Schemes for Frontend
    single_new = calculate_single_regime(profile, TaxRegime.NEW, raw_p)
    single_old = calculate_single_regime(profile, TaxRegime.OLD, raw_p)
    schemes_8 = evaluate_8_schemes(profile, raw_p)

    new_tax = single_new["total_tax"]
    old_tax = single_old["total_tax"]
    savings = abs(old_tax - new_tax)
    rec_regime = "new" if new_tax <= old_tax else "old"

    if rec_regime == "new":
        rec_reason = (
            f"The New Tax Regime results in ₹{savings:,.0f} lower tax liability (₹{new_tax:,.0f} vs ₹{old_tax:,.0f}) "
            f"due to progressive slab rates and the ₹75,000 standard deduction."
        )
    else:
        rec_reason = (
            f"The Old Tax Regime results in ₹{savings:,.0f} lower tax liability (₹{old_tax:,.0f} vs ₹{new_tax:,.0f}) "
            f"by claiming ₹{single_old['deductions_claimed']:,.0f} in Chapter VI-A statutory deductions and exemptions."
        )

    recommendations = build_recommendations(schemes_8, savings)

    # Attach 8 schemes to both comparison results
    single_new["schemes"] = schemes_8
    single_old["schemes"] = schemes_8
    active_result = single_new if rec_regime == "new" else single_old

    # 6. Generate AI Explanation summary
    explanation_text = ""
    if request.include_recommendations:
        preferred_lang = eval_res.tax_profile.metadata.get("preferred_language", "en")
        try:
            explanation_text = generate_explanation(eval_res, preferred_language=preferred_lang)
            eval_res.tax_profile.metadata["explanation"] = explanation_text
        except Exception:
            explanation_text = generate_llm_explanation_sync(profile, single_new, single_old, rec_regime, savings)
            eval_res.tax_profile.metadata["explanation"] = explanation_text
    else:
        explanation_text = generate_llm_explanation_sync(profile, single_new, single_old, rec_regime, savings)

    # Update session profile state with computed values
    session_store.set_tax_profile(session_id, eval_res.tax_profile)

    # 7. Populate Deductions and Schemes lists from rule evaluation for legacy tests
    deductions_results = []
    schemes_results = []
    for rule in eval_res.applied_rules:
        if rule.is_applicable and rule.is_eligible:
            if rule.category in (RuleCategory.DEDUCTION, RuleCategory.EXEMPTION):
                deductions_results.append(
                    DeductionResult(
                        title=rule.rule_name,
                        amount=rule.eligible_amount,
                        ruleId=rule.rule_id,
                        reason=build_reason(rule),
                        confidence="confirmed",
                    )
                )
            else:
                schemes_results.append(
                    SchemeResult(
                        title=rule.rule_name,
                        ruleId=rule.rule_id,
                        reason=build_reason(rule),
                        confidence="confirmed",
                    )
                )

    return AnalyzeResponse(
        # Frontend fields
        session_id=session_id,
        profile=raw_p or eval_res.tax_profile.model_dump(),
        explanation=explanation_text,
        warnings=warnings,
        result=active_result,
        comparison={
            "new": single_new,
            "old": single_old,
            "recommended_regime": rec_regime,
            "estimated_savings": savings,
            "reason": rec_reason,
        },
        recommendations=recommendations,

        # Legacy & Test contract fields
        deductions=deductions_results,
        schemes=schemes_results if not request.profile else schemes_8,
        tax_profile=eval_res.tax_profile,
        recommended_regime=TaxRegime.NEW if rec_regime == "new" else TaxRegime.OLD,
        old_regime_liability=old_tax,
        new_regime_liability=new_tax,
        potential_savings=savings,
        applied_rules=eval_res.applied_rules,
        optimization_tips=eval_res.optimization_tips,
    )
 