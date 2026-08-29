"""Router for exporting tax analysis reports."""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.analyze import build_reason
from app.pdf.filing_summary import generate_filing_summary_pdf
from app.rules_engine.evaluator import evaluate_tax_profile
from app.schemas.api import AnalyzeResponse, DeductionResult, SchemeResult
from app.schemas.domain import RuleCategory
from app.session import get_session_store, SessionStore

router = APIRouter(prefix="/export", tags=["export"])



@router.get("/health")
def health():
    return {"status": "ok", "service": "export"}


@router.get("/pdf")
def download_filing_summary(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store)
):
    """
    Generate and download the structured ReportLab PDF filing summary for a given session.
    Retrieves the tax profile, executes the rules engine, and compiles the comparison PDF.
    """
    # 1. Fetch active session
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found or has expired."
        )

    # 2. Check if a tax profile exists
    profile = session.tax_profile
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tax profile is associated with this session. Run analysis first."
        )

    # 3. Perform rules evaluation
    try:
        eval_res = evaluate_tax_profile(profile, version_or_fy=profile.financial_year)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rules engine evaluation failed: {str(e)}"
        )

    # 4. Map evaluation output to AnalyzeResponse structure
    deductions_results = []
    schemes_results = []
    for rule in eval_res.applied_rules:
        if rule.is_applicable and rule.is_eligible:
            if rule.category in (RuleCategory.DEDUCTION, RuleCategory.EXEMPTION):
                deductions_results.append(DeductionResult(
                    title=rule.rule_name,
                    amount=rule.eligible_amount,
                    ruleId=rule.rule_id,
                    reason=build_reason(rule),
                    confidence="confirmed"
                ))
            else:
                schemes_results.append(SchemeResult(
                    title=rule.rule_name,
                    ruleId=rule.rule_id,
                    reason=build_reason(rule),
                    confidence="confirmed"
                ))

    # Calculate validation warnings on the fly
    warnings = []
    if session.documents:
        from app.dual_check.validator import validate_ocr_vs_computed
        for doc_data in session.documents.values():
            check_result = validate_ocr_vs_computed(eval_res.tax_profile, doc_data)
            if not check_result.is_consistent:
                warnings.extend(check_result.discrepancies)

    analysis = AnalyzeResponse(
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

    # 5. Extract explanation summary from metadata (if generated previously)
    explanation = profile.metadata.get("explanation")

    # 6. Generate ReportLab PDF bytes
    try:
        pdf_bytes = generate_filing_summary_pdf(
            profile=eval_res.tax_profile,
            analysis=analysis,
            explanation=explanation
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ReportLab PDF generation failed: {str(e)}"
        )

    # 7. Return file response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="filing_summary_{session_id}.pdf"'
        }
    )
 