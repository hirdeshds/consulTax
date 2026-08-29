"""Router for tax simulation endpoints."""

import uuid
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status

from app.schemas.api import SimulateRequest, SimulateResponse
from app.schemas.domain import TaxProfile, TaxRegime
from app.services.unified_tax_service import (
    build_recommendations,
    calculate_single_regime,
    evaluate_8_schemes,
    generate_llm_explanation_sync,
    profile_dict_to_tax_profile,
)
from app.simulator.recalculate import recalculate_scenario

router = APIRouter(prefix="/simulate", tags=["simulate"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "simulate"}


@router.post("", response_model=SimulateResponse)
def simulate_recalculation(request: SimulateRequest):
    """
    Simulate tax liability changes by applying adjustments or what-if changes
    to a baseline tax profile.
    """
    # 1. Frontend what-if simulation
    if request.profile or request.changes is not None:
        try:
            profile_dict = dict(request.profile or {})
            if request.changes:
                profile_dict.update(request.changes)

            profile = profile_dict_to_tax_profile(profile_dict)
            session_id = request.session_id or str(uuid.uuid4())

            single_new = calculate_single_regime(profile, TaxRegime.NEW, profile_dict)
            single_old = calculate_single_regime(profile, TaxRegime.OLD, profile_dict)
            schemes_8 = evaluate_8_schemes(profile, profile_dict)

            new_tax = single_new["total_tax"]
            old_tax = single_old["total_tax"]
            savings = abs(old_tax - new_tax)
            rec_regime = "new" if new_tax <= old_tax else "old"

            if rec_regime == "new":
                rec_reason = (
                    f"The New Tax Regime results in ₹{savings:,.0f} lower tax liability (₹{new_tax:,.0f} vs ₹{old_tax:,.0f}) "
                    f"with simulated changes applied."
                )
            else:
                rec_reason = (
                    f"The Old Tax Regime results in ₹{savings:,.0f} lower tax liability (₹{old_tax:,.0f} vs ₹{new_tax:,.0f}) "
                    f"with total deductions of ₹{single_old['deductions_claimed']:,.0f}."
                )

            recommendations = build_recommendations(schemes_8, savings)
            single_new["schemes"] = schemes_8
            single_old["schemes"] = schemes_8
            active_result = single_new if rec_regime == "new" else single_old

            explanation_text = generate_llm_explanation_sync(profile, single_new, single_old, rec_regime, savings)

            return SimulateResponse(
                original_liability=old_tax if rec_regime == "new" else new_tax,
                projected_liability=new_tax if rec_regime == "new" else old_tax,
                net_savings=savings,
                rule_breakdown=[],
                session_id=session_id,
                profile=profile_dict,
                explanation=explanation_text,
                warnings=[],
                result=active_result,
                comparison={
                    "new": single_new,
                    "old": single_old,
                    "recommended_regime": rec_regime,
                    "estimated_savings": savings,
                    "reason": rec_reason,
                },
                recommendations=recommendations,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Simulation failed: {str(e)}"
            )

    # 2. Existing API client / pytest test contract
    if request.tax_profile:
        try:
            comparison = recalculate_scenario(
                base_profile=request.tax_profile,
                overrides=request.adjustments,
                target_regime=request.target_regime
            )
            return SimulateResponse(
                original_liability=comparison.baseline.total_tax_liability,
                projected_liability=comparison.projected.total_tax_liability,
                net_savings=comparison.delta.tax_saved,
                rule_breakdown=comparison.rule_breakdown
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Simulation failed: {str(e)}"
            )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Missing profile or tax_profile for simulation."
    )
 