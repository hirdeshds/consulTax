"""Unified tax calculation, scheme analysis, and explanation service for consulTax."""

from __future__ import annotations

import json
import math
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.rules_engine.evaluator import (
    apply_rebate_87a,
    calculate_gross_income,
    calculate_slab_tax,
    calculate_surcharge,
    evaluate_tax_profile,
)
from app.rules_engine.loader import load_rules_config
from app.schemas.api import (
    AnalyzeResponse,
    DeductionResult,
    DISCLAIMER,
    SchemeResult,
)
from app.schemas.domain import (
    DeductionDetails,
    IncomeDetails,
    RuleCategory,
    RuleResult,
    TaxProfile,
    TaxRegime,
)


def profile_dict_to_tax_profile(p: Dict[str, Any]) -> TaxProfile:
    """Map the frontend state dictionary into domain TaxProfile model."""
    age = int(p.get("age", 30))
    is_senior = age >= 60
    is_super_senior = age >= 80

    fy = str(p.get("financial_year", "2024-2025"))
    if not fy.startswith("20") or "-" not in fy:
        fy = "2024-2025"
    elif len(fy) == 7:  # e.g. 2025-26 -> 2025-2026
        parts = fy.split("-")
        if len(parts[1]) == 2:
            fy = f"{parts[0]}-20{parts[1]}"

    # Income streams
    salary = float(p.get("employment_income", p.get("salary", 0)) or 0)
    biz_rev = float(p.get("business_revenue", 0) or 0)
    biz_exp = float(p.get("business_expenses", 0) or 0)
    biz_income = max(0.0, biz_rev - biz_exp) if (biz_rev or biz_exp) else float(p.get("business_income", p.get("business_profession", 0)) or 0)
    
    rental_income = float(p.get("rental_income", p.get("house_property", 0)) or 0)
    other_income = float(p.get("other_income", 0) or 0)
    savings_interest = float(p.get("savings_interest", 0) or 0)
    total_other = max(other_income, savings_interest)

    income_details = IncomeDetails(
        salary=salary,
        business_profession=biz_income,
        house_property=rental_income,
        other_sources=total_other,
    )

    # Deductions
    provident_fund = float(p.get("provident_fund", 0) or 0)
    elss = float(p.get("elss_investment", 0) or 0)
    life_ins = float(p.get("life_insurance_premium", 0) or 0)
    tuition = float(p.get("children_tuition_fees", 0) or 0)
    home_loan_prin = float(p.get("home_loan_principal", 0) or 0)
    sec_80c_total = float(p.get("section_80c", 0) or 0)
    if not sec_80c_total:
        sec_80c_total = provident_fund + elss + life_ins + tuition + home_loan_prin

    nps_tier1 = float(p.get("nps_tier1_80ccd", p.get("section_80ccd_1b", 0)) or 0)
    health_self = float(p.get("health_insurance_self_family", p.get("section_80d", 0)) or 0)
    health_parents = float(p.get("health_insurance_parents", 0) or 0)
    parent_medical = float(p.get("parent_medical_spend", 0) or 0)
    sec_80d_total = health_self + health_parents + parent_medical

    home_loan_interest = float(p.get("home_loan_interest", p.get("section_24b", 0)) or 0)
    education_loan = float(p.get("education_loan_interest", p.get("section_80e", 0)) or 0)
    charity = float(p.get("charity_donations", p.get("section_80g", 0)) or 0)
    medical_treatment = float(p.get("eligible_medical_treatment", p.get("section_80ddb", 0)) or 0)

    # HRA exemption
    basic_salary = float(p.get("basic_salary", salary * 0.5) or 0)
    hra_received = float(p.get("hra_received", 0) or 0)
    rent_paid = float(p.get("annual_rent_paid", 0) or 0)
    is_metro = p.get("residential_location", "metro") == "metro"

    hra_exemption = 0.0
    if hra_received > 0 and rent_paid > 0 and basic_salary > 0:
        c1 = hra_received
        c2 = max(0.0, rent_paid - (0.10 * basic_salary))
        c3 = (0.50 if is_metro else 0.40) * basic_salary
        hra_exemption = min(c1, c2, c3)

    # Section 80TTA / 80TTB
    sec_80tta = 0.0
    sec_80ttb = 0.0
    if savings_interest > 0:
        if is_senior:
            sec_80ttb = min(savings_interest, 50000.0)
        else:
            sec_80tta = min(savings_interest, 10000.0)

    deduction_details = DeductionDetails(
        section_80c=sec_80c_total,
        section_80ccd_1b=nps_tier1,
        section_80d=sec_80d_total,
        section_24b=home_loan_interest,
        section_80e=education_loan,
        section_80g=charity,
        section_80ddb=medical_treatment,
        section_80tta=sec_80tta,
        section_80ttb=sec_80ttb,
        hra_exemption=hra_exemption,
    )

    tax_paid = float(p.get("tax_paid", p.get("tax_paid_tds", 0)) or 0)
    regime_pref = TaxRegime.NEW if str(p.get("regime", "new")).lower() == "new" else TaxRegime.OLD

    return TaxProfile(
        financial_year=fy,
        assessment_year="2025-2026",
        regime_preference=regime_pref,
        age=age,
        is_senior_citizen=is_senior,
        is_super_senior_citizen=is_super_senior,
        income=income_details,
        deductions=deduction_details,
        tax_paid_tds=tax_paid,
        metadata={"raw_profile": p},
    )


