"""Tax calculation and rules evaluation engine for consulTax."""

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from app.rules_engine.loader import load_rules_config
from app.schemas.api import AnalyzeResponse, SimulateResponse
from app.schemas.domain import (
    DeductionDetails,
    IncomeDetails,
    RuleCategory,
    RuleResult,
    TaxProfile,
    TaxRegime,
)


def calculate_gross_income(income: IncomeDetails) -> float:
    """Calculate total gross income across all streams."""
    return (
        income.salary
        + income.house_property
        + income.capital_gains_short_term
        + income.capital_gains_long_term
        + income.business_profession
        + income.other_sources
    )


def calculate_slab_tax(taxable_income: float, slabs: List[Dict[str, Any]]) -> float:
    """Calculate base income tax from progressive slab tiers."""
    if taxable_income <= 0:
        return 0.0

    total_tax = 0.0
    for slab in slabs:
        slab_min = slab["min"]
        slab_max = slab.get("max")
        rate = slab["rate"]

        if taxable_income > slab_min:
            if slab_max is not None:
                taxable_in_slab = min(taxable_income, slab_max) - slab_min
            else:
                taxable_in_slab = taxable_income - slab_min
            
            tax_in_slab = taxable_in_slab * rate
            total_tax += tax_in_slab

    return round(total_tax, 2)


def apply_rebate_87a(
    base_tax: float,
    taxable_income: float,
    rebate_config: Dict[str, Any],
    is_new_regime: bool = True,
) -> Tuple[float, float]:
    """
    Calculate Section 87A rebate and apply marginal relief where applicable.
    Returns: (tax_after_rebate, rebate_amount)
    """
    if base_tax <= 0 or taxable_income <= 0:
        return 0.0, 0.0

    threshold = rebate_config.get("threshold_income", 700000.0 if is_new_regime else 500000.0)
    max_rebate = rebate_config.get("max_rebate", 25000.0 if is_new_regime else 12500.0)

    # Full rebate if taxable income is at or below threshold
    if taxable_income <= threshold:
        rebate = min(base_tax, max_rebate)
        return 0.0, rebate

    # Marginal relief under New Regime for income slightly above threshold
    if is_new_regime and rebate_config.get("marginal_relief", True):
        excess_income = taxable_income - threshold
        if base_tax > excess_income:
            marginal_relief = base_tax - excess_income
            tax_after_rebate = excess_income
            return round(tax_after_rebate, 2), round(marginal_relief, 2)

    return round(base_tax, 2), 0.0


def calculate_surcharge(
    tax_after_rebate: float,
    taxable_income: float,
    surcharge_slabs: List[Dict[str, Any]],
) -> Tuple[float, float]:
    """
    Calculate surcharge on tax after rebate.
    Returns: (surcharge_amount, surcharge_rate)
    """
    if tax_after_rebate <= 0 or taxable_income <= 5000000:
        return 0.0, 0.0

    applicable_rate = 0.0
    for slab in surcharge_slabs:
        slab_min = slab["min"]
        slab_max = slab.get("max")
        if taxable_income > slab_min:
            if slab_max is None or taxable_income <= slab_max:
                applicable_rate = slab["rate"]
                break

    surcharge_amount = round(tax_after_rebate * applicable_rate, 2)
    return surcharge_amount, applicable_rate


