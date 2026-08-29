"""Simulator package for recalculating tax outcomes and comparing scenarios."""

from app.simulator.recalculate import (
    MetricDelta,
    ScenarioComparison,
    TaxMetricsSummary,
    apply_overrides,
    compare_multiple_scenarios,
    recalculate_scenario,
    simulate_deduction_increments,
)

__all__ = [
    "TaxMetricsSummary",
    "MetricDelta",
    "ScenarioComparison",
    "apply_overrides",
    "recalculate_scenario",
    "compare_multiple_scenarios",
    "simulate_deduction_increments",
]
 