def calculate_single_regime(
    profile: TaxProfile,
    regime: TaxRegime,
    raw_p: Dict[str, Any],
) -> Dict[str, Any]:
    """Calculate complete tax breakdown for one regime with transparent trace."""
    is_new = regime == TaxRegime.NEW
    gross_income = calculate_gross_income(profile.income)
    salary_income = profile.income.salary

    # Standard deduction
    if is_new:
        std_ded = min(salary_income, 75000.0) if salary_income > 0 else 0.0
    else:
        std_ded = min(salary_income, 50000.0) if salary_income > 0 else 0.0

    trace: List[str] = [
        f"Aggregated Gross Income from all sources: ₹{gross_income:,.0f}."
    ]

    deductions_claimed = 0.0
    deduction_breakdown: Dict[str, float] = {}

    if std_ded > 0:
        deductions_claimed += std_ded
        deduction_breakdown["Standard Deduction"] = std_ded
        trace.append(
            f"Standard Deduction applied u/s 16(ia): ₹{std_ded:,.0f} ({'New Regime ₹75k' if is_new else 'Old Regime ₹50k'})."
        )

    if not is_new:
        # 80C
        sec_80c = min(profile.deductions.section_80c, 150000.0)
        if sec_80c > 0:
            deductions_claimed += sec_80c
            deduction_breakdown["Section 80C"] = sec_80c
            trace.append(f"Section 80C (EPF/PPF/ELSS/Tuition): ₹{sec_80c:,.0f} applied (statutory cap ₹1.5L).")

        # 80CCD(1B)
        sec_80ccd_1b = min(profile.deductions.section_80ccd_1b, 50000.0)
        if sec_80ccd_1b > 0:
            deductions_claimed += sec_80ccd_1b
            deduction_breakdown["Section 80CCD(1B) NPS"] = sec_80ccd_1b
            trace.append(f"Section 80CCD(1B) NPS Tier-1: ₹{sec_80ccd_1b:,.0f} applied (exclusive ₹50k cap).")

        # 80D
        age = profile.age or 30
        self_cap = 50000.0 if age >= 60 else 25000.0
        parent_cap = 50000.0 if raw_p.get("parent_is_senior", False) else 25000.0
        max_80d = self_cap + parent_cap
        sec_80d = min(profile.deductions.section_80d, max_80d)
        if sec_80d > 0:
            deductions_claimed += sec_80d
            deduction_breakdown["Section 80D Health Insurance"] = sec_80d
            trace.append(f"Section 80D Health Insurance: ₹{sec_80d:,.0f} applied (cap ₹{max_80d:,.0f}).")

        # 24(b) Home Loan Interest
        sec_24b = min(profile.deductions.section_24b, 200000.0)
        if sec_24b > 0:
            deductions_claimed += sec_24b
            deduction_breakdown["Section 24(b) Home Loan Interest"] = sec_24b
            trace.append(f"Section 24(b) Home Loan Interest: ₹{sec_24b:,.0f} applied (statutory cap ₹2.0L).")

        # 80E Education loan
        sec_80e = profile.deductions.section_80e
        if sec_80e > 0:
            deductions_claimed += sec_80e
            deduction_breakdown["Section 80E Education Loan"] = sec_80e
            trace.append(f"Section 80E Education Loan Interest: ₹{sec_80e:,.0f} (100% deduction with no upper cap).")

        # 80TTA / 80TTB
        sec_80tta = profile.deductions.section_80tta
        sec_80ttb = profile.deductions.section_80ttb
        if sec_80ttb > 0:
            deductions_claimed += sec_80ttb
            deduction_breakdown["Section 80TTB Senior Interest"] = sec_80ttb
            trace.append(f"Section 80TTB Senior Deposit Interest: ₹{sec_80ttb:,.0f} (cap ₹50,000).")
        elif sec_80tta > 0:
            deductions_claimed += sec_80tta
            deduction_breakdown["Section 80TTA Savings Interest"] = sec_80tta
            trace.append(f"Section 80TTA Savings Interest: ₹{sec_80tta:,.0f} (cap ₹10,000).")

        # HRA Exemption
        hra_ex = profile.deductions.hra_exemption
        if hra_ex > 0:
            deductions_claimed += hra_ex
            deduction_breakdown["Section 10(13A) HRA Exemption"] = hra_ex
            trace.append(f"HRA Exemption u/s 10(13A): ₹{hra_ex:,.0f} exempted.")

        # 80G
        sec_80g = profile.deductions.section_80g * 0.5  # 50% category
        max_80g = max(0.0, (gross_income - (deductions_claimed - std_ded)) * 0.10)
        sec_80g_applied = min(sec_80g, max_80g)
        if sec_80g_applied > 0:
            deductions_claimed += sec_80g_applied
            deduction_breakdown["Section 80G Donations"] = sec_80g_applied
            trace.append(f"Section 80G Charitable Donations: ₹{sec_80g_applied:,.0f} (50% qualifying amount).")

        # 80DDB
        sec_80ddb_cap = 100000.0 if age >= 60 else 40000.0
        sec_80ddb = min(profile.deductions.section_80ddb, sec_80ddb_cap)
        if sec_80ddb > 0:
            deductions_claimed += sec_80ddb
            deduction_breakdown["Section 80DDB Medical Treatment"] = sec_80ddb
            trace.append(f"Section 80DDB Specified Disease Spend: ₹{sec_80ddb:,.0f} (cap ₹{sec_80ddb_cap:,.0f}).")

    taxable_income = max(0.0, gross_income - deductions_claimed)
    trace.append(
        f"Net Taxable Income after deductions: ₹{gross_income:,.0f} - ₹{deductions_claimed:,.0f} = ₹{taxable_income:,.0f}."
    )

    # Slabs calculation
    if is_new:
        slabs = [
            {"min": 0, "max": 300000, "rate": 0.0},
            {"min": 300000, "max": 700000, "rate": 0.05},
            {"min": 700000, "max": 1000000, "rate": 0.10},
            {"min": 1000000, "max": 1200000, "rate": 0.15},
            {"min": 1200000, "max": 1500000, "rate": 0.20},
            {"min": 1500000, "max": None, "rate": 0.30},
        ]
        rebate_cfg = {"threshold_income": 700000.0, "max_rebate": 25000.0, "marginal_relief": True}
    else:
        age = profile.age or 30
        if age >= 80:
            slabs = [
                {"min": 0, "max": 500000, "rate": 0.0},
                {"min": 500000, "max": 1000000, "rate": 0.20},
                {"min": 1000000, "max": None, "rate": 0.30},
            ]
        elif age >= 60:
            slabs = [
                {"min": 0, "max": 300000, "rate": 0.0},
                {"min": 300000, "max": 500000, "rate": 0.05},
                {"min": 500000, "max": 1000000, "rate": 0.20},
                {"min": 1000000, "max": None, "rate": 0.30},
            ]
        else:
            slabs = [
                {"min": 0, "max": 250000, "rate": 0.0},
                {"min": 250000, "max": 500000, "rate": 0.05},
                {"min": 500000, "max": 1000000, "rate": 0.20},
                {"min": 1000000, "max": None, "rate": 0.30},
            ]
        rebate_cfg = {"threshold_income": 500000.0, "max_rebate": 12500.0, "marginal_relief": False}

    base_tax = calculate_slab_tax(taxable_income, slabs)
    trace.append(f"Base progressive slab tax: ₹{base_tax:,.0f}.")

    tax_after_rebate, rebate_amt = apply_rebate_87a(base_tax, taxable_income, rebate_cfg, is_new_regime=is_new)
    if rebate_amt > 0:
        trace.append(f"Section 87A rebate & relief applied: -₹{rebate_amt:,.0f}.")

    # Surcharge
    surcharge_slabs = [
        {"min": 5000000, "max": 10000000, "rate": 0.10},
        {"min": 10000000, "max": 20000000, "rate": 0.15},
        {"min": 20000000, "max": None, "rate": 0.25},
    ]
    surcharge_amt, _ = calculate_surcharge(tax_after_rebate, taxable_income, surcharge_slabs)
    if surcharge_amt > 0:
        trace.append(f"Surcharge on high income: ₹{surcharge_amt:,.0f}.")

    # Cess
    cess = round((tax_after_rebate + surcharge_amt) * 0.04, 2)
    trace.append(f"Health & Education Cess (4%): ₹{cess:,.0f}.")

    total_tax = round(tax_after_rebate + surcharge_amt + cess, 2)
    tax_paid = profile.tax_paid_tds

    payable = max(0.0, round(total_tax - tax_paid, 2))
    refund = max(0.0, round(tax_paid - total_tax, 2))

    if payable > 0:
        trace.append(f"Net Tax Payable after TDS credit (₹{tax_paid:,.0f}): ₹{payable:,.0f}.")
    else:
        trace.append(f"Net Refund Due after TDS credit (₹{tax_paid:,.0f}): ₹{refund:,.0f}.")

    return {
        "gross_income": gross_income,
        "taxable_income": taxable_income,
        "income_tax": base_tax,
        "rebate": rebate_amt,
        "surcharge": surcharge_amt,
        "surcharge_marginal_relief": 0.0,
        "cess": cess,
        "total_tax": total_tax,
        "tax_paid": tax_paid,
        "payable": payable,
        "refund": refund,
        "regime": "new" if is_new else "old",
        "rule_version": f"FY {profile.financial_year}",
        "standard_deduction": std_ded,
        "deductions_claimed": deductions_claimed,
        "deduction_breakdown": deduction_breakdown,
        "excluded_income": {},
        "trace": trace,
    }


