"""Tax simulation and parameter recalculation engine."""

from copy import deepcopy
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.rules_engine.evaluator import (
    calculate_gross_income,
    calculate_tax_for_regime,
    evaluate_tax_profile,
)
from app.schemas.api import SimulateResponse
from app.schemas.domain import (
    DeductionDetails,
    IncomeDetails,
    RuleResult,
    TaxProfile,
    TaxRegime,
)


class TaxMetricsSummary(BaseModel):
    """Summarized tax calculation metrics for comparison."""
    gross_income: float
    total_deductions: float
    net_taxable_income: float
    base_slab_tax: float
    rebate_87a: float
    tax_after_rebate: float
    surcharge: float
    cess: float
    total_tax_liability: float
    effective_tax_rate: float  # (total_tax_liability / gross_income) * 100
    regime: TaxRegime


class MetricDelta(BaseModel):
    """Delta comparison between baseline and projected values."""
    gross_income_delta: float
    deductions_delta: float
    taxable_income_delta: float
    tax_liability_delta: float  # Negative means tax reduced (savings)
    tax_saved: float           # Positive means savings
    tax_savings_percentage: float
    effective_rate_delta: float


class ScenarioComparison(BaseModel):
    """Detailed outcome comparison between baseline and a simulated scenario."""
    scenario_name: str = "Simulated Scenario"
    description: Optional[str] = None
    applied_overrides: Dict[str, Any] = Field(default_factory=dict)
    baseline: TaxMetricsSummary
    projected: TaxMetricsSummary
    delta: MetricDelta
    recommended_regime: TaxRegime
    rule_breakdown: List[RuleResult] = Field(default_factory=list)
    key_takeaways: List[str] = Field(default_factory=list)


def apply_overrides(base_profile: TaxProfile, overrides: Dict[str, Any]) -> TaxProfile:
    """
    Safely clone the base TaxProfile and apply overrides.
    Supports both nested structure and flat key overrides.
    """
    profile = base_profile.model_copy(deep=True)

    # 1. Direct top-level attributes
    for top_key in ["financial_year", "assessment_year", "age", "is_senior_citizen", "is_super_senior_citizen", "residential_status"]:
        if top_key in overrides:
            setattr(profile, top_key, overrides[top_key])

    if "regime_preference" in overrides:
        regime_val = overrides["regime_preference"]
        if isinstance(regime_val, str):
            profile.regime_preference = TaxRegime(regime_val.lower())
        else:
            profile.regime_preference = regime_val

    # 2. Income overrides
    income_overrides = overrides.get("income", {})
    if isinstance(income_overrides, dict):
        for k, v in income_overrides.items():
            if hasattr(profile.income, k):
                setattr(profile.income, k, float(v))

    # 3. Deduction overrides
    deduction_overrides = overrides.get("deductions", {})
    if isinstance(deduction_overrides, dict):
        for k, v in deduction_overrides.items():
            if hasattr(profile.deductions, k):
                setattr(profile.deductions, k, float(v))

    # 4. Handle flat field overrides (e.g. overrides = {"salary": 1500000, "section_80c": 150000})
    for k, v in overrides.items():
        if k in ["income", "deductions"]:
            continue
        if hasattr(profile.income, k):
            setattr(profile.income, k, float(v))
        elif hasattr(profile.deductions, k):
            setattr(profile.deductions, k, float(v))

    return profile


def _extract_metrics_summary(calc_result: Dict[str, Any]) -> TaxMetricsSummary:
    """Helper to convert tax calculation dict into typed TaxMetricsSummary."""
    gross = calc_result["gross_income"]
    tax = calc_result["total_tax_liability"]
    effective_rate = round((tax / gross * 100), 2) if gross > 0 else 0.0

    return TaxMetricsSummary(
        gross_income=calc_result["gross_income"],
        total_deductions=calc_result["total_deductions"],
        net_taxable_income=calc_result["net_taxable_income"],
        base_slab_tax=calc_result["base_slab_tax"],
        rebate_87a=calc_result["rebate_87a"],
        tax_after_rebate=calc_result["tax_after_rebate"],
        surcharge=calc_result["surcharge"],
        cess=calc_result["cess"],
        total_tax_liability=tax,
        effective_tax_rate=effective_rate,
        regime=calc_result["regime"],
    )