def evaluate_deductions(
    profile: TaxProfile,
    regime: TaxRegime,
    rules_config: Dict[str, Any],
) -> Tuple[float, List[RuleResult]]:
    """
    Evaluate all applicable deductions for the given regime and generate RuleResults.
    Returns: (total_deductions_amount, list_of_rule_results)
    """
    regime_key = regime.value
    regime_cfg = rules_config.get("regimes", {}).get(regime_key, {})
    results: List[RuleResult] = []
    total_deduction = 0.0

    income = profile.income
    deductions = profile.deductions
    salary_income = income.salary

    # 1. Standard Deduction
    std_ded_cfg = regime_cfg.get("standard_deduction", {})
    std_ded_max = std_ded_cfg.get("salaried", 75000.0 if regime == TaxRegime.NEW else 50000.0)
    std_ded_eligible = min(salary_income, std_ded_max) if salary_income > 0 else 0.0
    
    results.append(
        RuleResult(
            rule_id="sec_standard_deduction",
            rule_name="Standard Deduction (Salary)",
            category=RuleCategory.DEDUCTION,
            is_applicable=salary_income > 0,
            is_eligible=salary_income > 0,
            max_limit=std_ded_max,
            claimed_amount=deductions.standard_deduction or std_ded_max,
            eligible_amount=std_ded_eligible,
            potential_savings=round(std_ded_eligible * 0.20, 2),  # Estimated average bracket
            tax_regime=regime,
            legal_section="Section 16(ia)",
            description="Flat standard deduction allowed for salaried individuals and pensioners.",
            recommendations=[
                f"Eligible for standard deduction of ₹{std_ded_eligible:,.2f} against salary income."
            ] if std_ded_eligible > 0 else ["Standard deduction applies only to salaried income."]
        )
    )
    total_deduction += std_ded_eligible

    # New regime specific evaluation
    if regime == TaxRegime.NEW:
        # Employer NPS (80CCD(2)) is allowed in New Regime
        if deductions.section_80ccd_2 > 0:
            nps_limit = salary_income * 0.14  # Up to 14% of basic
            eligible_nps = min(deductions.section_80ccd_2, nps_limit)
            total_deduction += eligible_nps
            results.append(
                RuleResult(
                    rule_id="sec_80ccd_2",
                    rule_name="Employer NPS Contribution",
                    category=RuleCategory.DEDUCTION,
                    is_applicable=True,
                    is_eligible=True,
                    max_limit=nps_limit,
                    claimed_amount=deductions.section_80ccd_2,
                    eligible_amount=eligible_nps,
                    potential_savings=round(eligible_nps * 0.20, 2),
                    tax_regime=regime,
                    legal_section="Section 80CCD(2)",
                    description="Employer contribution to National Pension Scheme (up to 14% of salary).",
                    recommendations=[f"Claimed ₹{eligible_nps:,.2f} under Section 80CCD(2)."]
                )
            )
        return total_deduction, results

    # Old regime deductions evaluation
    limits = regime_cfg.get("deduction_limits", {})

    # Section 80C
    c_limit = limits.get("section_80c", {}).get("max_limit", 150000.0)
    c_eligible = min(deductions.section_80c, c_limit)
    total_deduction += c_eligible
    c_headroom = max(0.0, c_limit - deductions.section_80c)
    results.append(
        RuleResult(
            rule_id="sec_80c",
            rule_name="Section 80C Deductions",
            category=RuleCategory.DEDUCTION,
            is_applicable=True,
            is_eligible=True,
            max_limit=c_limit,
            claimed_amount=deductions.section_80c,
            eligible_amount=c_eligible,
            potential_savings=round(c_eligible * 0.30, 2),
            tax_regime=regime,
            legal_section="Section 80C",
            description="Deduction for investments in EPF, PPF, ELSS, Life Insurance, SSY, etc.",
            recommendations=[
                f"You have ₹{c_headroom:,.2f} remaining headroom to invest in 80C instruments (ELSS/PPF/NPS)."
            ] if c_headroom > 0 else ["You have fully utilized your Section 80C limit of ₹1,50,000."]
        )
    )

    # Section 80CCD(1B) - NPS Additional
    nps_limit = limits.get("section_80ccd_1b", {}).get("max_limit", 50000.0)
    nps_eligible = min(deductions.section_80ccd_1b, nps_limit)
    total_deduction += nps_eligible
    nps_headroom = max(0.0, nps_limit - deductions.section_80ccd_1b)
    results.append(
        RuleResult(
            rule_id="sec_80ccd_1b",
            rule_name="NPS Self Contribution (Section 80CCD(1B))",
            category=RuleCategory.DEDUCTION,
            is_applicable=True,
            is_eligible=True,
            max_limit=nps_limit,
            claimed_amount=deductions.section_80ccd_1b,
            eligible_amount=nps_eligible,
            potential_savings=round(nps_eligible * 0.30, 2),
            tax_regime=regime,
            legal_section="Section 80CCD(1B)",
            description="Additional voluntary deduction for Tier 1 NPS investments.",
            recommendations=[
                f"You can save up to ₹{nps_headroom * 0.30:,.2f} more by contributing ₹{nps_headroom:,.2f} into NPS Tier-1."
            ] if nps_headroom > 0 else ["Maximum Section 80CCD(1B) benefit claimed."]
        )
    )

    # Section 80D - Health Insurance
    d_cfg = limits.get("section_80d", {})
    self_limit = d_cfg.get("self_family_senior_max", 50000.0) if profile.is_senior_citizen else d_cfg.get("self_family_max", 25000.0)
    d_eligible = min(deductions.section_80d, self_limit + d_cfg.get("parents_senior_max", 50000.0))
    total_deduction += d_eligible
    results.append(
        RuleResult(
            rule_id="sec_80d",
            rule_name="Health Insurance & Medical (Section 80D)",
            category=RuleCategory.DEDUCTION,
            is_applicable=True,
            is_eligible=True,
            max_limit=d_cfg.get("total_max_possible", 100000.0),
            claimed_amount=deductions.section_80d,
            eligible_amount=d_eligible,
            potential_savings=round(d_eligible * 0.30, 2),
            tax_regime=regime,
            legal_section="Section 80D",
            description="Deduction for health insurance premiums for self, family, and parents.",
            recommendations=[
                f"Eligible Section 80D deduction: ₹{d_eligible:,.2f}."
            ]
        )
    )

    # Section 24(b) - Home Loan Interest
    hl_cfg = limits.get("section_24b", {})
    hl_limit = hl_cfg.get("self_occupied_max", 200000.0)
    hl_eligible = min(deductions.section_24b, hl_limit) if deductions.section_24b > 0 else 0.0
    total_deduction += hl_eligible
    if deductions.section_24b > 0:
        results.append(
            RuleResult(
                rule_id="sec_24b",
                rule_name="Home Loan Interest (Section 24(b))",
                category=RuleCategory.DEDUCTION,
                is_applicable=True,
                is_eligible=True,
                max_limit=hl_limit,
                claimed_amount=deductions.section_24b,
                eligible_amount=hl_eligible,
                potential_savings=round(hl_eligible * 0.30, 2),
                tax_regime=regime,
                legal_section="Section 24(b)",
                description="Deduction for interest on housing loan for self-occupied house property.",
                recommendations=[f"Home loan interest deduction eligible: ₹{hl_eligible:,.2f}."]
            )
        )

    # HRA Exemption
    if deductions.hra_exemption > 0:
        total_deduction += deductions.hra_exemption
        results.append(
            RuleResult(
                rule_id="sec_10_13a_hra",
                rule_name="House Rent Allowance (HRA) Exemption",
                category=RuleCategory.EXEMPTION,
                is_applicable=True,
                is_eligible=True,
                claimed_amount=deductions.hra_exemption,
                eligible_amount=deductions.hra_exemption,
                potential_savings=round(deductions.hra_exemption * 0.30, 2),
                tax_regime=regime,
                legal_section="Section 10(13A)",
                description="Exemption on House Rent Allowance paid towards residential accommodation."
            )
        )

    # Section 80TTA / 80TTB
    if profile.is_senior_citizen:
        ttb_limit = limits.get("section_80ttb", {}).get("max_limit", 50000.0)
        ttb_eligible = min(deductions.section_80ttb, ttb_limit)
        total_deduction += ttb_eligible
    else:
        tta_limit = limits.get("section_80tta", {}).get("max_limit", 10000.0)
        tta_eligible = min(deductions.section_80tta, tta_limit)
        total_deduction += tta_eligible

    # Other deductions (80G, 80E, etc.)
    if deductions.section_80g > 0:
        total_deduction += deductions.section_80g
    if deductions.section_80e > 0:
        total_deduction += deductions.section_80e

    return total_deduction, results


