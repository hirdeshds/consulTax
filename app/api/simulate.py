"""Simulation API endpoints for tax recalculation and what-if scenario comparisons."""

import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.audit.logger import audit_logger
from app.schemas.domain import TaxProfile, TaxRegime
from app.session.store import get_session_store
from app.simulator.recalculate import (
    ScenarioComparison,
    compare_multiple_scenarios,
    recalculate_scenario,
    simulate_deduction_increments,
)

router = APIRouter(prefix="/simulate", tags=["Simulator"])


class SimulationPayload(BaseModel):
    session_id: Optional[str] = Field(None, description="Optional active session ID to load profile from")
    tax_profile: Optional[TaxProfile] = Field(None, description="Direct tax profile (if not using session)")
    adjustments: Dict[str, Any] = Field(default_factory=dict, description="Income and deduction parameter overrides")
    target_regime: Optional[TaxRegime] = Field(None, description="Regime to evaluate (defaults to profile preference)")
    financial_year: Optional[str] = Field(None, description="Financial year (defaults to profile FY)")
    scenario_name: Optional[str] = Field("Custom Scenario", description="Label for this simulated scenario")


class MultiScenarioPayload(BaseModel):
    session_id: Optional[str] = None
    tax_profile: Optional[TaxProfile] = None
    target_regime: Optional[TaxRegime] = None
    financial_year: Optional[str] = None
    scenarios: List[Dict[str, Any]] = Field(..., min_length=1, description="List of scenario override objects")


class SensitivityPayload(BaseModel):
    session_id: Optional[str] = None
    tax_profile: Optional[TaxProfile] = None
    deduction_field: str = Field("section_80c", description="Deduction field to vary, e.g. section_80c, section_80d, section_80ccd_1b")
    increments: List[float] = Field(
        default=[10000.0, 25000.0, 50000.0, 100000.0, 150000.0],
        description="Incremental contribution steps to simulate",
    )
    target_regime: Optional[TaxRegime] = None
    financial_year: Optional[str] = None


def _resolve_profile(session_id: Optional[str], tax_profile: Optional[TaxProfile]) -> TaxProfile:
    """Helper to resolve profile from payload or session."""
    if tax_profile:
        return tax_profile
    if session_id:
        store = get_session_store()
        session = store.get_session(session_id)
        if session and session.tax_profile:
            return session.tax_profile
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No tax profile found in session '{session_id}'.",
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Either 'tax_profile' or 'session_id' with an existing profile must be provided.",
    )


@router.post("", response_model=ScenarioComparison)
def simulate_single_scenario(payload: SimulationPayload):
    """
    Simulate tax liability changes by applying parameter overrides to a tax profile.
    Returns full baseline vs projected comparisons and savings breakdown.
    """
    start_time = time.perf_counter()
    profile = _resolve_profile(payload.session_id, payload.tax_profile)

    comparison = recalculate_scenario(
        base_profile=profile,
        overrides=payload.adjustments,
        target_regime=payload.target_regime,
        version_or_fy=payload.financial_year,
        scenario_name=payload.scenario_name or "Custom Scenario",
    )

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # Save to session history if session_id present
    if payload.session_id:
        store = get_session_store()
        store.add_simulation_result(payload.session_id, comparison.model_dump(mode="json"))

    # Log audit event
    audit_logger.log_simulation(
        session_id=payload.session_id,
        original_tax=comparison.baseline.total_tax_liability,
        projected_tax=comparison.projected.total_tax_liability,
        savings=comparison.delta.tax_saved,
        overrides=payload.adjustments,
        execution_time_ms=elapsed_ms,
    )

    return comparison


@router.post("/scenarios", response_model=List[ScenarioComparison])
def simulate_multiple_scenarios(payload: MultiScenarioPayload):
    """
    Compare multiple hypothetical tax strategies against baseline profile, ranked by highest tax savings.
    """
    profile = _resolve_profile(payload.session_id, payload.tax_profile)

    results = compare_multiple_scenarios(
        base_profile=profile,
        scenarios=payload.scenarios,
        target_regime=payload.target_regime,
        version_or_fy=payload.financial_year,
    )

    if payload.session_id:
        store = get_session_store()
        store.add_simulation_result(
            payload.session_id,
            {"multi_scenario_count": len(results), "top_scenario": results[0].scenario_name if results else None},
        )

    return results


@router.post("/sensitivity")
def simulate_sensitivity(payload: SensitivityPayload):
    """
    Generate step-by-step ROI curves showing marginal tax savings for incremental deduction investments.
    """
    profile = _resolve_profile(payload.session_id, payload.tax_profile)

    steps = simulate_deduction_increments(
        base_profile=profile,
        deduction_field=payload.deduction_field,
        increments=payload.increments,
        target_regime=payload.target_regime,
        version_or_fy=payload.financial_year,
    )

    return {
        "deduction_field": payload.deduction_field,
        "financial_year": payload.financial_year or profile.financial_year,
        "steps": steps,
    }
