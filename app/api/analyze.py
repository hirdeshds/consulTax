"""Router for tax profile and document analysis computations."""

from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.api import (
    AnalyzeRequest,
    AnalyzeResponse,
    DeductionResult,
    FrontendComparison,
    FrontendProfileInput,
    FrontendRecommendation,
    FrontendTaxResult,
    SchemeResult,
)
from app.schemas.domain import (
    DocumentData,
    IncomeDetails,
    DeductionDetails,
    RuleCategory,
    RuleResult,
    TaxDocument,
    TaxProfile,
    TaxRegime,
)
from app.session import get_session_store, SessionStore
from app.rules_engine.evaluator import (
    calculate_tax_for_regime,
    evaluate_tax_profile,
    load_rules_config,
)
from app.dual_check.validator import validate_ocr_vs_computed
from app.explanation.generator import generate_explanation

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

    return rule.description or f"Eligible deduction under {sect}"


def map_flat_profile_to_tax_profile(raw_profile: Any, financial_year_override: Optional[str] = None) -> TaxProfile:
    """Map flat profile input from frontend into domain TaxProfile model."""
    if isinstance(raw_profile, dict):
        p = raw_profile
    elif hasattr(raw_profile, "model_dump"):
        p = raw_profile.model_dump()
    elif hasattr(raw_profile, "__dict__"):
        p = raw_profile.__dict__
    else:
        p = {}

    fy = financial_year_override or p.get("financial_year") or "2024-25"
    age = int(p.get("age", 30)) if p.get("age") is not None else 30
    is_senior = age >= 60
    is_super_senior = age >= 80

    emp_inc = float(p.get("employment_income") or 0.0)
    biz_rev = float(p.get("business_revenue") or 0.0)
    biz_exp = float(p.get("business_expenses") or 0.0)
    biz_profit = max(0.0, biz_rev - biz_exp)
    oth_inc = float(p.get("other_income") or 0.0)
    div_inc = float(p.get("dividend_income") or 0.0)
    rent_inc = float(p.get("rental_income") or 0.0)
    cap_gains = float(p.get("capital_gains") or 0.0)

    basic_salary = float(p.get("basic_salary") or 0.0)
    hra_rec = float(p.get("hra_received") or 0.0)
    rent_paid = float(p.get("annual_rent_paid") or 0.0)
    is_metro = str(p.get("residential_location", "metro")).lower() == "metro"

    # Compute Section 10(13A) HRA exemption
    hra_exemption = 0.0
    if hra_rec > 0 and rent_paid > 0:
        base_for_hra = basic_salary if basic_salary > 0 else emp_inc * 0.50
        limit_a = hra_rec
        limit_b = max(0.0, rent_paid - 0.10 * base_for_hra)
        limit_c = (0.50 if is_metro else 0.40) * base_for_hra
        hra_exemption = min(limit_a, limit_b, limit_c)

    # Compute Section 80C
    pf = float(p.get("provident_fund") or 0.0)
    elss = float(p.get("elss_investment") or 0.0)
    lic = float(p.get("life_insurance_premium") or 0.0)
    tuition = float(p.get("children_tuition_fees") or 0.0)
    hl_principal = float(p.get("home_loan_principal") or 0.0)
    total_80c = pf + elss + lic + tuition + hl_principal

    # Compute Section 80D
    health_self = float(p.get("health_insurance_self_family") or 0.0)
    health_parents = float(p.get("health_insurance_parents") or 0.0)
    parent_med = float(p.get("parent_medical_spend") or 0.0)
    total_80d = health_self + health_parents + parent_med

    # Section 24(b), 80E, 80G, 80DDB
    sec_24b = float(p.get("home_loan_interest") or 0.0)
    sec_80e = float(p.get("education_loan_interest") or 0.0)
    sec_80g = float(p.get("charity_donations") or 0.0) * 0.50
    sec_80ddb = float(p.get("eligible_medical_treatment") or 0.0)

    # Taxes paid
    tax_paid = float(p.get("tax_paid") or 0.0)

    income = IncomeDetails(
        salary=emp_inc,
        house_property=rent_inc,
        capital_gains_short_term=cap_gains,
        capital_gains_long_term=0.0,
        business_profession=biz_profit,
        other_sources=oth_inc + div_inc,
    )

    deductions = DeductionDetails(
        section_80c=total_80c,
        section_80d=total_80d,
        section_24b=sec_24b,
        section_80e=sec_80e,
        section_80g=sec_80g,
        section_80ddb=sec_80ddb,
        hra_exemption=hra_exemption,
    )

    metadata = {
        "name": p.get("name", "Taxpayer"),
        "raw_profile": p,
    }

    return TaxProfile(
        financial_year=fy,
        age=age,
        is_senior_citizen=is_senior,
        is_super_senior_citizen=is_super_senior,
        residential_status="resident" if p.get("is_resident", True) else "non_resident",
        income=income,
        deductions=deductions,
        tax_paid_tds=tax_paid,
        metadata=metadata,
    )


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


