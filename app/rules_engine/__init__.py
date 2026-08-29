"""Rules engine package for loading rules configs and evaluating tax profiles."""

from app.rules_engine.evaluator import (
    apply_rebate_87a,
    calculate_gross_income,
    calculate_slab_tax,
    calculate_surcharge,
    calculate_tax_for_regime,
    evaluate_deductions,
    evaluate_tax_profile,
    simulate_tax_adjustments,
)
from app.rules_engine.loader import (
    clear_rules_cache,
    get_available_rule_versions,
    get_regime_config,
    load_rules_config,
    normalize_version,
)

__all__ = [
    "load_rules_config",
    "get_regime_config",
    "get_available_rule_versions",
    "clear_rules_cache",
    "normalize_version",
    "calculate_gross_income",
    "calculate_slab_tax",
    "apply_rebate_87a",
    "calculate_surcharge",
    "evaluate_deductions",
    "calculate_tax_for_regime",
    "evaluate_tax_profile",
    "simulate_tax_adjustments",
]
