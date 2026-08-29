"""Router for tax simulation endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.api import SimulateRequest, SimulateResponse
from app.simulator.recalculate import recalculate_scenario

router = APIRouter(prefix="/simulate", tags=["simulate"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "simulate"}


@router.post("", response_model=SimulateResponse)
def simulate_recalculation(request: SimulateRequest):
    """
    Simulate tax liability changes by applying adjustments
    to a baseline tax profile.
    """
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