def build_tax_result_for_regime(
    calc_data: Dict[str, Any],
    profile: TaxProfile,
    regime_name: str,
    fy: str,
) -> FrontendTaxResult:
    """Convert calculation dictionary into structured FrontendTaxResult model."""
    gross = calc_data["gross_income"]
    taxable = calc_data["net_taxable_income"]
    total_tax = calc_data["total_tax_liability"]
    tax_paid = profile.tax_paid_tds + profile.tax_paid_advance + profile.tax_paid_self_assessment
    payable = max(0.0, round(total_tax - tax_paid, 2))
    refund = max(0.0, round(tax_paid - total_tax, 2))

    rule_results: List[RuleResult] = calc_data.get("rule_results", [])
    std_ded = 0.0
    deduction_breakdown: Dict[str, float] = {}
    for r in rule_results:
        if r.eligible_amount > 0:
            deduction_breakdown[r.rule_name] = r.eligible_amount
        if r.rule_id == "sec_standard_deduction":
            std_ded = r.eligible_amount

    deductions_claimed = calc_data["total_deductions"]

    trace: List[str] = [
        f"Gross Total Income across all heads: ₹{gross:,.2f}",
        f"Standard deduction under Section 16(ia): ₹{std_ded:,.2f}",
        f"Total eligible deductions and exemptions: ₹{deductions_claimed:,.2f}",
        f"Net Taxable Income after deductions: ₹{taxable:,.2f}",
        f"Base tax from progressive slab tiers: ₹{calc_data['base_slab_tax']:,.2f}",
    ]
    if calc_data.get("rebate_87a", 0) > 0:
        trace.append(f"Section 87A Tax Rebate applied: ₹{calc_data['rebate_87a']:,.2f}")
    if calc_data.get("surcharge", 0) > 0:
        trace.append(f"Surcharge on tax ({calc_data.get('surcharge_rate', 0)*100:.0f}%): ₹{calc_data['surcharge']:,.2f}")
    trace.append(f"Health & Education Cess (4%): ₹{calc_data['cess']:,.2f}")
    trace.append(f"Final Estimated Total Tax Liability: ₹{total_tax:,.2f}")
    if tax_paid > 0:
        trace.append(f"Tax already deducted/paid (TDS/Advance): ₹{tax_paid:,.2f}")
        if payable > 0:
            trace.append(f"Estimated Net Tax Still Payable: ₹{payable:,.2f}")
        else:
            trace.append(f"Estimated Tax Refund Due: ₹{refund:,.2f}")

    return FrontendTaxResult(
        gross_income=gross,
        taxable_income=taxable,
        total_tax=total_tax,
        tax_paid=tax_paid,
        payable=payable,
        refund=refund,
        regime=regime_name,
        rule_version=fy,
        standard_deduction=std_ded,
        deductions_claimed=deductions_claimed,
        deduction_breakdown=deduction_breakdown,
        excluded_income={},
        trace=trace,
    )