def evaluate_8_schemes(profile: TaxProfile, raw_p: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Evaluate the 8 canonical statutory tax-saving schemes for Old Regime planning."""
    age = profile.age or 30
    is_senior = age >= 60

    gross = calculate_gross_income(profile.income)
    tax_rate = 0.312 if gross > 1000000 else (0.208 if gross > 500000 else 0.052)

    schemes: List[Dict[str, Any]] = []

    # 1. Section 80C
    c_claimed = profile.deductions.section_80c
    c_limit = 150000.0
    c_potential = max(0.0, c_limit - c_claimed)
    c_saving = round(c_potential * tax_rate, 0)
    c_status = "claimed" if c_claimed >= c_limit else ("partially_claimed" if c_claimed > 0 else "untapped")
    schemes.append({
        "scheme_id": "80c",
        "section": "Section 80C",
        "name": "EPF, PPF, ELSS, SSY & Home Loan Principal",
        "category": "Savings & Investments",
        "status": c_status,
        "claimed_amount": c_claimed,
        "max_limit": c_limit,
        "potential_deduction": c_potential,
        "estimated_tax_saving": c_saving,
        "trigger_rule": "Eligible statutory investment ceiling is ₹1,50,000 per financial year.",
        "plain_explanation": "Allows deductions for EPF, PPF, tax-saving mutual funds (ELSS), Sukanya Samriddhi Yojana (SSY), Life Insurance premiums, and children's school tuition fees.",
        "eligibility_conditions": "Requires maintaining documentary proofs / receipts under the Old Tax Regime.",
    })

    # 2. Section 80CCD(1B) NPS
    nps_claimed = profile.deductions.section_80ccd_1b
    nps_limit = 50000.0
    nps_potential = max(0.0, nps_limit - nps_claimed)
    nps_saving = round(nps_potential * tax_rate, 0)
    nps_status = "claimed" if nps_claimed >= nps_limit else ("partially_claimed" if nps_claimed > 0 else "untapped")
    schemes.append({
        "scheme_id": "80ccd_1b",
        "section": "Section 80CCD(1B)",
        "name": "National Pension System (NPS Tier-1)",
        "category": "Retirement Scheme",
        "status": nps_status,
        "claimed_amount": nps_claimed,
        "max_limit": nps_limit,
        "potential_deduction": nps_potential,
        "estimated_tax_saving": nps_saving,
        "trigger_rule": "Exclusive ₹50,000 deduction limit over and above the Section 80C cap.",
        "plain_explanation": "Voluntary contributions towards a Tier-1 NPS PRAN account grant an exclusive ₹50k tax shield for long-term retirement savings.",
        "eligibility_conditions": "Applicable only to Tier-1 accounts under Old Tax Regime.",
    })

    # 3. Section 80D Health Insurance
    self_cap = 50000.0 if is_senior else 25000.0
    parent_cap = 50000.0 if raw_p.get("parent_is_senior", False) else 25000.0
    d_limit = self_cap + parent_cap
    d_claimed = profile.deductions.section_80d
    d_potential = max(0.0, d_limit - d_claimed)
    d_saving = round(d_potential * tax_rate, 0)
    d_status = "claimed" if d_claimed >= d_limit else ("partially_claimed" if d_claimed > 0 else "untapped")
    schemes.append({
        "scheme_id": "80d",
        "section": "Section 80D",
        "name": "Medical Insurance & Senior Parent Health",
        "category": "Health & Protection",
        "status": d_status,
        "claimed_amount": d_claimed,
        "max_limit": d_limit,
        "potential_deduction": d_potential,
        "estimated_tax_saving": d_saving,
        "trigger_rule": f"Self/Family limit ₹{self_cap:,.0f} + Parent limit ₹{parent_cap:,.0f} (Total cap ₹{d_limit:,.0f}).",
        "plain_explanation": "Deduction for health insurance premiums for self, spouse, children, and parents. Also covers ₹5,000 preventive checkup.",
        "eligibility_conditions": "Premiums must be paid via non-cash banking channels.",
    })

    # 4. Section 24(b) Home Loan Interest
    hl_claimed = profile.deductions.section_24b
    hl_limit = 200000.0
    hl_potential = max(0.0, hl_limit - hl_claimed) if hl_claimed > 0 else 0.0
    hl_saving = round(hl_potential * tax_rate, 0)
    hl_status = "claimed" if hl_claimed >= hl_limit else ("partially_claimed" if hl_claimed > 0 else "not_applicable")
    schemes.append({
        "scheme_id": "24b",
        "section": "Section 24(b)",
        "name": "Home Loan Interest (Self-Occupied)",
        "category": "Housing & Real Estate",
        "status": hl_status,
        "claimed_amount": hl_claimed,
        "max_limit": hl_limit,
        "potential_deduction": hl_potential,
        "estimated_tax_saving": hl_saving,
        "trigger_rule": "Up to ₹2,00,000 interest deduction on housing loan taken for acquisition/construction.",
        "plain_explanation": "Reduces taxable income directly by the interest paid on housing loans for self-occupied residential property.",
        "eligibility_conditions": "Construction must be completed within 5 years; bank interest certificate required.",
    })

    # 5. Section 80E Education Loan
    edu_claimed = profile.deductions.section_80e
    edu_status = "claimed" if edu_claimed > 0 else "not_applicable"
    schemes.append({
        "scheme_id": "80e",
        "section": "Section 80E",
        "name": "Higher Education Loan Interest",
        "category": "Education & Skilling",
        "status": edu_status,
        "claimed_amount": edu_claimed,
        "max_limit": None,
        "potential_deduction": 0,
        "estimated_tax_saving": round(edu_claimed * tax_rate, 0) if edu_claimed > 0 else 0,
        "trigger_rule": "100% deduction on interest with no upper statutory ceiling for up to 8 years.",
        "plain_explanation": "Deducts full interest paid on education loans taken for self, spouse, or children for higher studies.",
        "eligibility_conditions": "Loan must be sanctioned by a recognized bank or financial institution.",
    })

    # 6. Section 80TTA / 80TTB
    tt_claimed = profile.deductions.section_80ttb if is_senior else profile.deductions.section_80tta
    tt_limit = 50000.0 if is_senior else 10000.0
    tt_potential = max(0.0, tt_limit - tt_claimed)
    tt_saving = round(tt_potential * tax_rate, 0)
    tt_status = "claimed" if tt_claimed >= tt_limit else ("partially_claimed" if tt_claimed > 0 else "untapped")
    schemes.append({
        "scheme_id": "80tta_ttb",
        "section": "Section 80TTB" if is_senior else "Section 80TTA",
        "name": "Deposit Interest Exemption (Senior Citizens)" if is_senior else "Savings Bank Interest Exemption",
        "category": "Banking & Savings",
        "status": tt_status,
        "claimed_amount": tt_claimed,
        "max_limit": tt_limit,
        "potential_deduction": tt_potential,
        "estimated_tax_saving": tt_saving,
        "trigger_rule": f"₹{tt_limit:,.0f} limit on interest earned from savings/fixed deposits.",
        "plain_explanation": "Exempts bank savings interest for individuals, and all deposit interest (including FDs) for senior citizens.",
        "eligibility_conditions": "Old Tax Regime only.",
    })

    # 7. Section 80G Donations
    g_claimed = profile.deductions.section_80g
    g_status = "claimed" if g_claimed > 0 else "not_applicable"
    schemes.append({
        "scheme_id": "80g",
        "section": "Section 80G",
        "name": "Donations to Approved Relief Funds",
        "category": "Philanthropy",
        "status": g_status,
        "claimed_amount": g_claimed,
        "max_limit": None,
        "potential_deduction": 0,
        "estimated_tax_saving": round(g_claimed * 0.5 * tax_rate, 0) if g_claimed > 0 else 0,
        "trigger_rule": "50% or 100% deduction subject to 10% adjusted gross income cap.",
        "plain_explanation": "Tax benefits for donations to authorized charitable trusts, PM Cares / Relief funds.",
        "eligibility_conditions": "Donations above ₹2,000 must be in electronic/banking mode with 10BE receipt.",
    })

    # 8. Section 80DDB Critical Disease Treatment
    ddb_claimed = profile.deductions.section_80ddb
    ddb_limit = 100000.0 if is_senior else 40000.0
    ddb_potential = max(0.0, ddb_limit - ddb_claimed) if ddb_claimed > 0 else 0.0
    ddb_status = "claimed" if ddb_claimed >= ddb_limit else ("partially_claimed" if ddb_claimed > 0 else "not_applicable")
    schemes.append({
        "scheme_id": "80ddb",
        "section": "Section 80DDB",
        "name": "Specified Critical Disease Treatment",
        "category": "Medical Support",
        "status": ddb_status,
        "claimed_amount": ddb_claimed,
        "max_limit": ddb_limit,
        "potential_deduction": ddb_potential,
        "estimated_tax_saving": round(ddb_potential * tax_rate, 0),
        "trigger_rule": f"₹{ddb_limit:,.0f} statutory ceiling for treatment of notified illnesses.",
        "plain_explanation": "Deduction for medical expenditure incurred for treatment of specified critical diseases (cancer, renal failure, neurological disorders).",
        "eligibility_conditions": "Prescription certificate (Form 10-I) from a specialist required.",
    })

    return schemes


def build_recommendations(schemes: List[Dict[str, Any]], diff: float) -> List[Dict[str, Any]]:
    """Build structured actionable recommendations from untapped scheme capacity."""
    recs = []
    for s in schemes:
        if s["status"] in ("untapped", "partially_claimed") and s["potential_deduction"] > 0:
            recs.append({
                "section": s["section"],
                "title": f"Utilize unused capacity in {s['name']}",
                "potential_deduction": s["potential_deduction"],
                "estimated_tax_saving": s["estimated_tax_saving"],
                "reason": f"{s['section']} allows up to ₹{s['max_limit']:,.0f}. You have ₹{s['potential_deduction']:,.0f} unclaimed capacity.",
                "conditions": s["eligibility_conditions"],
            })
    return recs


def generate_llm_explanation_sync(
    profile: TaxProfile,
    new_res: Dict[str, Any],
    old_res: Dict[str, Any],
    recommended: str,
    savings: float,
) -> str:
    """Generate rich plain English tax summary using Groq or Cohere if configured, else deterministic."""
    rec_label = "New Tax Regime" if recommended == "new" else "Old Tax Regime"
    
    if settings.GROQ_API_KEY:
        try:
            import urllib.request
            prompt = (
                f"You are an expert Indian tax advisor. Write a short 3-4 sentence plain-English summary for a taxpayer with "
                f"Gross Salary ₹{profile.income.salary:,.0f}, age {profile.age or 30}. "
                f"Recommended regime: {rec_label}. Tax under New Regime: ₹{new_res['total_tax']:,.0f}, Old Regime: ₹{old_res['total_tax']:,.0f}. "
                f"Total tax saved by choosing {rec_label}: ₹{savings:,.0f}. Mention key deductions."
            )
            req_data = {
                "model": settings.GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 250,
                "temperature": 0.3,
            }
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps(req_data).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

    if recommended == "new":
        return (
            f"Based on your profile with gross income of ₹{new_res['gross_income']:,.0f}, the **New Tax Regime** is optimal, "
            f"resulting in a lower tax liability of ₹{new_res['total_tax']:,.0f} (vs ₹{old_res['total_tax']:,.0f} under Old Regime). "
            f"You save ₹{savings:,.0f} primarily due to lower tax slab rates and the ₹75,000 standard deduction."
        )
    else:
        return (
            f"Based on your claimed deductions of ₹{old_res['deductions_claimed']:,.0f}, the **Old Tax Regime** is optimal, "
            f"resulting in a tax liability of ₹{old_res['total_tax']:,.0f} (vs ₹{new_res['total_tax']:,.0f} under New Regime). "
            f"You save ₹{savings:,.0f} by leveraging Chapter VI-A statutory deductions and exemptions."
        )