def calculate_tax_for_regime(
    profile: TaxProfile,
    regime: TaxRegime,
    version_or_fy: Optional[str] = None,
) -> Dict[str, Any]:
    """Calculate complete tax liability breakdown for a specified regime."""
    rules_cfg = load_rules_config(version_or_fy or profile.financial_year)
    regime_key = regime.value
    regime_cfg = rules_cfg.get("regimes", {}).get(regime_key, {})
    cess_rate = rules_cfg.get("cess_rate", 0.04)

    gross_income = calculate_gross_income(profile.income)
    total_deductions, rule_results = evaluate_deductions(profile, regime, rules_cfg)

    # Net taxable income cannot be negative
    net_taxable_income = max(0.0, gross_income - total_deductions)

    # Resolve tax slabs based on regime & age
    if regime == TaxRegime.OLD:
        slabs_dict = regime_cfg.get("tax_slabs", {})
        if profile.is_super_senior_citizen or (profile.age and profile.age >= 80):
            slabs = slabs_dict.get("super_senior_citizen", slabs_dict.get("general", []))
        elif profile.is_senior_citizen or (profile.age and profile.age >= 60):
            slabs = slabs_dict.get("senior_citizen", slabs_dict.get("general", []))
        else:
            slabs = slabs_dict.get("general", [])
    else:
        slabs = regime_cfg.get("tax_slabs", [])

    base_slab_tax = calculate_slab_tax(net_taxable_income, slabs)

    # Section 87A Rebate
    rebate_cfg = regime_cfg.get("rebate_87a", {})
    tax_after_rebate, rebate_amount = apply_rebate_87a(
        base_slab_tax,
        net_taxable_income,
        rebate_cfg,
        is_new_regime=(regime == TaxRegime.NEW),
    )

    # Surcharge
    surcharge_slabs = regime_cfg.get("surcharge_slabs", [])
    surcharge_amount, surcharge_rate = calculate_surcharge(
        tax_after_rebate,
        net_taxable_income,
        surcharge_slabs,
    )

    # Health & Education Cess (4%)
    tax_plus_surcharge = tax_after_rebate + surcharge_amount
    cess_amount = round(tax_plus_surcharge * cess_rate, 2) if tax_plus_surcharge > 0 else 0.0

    total_tax_liability = round(tax_plus_surcharge + cess_amount, 2)

    return {
        "regime": regime,
        "gross_income": round(gross_income, 2),
        "total_deductions": round(total_deductions, 2),
        "net_taxable_income": round(net_taxable_income, 2),
        "base_slab_tax": round(base_slab_tax, 2),
        "rebate_87a": round(rebate_amount, 2),
        "tax_after_rebate": round(tax_after_rebate, 2),
        "surcharge": round(surcharge_amount, 2),
        "surcharge_rate": surcharge_rate,
        "cess": round(cess_amount, 2),
        "total_tax_liability": total_tax_liability,
        "rule_results": rule_results,
    }