def generate_recommendations(profile: TaxProfile, old_calc: Dict[str, Any]) -> List[FrontendRecommendation]:
    """Generate rich, actionable tax optimization recommendations."""
    recs: List[FrontendRecommendation] = []
    d = profile.deductions

    # 1. Section 80C
    c_limit = 150000.0
    c_claimed = d.section_80c
    if c_claimed < c_limit:
        headroom = c_limit - c_claimed
        savings = round(headroom * 0.30, 2)
        recs.append(
            FrontendRecommendation(
                section="Section 80C",
                title="Maximise Section 80C Deductions (ELSS, PPF, EPF, Life Insurance)",
                potential_deduction=headroom,
                estimated_tax_saving=savings,
                reason=f"You have ₹{headroom:,.0f} in unused Section 80C headroom. Claiming this fully reduces taxable income in the Old Regime.",
                conditions="Invest in eligible instruments (ELSS, PPF, EPF, NSC, SSY, or tuition fees) before the end of the financial year.",
            )
        )

    # 2. Section 80CCD(1B) - NPS Additional
    nps_limit = 50000.0
    nps_claimed = d.section_80ccd_1b
    if nps_claimed < nps_limit:
        headroom = nps_limit - nps_claimed
        savings = round(headroom * 0.30, 2)
        recs.append(
            FrontendRecommendation(
                section="Section 80CCD(1B)",
                title="Voluntary National Pension System (NPS Tier-1) Investment",
                potential_deduction=headroom,
                estimated_tax_saving=savings,
                reason=f"Exclusive ₹{nps_limit:,.0f} deduction available over and above the ₹1.5L 80C limit.",
                conditions="Direct voluntary deposit into your individual Tier-1 NPS PRAN account.",
            )
        )

    # 3. Section 80D - Health Insurance
    d_limit = 50000.0 if profile.is_senior_citizen else 25000.0
    parents_limit = 50000.0
    total_d_max = d_limit + parents_limit
    d_claimed = d.section_80d
    if d_claimed < total_d_max:
        headroom = total_d_max - d_claimed
        savings = round(headroom * 0.30, 2)
        recs.append(
            FrontendRecommendation(
                section="Section 80D",
                title="Health Insurance & Preventive Health Checkup",
                potential_deduction=headroom,
                estimated_tax_saving=savings,
                reason=f"Covers health insurance premiums and preventive health checkups (up to ₹5,000 within the overall cap).",
                conditions="Pay health insurance premiums by non-cash banking mode (online/cheque) for self, spouse, children, or parents.",
            )
        )

    # 4. Section 80CCD(2) - Corporate NPS
    if profile.income.salary > 0 and d.section_80ccd_2 == 0:
        nps_corp_limit = round(profile.income.salary * 0.14, 2)
        savings = round(nps_corp_limit * 0.30, 2)
        recs.append(
            FrontendRecommendation(
                section="Section 80CCD(2)",
                title="Employer NPS Contribution (Available in BOTH New & Old Regimes)",
                potential_deduction=nps_corp_limit,
                estimated_tax_saving=savings,
                reason="Employer contribution to NPS is tax-exempt up to 14% of basic salary in both New and Old regimes.",
                conditions="Request your employer/HR to restructure CTC to route part of salary into Corporate NPS.",
            )
        )

    # 5. Section 24(b) - Home Loan Interest
    if d.section_24b > 0 and d.section_24b < 200000.0:
        headroom = 200000.0 - d.section_24b
        savings = round(headroom * 0.30, 2)
        recs.append(
            FrontendRecommendation(
                section="Section 24(b)",
                title="Home Loan Interest on Self-Occupied Property",
                potential_deduction=headroom,
                estimated_tax_saving=savings,
                reason=f"Interest on housing loan for self-occupied residential property is deductible up to ₹2,00,000.",
                conditions="Obtain annual interest certificate from the lending financial institution.",
            )
        )

    # 6. Section 80E - Education Loan Interest
    if d.section_80e > 0:
        recs.append(
            FrontendRecommendation(
                section="Section 80E",
                title="Higher Education Loan Interest Deduction",
                potential_deduction=d.section_80e,
                estimated_tax_saving=round(d.section_80e * 0.30, 2),
                reason="Full interest paid on loan taken for higher education of self, spouse, or children is 100% deductible with no upper limit for up to 8 years.",
                conditions="Loan must be obtained from a scheduled bank or approved financial institution.",
            )
        )

    return recs