def recalculate_scenario(
    base_profile: TaxProfile,
    overrides: Dict[str, Any],
    target_regime: Optional[TaxRegime] = None,
    version_or_fy: Optional[str] = None,
    scenario_name: str = "Simulated Scenario",
    description: Optional[str] = None,
) -> ScenarioComparison:
    """
    Recalculate tax outcomes given an original profile and parametric overrides,
    producing a complete baseline vs projected delta analysis.
    """
    fy = version_or_fy or base_profile.financial_year
    regime = target_regime or base_profile.regime_preference

    # Calculate baseline
    base_calc = calculate_tax_for_regime(base_profile, regime, fy)
    baseline_metrics = _extract_metrics_summary(base_calc)

    # Apply overrides and calculate projected scenario
    simulated_profile = apply_overrides(base_profile, overrides)
    proj_calc = calculate_tax_for_regime(simulated_profile, regime, fy)
    projected_metrics = _extract_metrics_summary(proj_calc)

    # Compute deltas
    gross_delta = round(projected_metrics.gross_income - baseline_metrics.gross_income, 2)
    ded_delta = round(projected_metrics.total_deductions - baseline_metrics.total_deductions, 2)
    taxable_delta = round(projected_metrics.net_taxable_income - baseline_metrics.net_taxable_income, 2)
    tax_delta = round(projected_metrics.total_tax_liability - baseline_metrics.total_tax_liability, 2)
    tax_saved = round(max(0.0, -tax_delta), 2)
    
    savings_pct = (
        round((tax_saved / baseline_metrics.total_tax_liability) * 100, 2)
        if baseline_metrics.total_tax_liability > 0
        else 0.0
    )
    rate_delta = round(projected_metrics.effective_tax_rate - baseline_metrics.effective_tax_rate, 2)

    delta = MetricDelta(
        gross_income_delta=gross_delta,
        deductions_delta=ded_delta,
        taxable_income_delta=taxable_delta,
        tax_liability_delta=tax_delta,
        tax_saved=tax_saved,
        tax_savings_percentage=savings_pct,
        effective_rate_delta=rate_delta,
    )

    # Generate insights and takeaways
    takeaways: List[str] = []
    if tax_saved > 0:
        takeaways.append(
            f"This scenario reduces total tax by ₹{tax_saved:,.2f} ({savings_pct}% lower than baseline)."
        )
    elif tax_delta > 0:
        takeaways.append(
            f"This scenario increases tax liability by ₹{tax_delta:,.2f} due to higher taxable income."
        )
    else:
        takeaways.append("Tax liability remains unchanged under this scenario.")

    if ded_delta > 0:
        takeaways.append(
            f"Increased claimed deductions by ₹{ded_delta:,.2f}, reducing taxable income to ₹{projected_metrics.net_taxable_income:,.2f}."
        )

    if baseline_metrics.effective_tax_rate != projected_metrics.effective_tax_rate:
        takeaways.append(
            f"Effective tax rate shifts from {baseline_metrics.effective_tax_rate}% to {projected_metrics.effective_tax_rate}%."
        )

    return ScenarioComparison(
        scenario_name=scenario_name,
        description=description,
        applied_overrides=overrides,
        baseline=baseline_metrics,
        projected=projected_metrics,
        delta=delta,
        recommended_regime=regime,
        rule_breakdown=proj_calc["rule_results"],
        key_takeaways=takeaways,
    )


def compare_multiple_scenarios(
    base_profile: TaxProfile,
    scenarios: List[Dict[str, Any]],
    target_regime: Optional[TaxRegime] = None,
    version_or_fy: Optional[str] = None,
) -> List[ScenarioComparison]:
    """
    Simulate and compare multiple named scenarios against the baseline profile,
    sorted by highest tax savings.
    """
    results: List[ScenarioComparison] = []
    for idx, sc in enumerate(scenarios, start=1):
        name = sc.get("name", f"Scenario {idx}")
        desc = sc.get("description")
        overrides = sc.get("overrides", sc)
        regime = sc.get("target_regime", target_regime)

        comp = recalculate_scenario(
            base_profile=base_profile,
            overrides=overrides,
            target_regime=regime,
            version_or_fy=version_or_fy,
            scenario_name=name,
            description=desc,
        )
        results.append(comp)

    # Rank by highest tax saved
    results.sort(key=lambda x: x.delta.tax_saved, reverse=True)
    return results


def simulate_deduction_increments(
    base_profile: TaxProfile,
    deduction_field: str,
    increments: List[float],
    target_regime: Optional[TaxRegime] = None,
    version_or_fy: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Generate a sensitivity step curve showing marginal tax savings for incremental deduction investments.
    """
    regime = target_regime or base_profile.regime_preference
    fy = version_or_fy or base_profile.financial_year
    current_val = getattr(base_profile.deductions, deduction_field, 0.0)

    steps: List[Dict[str, Any]] = []
    base_calc = calculate_tax_for_regime(base_profile, regime, fy)
    prev_tax = base_calc["total_tax_liability"]

    for inc in increments:
        new_val = current_val + inc
        scenario = recalculate_scenario(
            base_profile=base_profile,
            overrides={"deductions": {deduction_field: new_val}},
            target_regime=regime,
            version_or_fy=fy,
            scenario_name=f"+₹{inc:,.0f} {deduction_field}",
        )
        proj_tax = scenario.projected.total_tax_liability
        marginal_savings = round(prev_tax - proj_tax, 2)
        total_savings = scenario.delta.tax_saved

        steps.append({
            "additional_investment": inc,
            "total_deduction_value": new_val,
            "projected_tax_liability": proj_tax,
            "marginal_savings": marginal_savings,
            "cumulative_savings": total_savings,
            "roi_percentage": round((total_savings / inc * 100), 2) if inc > 0 else 0.0,
        })
        prev_tax = proj_tax

    return steps
 