def evaluate_tax_profile(
    profile: TaxProfile,
    version_or_fy: Optional[str] = None,
) -> AnalyzeResponse:
    """
    Compare Old and New Tax Regimes for a tax profile and generate recommendations.
    """
    fy = version_or_fy or profile.financial_year
    old_calc = calculate_tax_for_regime(profile, TaxRegime.OLD, fy)
    new_calc = calculate_tax_for_regime(profile, TaxRegime.NEW, fy)

    old_liability = old_calc["total_tax_liability"]
    new_liability = new_calc["total_tax_liability"]

    if new_liability <= old_liability:
        recommended_regime = TaxRegime.NEW
        savings = round(old_liability - new_liability, 2)
        applied_rules = new_calc["rule_results"]
    else:
        recommended_regime = TaxRegime.OLD
        savings = round(new_liability - old_liability, 2)
        applied_rules = old_calc["rule_results"]

    # Generate actionable optimization tips
    optimization_tips: List[str] = []
    if recommended_regime == TaxRegime.NEW:
        optimization_tips.append(
            f"New Tax Regime saves you ₹{savings:,.2f} compared to the Old Regime."
        )
        optimization_tips.append(
            "Under the New Regime, you get an increased Standard Deduction of ₹75,000 and zero tax on income up to ₹7.75 Lakhs."
        )
        if profile.deductions.section_80ccd_2 == 0:
            optimization_tips.append(
                "Consider opting for Employer NPS contribution under Section 80CCD(2) to further reduce your taxable income in the New Regime."
            )
    else:
        optimization_tips.append(
            f"Old Tax Regime is more beneficial by ₹{savings:,.2f} due to your high deductions/exemptions."
        )
        if profile.deductions.section_80c < 150000:
            rem = 150000 - profile.deductions.section_80c
            optimization_tips.append(
                f"You can claim additional ₹{rem:,.2f} under Section 80C to save more tax."
            )
        if profile.deductions.section_80ccd_1b < 50000:
            rem_nps = 50000 - profile.deductions.section_80ccd_1b
            optimization_tips.append(
                f"Contributing ₹{rem_nps:,.2f} to NPS Tier-1 (Sec 80CCD(1B)) will yield direct additional tax savings."
            )

    # Update profile calculated fields
    updated_profile = profile.model_copy(deep=True)
    best_calc = new_calc if recommended_regime == TaxRegime.NEW else old_calc
    updated_profile.gross_total_income = best_calc["gross_income"]
    updated_profile.total_deductions = best_calc["total_deductions"]
    updated_profile.net_taxable_income = best_calc["net_taxable_income"]
    updated_profile.total_tax_liability = best_calc["total_tax_liability"]
    updated_profile.regime_preference = recommended_regime

    # Set computed standard deduction in profile for downstream exports/checks
    std_ded = 0.0
    for rule in applied_rules:
        if rule.rule_id == "sec_standard_deduction":
            std_ded = rule.eligible_amount
            break
    updated_profile.deductions.standard_deduction = std_ded

    updated_profile.refund_or_due_amount = round(

        best_calc["total_tax_liability"] - (updated_profile.tax_paid_tds + updated_profile.tax_paid_advance + updated_profile.tax_paid_self_assessment),
        2
    )

    return AnalyzeResponse(
        tax_profile=updated_profile,
        recommended_regime=recommended_regime,
        old_regime_liability=old_liability,
        new_regime_liability=new_liability,
        potential_savings=savings,
        applied_rules=applied_rules,
        optimization_tips=optimization_tips,
    )