@router.post("", response_model=AnalyzeResponse)
async def analyze_tax_assessment(
    request: AnalyzeRequest,
    session_store: SessionStore = Depends(get_session_store),
):
    """
    POST endpoint that connects Document mapping, Rules Engine computation,
    OCR dual-check validator, and AI advice explanation generation.
    Supports both Frontend profile input and domain models seamlessly.
    """
    session_id = request.sessionId or request.session_id
    if not session_id:
        new_sess = session_store.create_session()
        session_id = new_sess.session_id

    session = session_store.get_session(session_id)
    if not session:
        session = session_store.create_session(session_id=session_id)

    profile = None

    # 1. Resolve Tax Profile from flat profile, domain tax_profile, or session
    if request.profile:
        profile = map_flat_profile_to_tax_profile(request.profile, request.financial_year)
    elif request.tax_profile:
        profile = request.tax_profile.model_copy(deep=True)
    elif session and session.tax_profile:
        profile = session.tax_profile.model_copy(deep=True)

    if not profile:
        profile = TaxProfile(financial_year=request.financial_year or "2024-25")

    if request.financial_year:
        profile.financial_year = request.financial_year

    # 2. Map input document to profile if present
    if request.document:
        map_document_to_profile(request.document, profile)
    elif session and session.documents:
        map_session_documents_to_profile(session.documents, profile)

    # 3. Evaluate tax for both regimes
    fy = profile.financial_year or "2024-25"
    try:
        new_calc = calculate_tax_for_regime(profile, TaxRegime.NEW, fy)
        old_calc = calculate_tax_for_regime(profile, TaxRegime.OLD, fy)
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

    # 5. Generate AI Explanation summary
    explanation_text = ""
    if request.include_recommendations:
        preferred_lang = eval_res.tax_profile.metadata.get("preferred_language", "en")
        try:
            explanation_text = generate_explanation(eval_res, preferred_language=preferred_lang)
            eval_res.tax_profile.metadata["explanation"] = explanation_text
        except Exception as e:
            warnings.append(f"AI explanation generation note: {str(e)}")
            explanation_text = f"Calculated based on FY {fy} rules. {eval_res.recommended_regime.value.upper()} regime minimizes tax."

    # Update session profile state with computed values
    session_store.set_tax_profile(session_id, eval_res.tax_profile)

    # 6. Build Frontend TaxResults, Comparison, and Recommendations
    new_tax_result = build_tax_result_for_regime(new_calc, profile, "new", fy)
    old_tax_result = build_tax_result_for_regime(old_calc, profile, "old", fy)

    rec_regime = "new" if new_calc["total_tax_liability"] <= old_calc["total_tax_liability"] else "old"
    diff_savings = round(abs(old_calc["total_tax_liability"] - new_calc["total_tax_liability"]), 2)
    reason_str = (
        f"The {rec_regime.upper()} Tax Regime results in ₹{diff_savings:,.2f} lower estimated tax. "
        + ("It offers standard deduction of ₹75,000 and zero tax up to ₹7 Lakhs." if rec_regime == "new" else "Your claimed deductions under Chapter VI-A yield higher tax savings in the Old Regime.")
    )

    comparison = FrontendComparison(
        new=new_tax_result,
        old=old_tax_result,
        recommended_regime=rec_regime,
        estimated_savings=diff_savings,
        reason=reason_str,
    )

    active_result = new_tax_result if rec_regime == "new" else old_tax_result
    recommendations_list = generate_recommendations(profile, old_calc)

    # Populate Deductions and Schemes lists from rule evaluation for legacy tests
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
        session_id=session_id,
        explanation=explanation_text or reason_str,
        warnings=warnings,
        result=active_result,
        comparison=comparison,
        recommendations=recommendations_list,
        deductions=deductions_results,
        schemes=schemes_results,
        tax_profile=eval_res.tax_profile,
        recommended_regime=eval_res.recommended_regime,
        old_regime_liability=eval_res.old_regime_liability,
        new_regime_liability=eval_res.new_regime_liability,
        potential_savings=eval_res.potential_savings,
        applied_rules=eval_res.applied_rules,
        optimization_tips=eval_res.optimization_tips,
    )
