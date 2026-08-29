"""Router for tax profile and document analysis computations."""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional

from app.schemas.api import AnalyzeRequest, AnalyzeResponse, DeductionResult, SchemeResult
from app.schemas.domain import TaxProfile, TaxRegime, RuleCategory, TaxDocument
from app.session import get_session_store, SessionStore
from app.rules_engine.evaluator import evaluate_tax_profile
from app.dual_check.validator import validate_ocr_vs_computed
from app.explanation.generator import generate_explanation

router = APIRouter(prefix="/analyze", tags=["analyze"])


def map_document_to_profile(doc: TaxDocument, profile: TaxProfile) -> None:
    """Maps fields from standard TaxDocument input into a TaxProfile."""
    # 1. Map Income details
    profile.income.salary = doc.income.salary
    profile.income.business_profession = doc.income.business_income
    profile.income.house_property = doc.income.rental_income
    profile.income.other_sources = doc.income.other_income

    # 2. Map deductions details
    profile.deductions.section_80c = doc.investments.section_80c
    profile.deductions.section_80d = doc.investments.health_insurance
    profile.deductions.section_24b = doc.investments.home_loan_interest
    profile.deductions.hra_exemption = doc.investments.other  # Map general investment proof into other if applicable


def map_session_documents_to_profile(documents: dict, profile: TaxProfile) -> None:
    """Maps fields from session DocumentData extracted_fields into a TaxProfile."""
    for doc in documents.values():
        ext = doc.extracted_fields
        if not ext:
            continue
        
        # 1. Map Income details
        if "salary" in ext and ext["salary"] is not None:
            profile.income.salary = float(ext["salary"])
        if "business_income" in ext and ext["business_income"] is not None:
            profile.income.business_profession = float(ext["business_income"])
        elif "business_profession" in ext and ext["business_profession"] is not None:
            profile.income.business_profession = float(ext["business_profession"])
        if "rental_income" in ext and ext["rental_income"] is not None:
            profile.income.house_property = float(ext["rental_income"])
        elif "house_property" in ext and ext["house_property"] is not None:
            profile.income.house_property = float(ext["house_property"])
        if "other_income" in ext and ext["other_income"] is not None:
            profile.income.other_sources = float(ext["other_income"])
        elif "other_sources" in ext and ext["other_sources"] is not None:
            profile.income.other_sources = float(ext["other_sources"])

        # 2. Map deductions details
        if "section_80c" in ext and ext["section_80c"] is not None:
            profile.deductions.section_80c = float(ext["section_80c"])
        if "section_80d" in ext and ext["section_80d"] is not None:
            profile.deductions.section_80d = float(ext["section_80d"])
        elif "health_insurance" in ext and ext["health_insurance"] is not None:
            profile.deductions.section_80d = float(ext["health_insurance"])
        if "section_24b" in ext and ext["section_24b"] is not None:
            profile.deductions.section_24b = float(ext["section_24b"])
        elif "home_loan_interest" in ext and ext["home_loan_interest"] is not None:
            profile.deductions.section_24b = float(ext["home_loan_interest"])
        if "standard_deduction" in ext and ext["standard_deduction"] is not None:
            profile.deductions.standard_deduction = float(ext["standard_deduction"])
        if "hra_exemption" in ext and ext["hra_exemption"] is not None:
            profile.deductions.hra_exemption = float(ext["hra_exemption"])


@router.post("", response_model=AnalyzeResponse)
async def analyze_tax_assessment(
    request: AnalyzeRequest,
    session_store: SessionStore = Depends(get_session_store)
):
    """
    POST endpoint that connects Document mapping, Rules Engine computation,
    OCR dual-check validator, and AI advice explanation generation.
    """
    session_id = request.sessionId
    profile = None
    session = None

    # 1. Resolve Tax Profile
    if session_id:
        session = session_store.get_session(session_id)

    if request.tax_profile:
        profile = request.tax_profile.model_copy(deep=True)
    elif session and session.tax_profile:
        profile = session.tax_profile.model_copy(deep=True)
            
    if not profile:
        profile = TaxProfile(financial_year=request.financial_year or "2024-2025")

    # Override financial year if explicitly provided in request
    if request.financial_year:
        profile.financial_year = request.financial_year

    # 2. Map input document to profile if present
    if request.document:
        map_document_to_profile(request.document, profile)
    elif session and session.documents:
        map_session_documents_to_profile(session.documents, profile)

    # 3. Perform Rules Engine evaluation
    try:
        eval_res = evaluate_tax_profile(profile, version_or_fy=profile.financial_year)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rules evaluation failed: {str(e)}"
        )

    # 4. Perform Dual-Check OCR validation
    warnings = []
    if session:
        for doc_id, doc_data in session.documents.items():
            check_result = validate_ocr_vs_computed(eval_res.tax_profile, doc_data)
            if not check_result.is_consistent:
                warnings.extend(check_result.discrepancies)

    # 5. Generate AI Explanation summary
    if request.include_recommendations:
        preferred_lang = eval_res.tax_profile.metadata.get("preferred_language", "en")
        try:
            explanation = generate_explanation(eval_res, preferred_language=preferred_lang)
            eval_res.tax_profile.metadata["explanation"] = explanation
        except Exception as e:
            # Append parsing failure as a warning and continue
            warnings.append(f"AI explanation generation failed: {str(e)}")

    # Update session profile state with computed values
    if session_id:
        session_store.set_tax_profile(session_id, eval_res.tax_profile)


    # 6. Populate Deductions and Schemes lists from rule evaluation
    deductions_results = []
    schemes_results = []
    
    for rule in eval_res.applied_rules:
        if rule.is_applicable and rule.is_eligible:
            sect = f" under {rule.legal_section}" if rule.legal_section else ""
            if rule.category in (RuleCategory.DEDUCTION, RuleCategory.EXEMPTION):
                deductions_results.append(DeductionResult(
                    title=rule.rule_name,
                    amount=rule.eligible_amount,
                    ruleId=rule.rule_id,
                    reason=rule.description or f"Eligible deduction{sect}",
                    confidence="confirmed"
                ))
            else:
                schemes_results.append(SchemeResult(
                    title=rule.rule_name,
                    ruleId=rule.rule_id,
                    reason=rule.description or f"Eligible tax scheme option{sect}",
                    confidence="confirmed"
                ))

    return AnalyzeResponse(
        deductions=deductions_results,
        schemes=schemes_results,
        warnings=warnings,
        tax_profile=eval_res.tax_profile,
        recommended_regime=eval_res.recommended_regime,
        old_regime_liability=eval_res.old_regime_liability,
        new_regime_liability=eval_res.new_regime_liability,
        potential_savings=eval_res.potential_savings,
        applied_rules=eval_res.applied_rules,
        optimization_tips=eval_res.optimization_tips
    )