def simulate_tax_adjustments(
    profile: TaxProfile,
    adjustments: Dict[str, Any],
    target_regime: Optional[TaxRegime] = None,
    version_or_fy: Optional[str] = None,
) -> SimulateResponse:
    """
    Simulate tax liability changes by applying hypothetical income or deduction adjustments.
    """
    fy = version_or_fy or profile.financial_year
    regime = target_regime or profile.regime_preference

    # Baseline calculation
    base_calc = calculate_tax_for_regime(profile, regime, fy)
    original_liability = base_calc["total_tax_liability"]

    # Apply adjustments on a modified profile copy
    adj_profile = profile.model_copy(deep=True)
    
    # Handle income adjustments
    if "income" in adjustments:
        for k, v in adjustments["income"].items():
            if hasattr(adj_profile.income, k):
                setattr(adj_profile.income, k, float(v))
                
    # Handle deduction adjustments
    if "deductions" in adjustments:
        for k, v in adjustments["deductions"].items():
            if hasattr(adj_profile.deductions, k):
                setattr(adj_profile.deductions, k, float(v))

    projected_calc = calculate_tax_for_regime(adj_profile, regime, fy)
    projected_liability = projected_calc["total_tax_liability"]
    net_savings = round(original_liability - projected_liability, 2)

    return SimulateResponse(
        original_liability=original_liability,
        projected_liability=projected_liability,
        net_savings=net_savings,
        rule_breakdown=projected_calc["rule_results"],
    )
 