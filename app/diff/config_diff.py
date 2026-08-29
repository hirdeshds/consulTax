"""Tax rule configuration comparison and diffing engine."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.rules_engine.loader import load_rules_config, normalize_version


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


class RuleDiffItem(BaseModel):
    """Represents a single granular rule change between two configurations."""
    field_path: str
    category: str
    change_type: ChangeType
    old_value: Any
    new_value: Any
    description: str


class RulesDiffResult(BaseModel):
    """Complete diff report between two tax rule versions."""
    from_version: str
    to_version: str
    from_financial_year: str
    to_financial_year: str
    total_changes: int
    changes: List[RuleDiffItem] = Field(default_factory=list)
    summary_highlights: List[str] = Field(default_factory=list)


def _compare_scalar(
    path: str,
    category: str,
    old_val: Any,
    new_val: Any,
    desc_label: str,
) -> Optional[RuleDiffItem]:
    """Helper to compare scalar attributes."""
    if old_val != new_val:
        return RuleDiffItem(
            field_path=path,
            category=category,
            change_type=ChangeType.MODIFIED if old_val is not None and new_val is not None else (ChangeType.ADDED if old_val is None else ChangeType.REMOVED),
            old_value=old_val,
            new_value=new_val,
            description=f"{desc_label} changed from {old_val} to {new_val}",
        )
    return None


def _compare_slabs(
    regime_name: str,
    old_slabs: List[Dict[str, Any]],
    new_slabs: List[Dict[str, Any]],
    category: str = "tax_slabs",
) -> List[RuleDiffItem]:
    """Compare slab tiers between two versions."""
    diffs: List[RuleDiffItem] = []
    
    if old_slabs != new_slabs:
        diffs.append(
            RuleDiffItem(
                field_path=f"regimes.{regime_name}.{category}",
                category=category,
                change_type=ChangeType.MODIFIED,
                old_value=old_slabs,
                new_value=new_slabs,
                description=f"{regime_name.capitalize()} tax slab tiers updated from {len(old_slabs)} to {len(new_slabs)} brackets.",
            )
        )
    return diffs


def compare_rule_configs(
    from_version: str = "2024-25",
    to_version: str = "2025-26",
) -> RulesDiffResult:
    """
    Compare two tax rule configurations and return a structured diff analysis.
    """
    from_cfg = load_rules_config(from_version)
    to_cfg = load_rules_config(to_version)

    norm_from = normalize_version(from_version)
    norm_to = normalize_version(to_version)

    changes: List[RuleDiffItem] = []
    highlights: List[str] = []

    # 1. Compare Cess Rate
    cess_diff = _compare_scalar(
        "cess_rate",
        "cess",
        from_cfg.get("cess_rate"),
        to_cfg.get("cess_rate"),
        "Health and Education Cess rate",
    )
    if cess_diff:
        changes.append(cess_diff)
        highlights.append(cess_diff.description)

    # 2. Compare Regimes
    from_regimes = from_cfg.get("regimes", {})
    to_regimes = to_cfg.get("regimes", {})

    for regime_key in ["new", "old"]:
        from_r = from_regimes.get(regime_key, {})
        to_r = to_regimes.get(regime_key, {})

        if not from_r and not to_r:
            continue

        # Standard deduction
        from_std = from_r.get("standard_deduction", {})
        to_std = to_r.get("standard_deduction", {})
        for role in ["salaried", "pensioners", "family_pension_max"]:
            if from_std.get(role) != to_std.get(role):
                diff = _compare_scalar(
                    f"regimes.{regime_key}.standard_deduction.{role}",
                    "standard_deduction",
                    from_std.get(role),
                    to_std.get(role),
                    f"{regime_key.upper()} regime Standard Deduction for {role}",
                )
                if diff:
                    changes.append(diff)
                    highlights.append(
                        f"Standard Deduction ({regime_key.capitalize()} - {role}) changed from ₹{from_std.get(role):,.0f} to ₹{to_std.get(role):,.0f}"
                    )

        # Rebate 87A
        from_reb = from_r.get("rebate_87a", {})
        to_reb = to_r.get("rebate_87a", {})
        if from_reb.get("threshold_income") != to_reb.get("threshold_income"):
            diff = _compare_scalar(
                f"regimes.{regime_key}.rebate_87a.threshold_income",
                "rebate_87a",
                from_reb.get("threshold_income"),
                to_reb.get("threshold_income"),
                f"Section 87A rebate income threshold ({regime_key.capitalize()})",
            )
            if diff:
                changes.append(diff)
                highlights.append(
                    f"Section 87A rebate threshold in {regime_key.capitalize()} Regime: ₹{from_reb.get('threshold_income'):,.0f} -> ₹{to_reb.get('threshold_income'):,.0f}"
                )

        if from_reb.get("max_rebate") != to_reb.get("max_rebate"):
            diff = _compare_scalar(
                f"regimes.{regime_key}.rebate_87a.max_rebate",
                "rebate_87a",
                from_reb.get("max_rebate"),
                to_reb.get("max_rebate"),
                f"Section 87A maximum rebate amount ({regime_key.capitalize()})",
            )
            if diff:
                changes.append(diff)

        # Slabs
        if regime_key == "new":
            from_slabs = from_r.get("tax_slabs", [])
            to_slabs = to_r.get("tax_slabs", [])
            slab_diffs = _compare_slabs("new", from_slabs, to_slabs)
            if slab_diffs:
                changes.extend(slab_diffs)
                highlights.append("New Tax Regime slab structures modified.")
        else:
            # Old regime slabs (grouped by age)
            from_slabs_dict = from_r.get("tax_slabs", {})
            to_slabs_dict = to_r.get("tax_slabs", {})
            for age_cat in ["general", "senior_citizen", "super_senior_citizen"]:
                s_from = from_slabs_dict.get(age_cat, [])
                s_to = to_slabs_dict.get(age_cat, [])
                if s_from != s_to:
                    slab_diffs = _compare_slabs(f"old_{age_cat}", s_from, s_to)
                    changes.extend(slab_diffs)
                    highlights.append(f"Old Tax Regime slabs for {age_cat} updated.")

        # Deduction limits (Old Regime)
        from_limits = from_r.get("deduction_limits", {})
        to_limits = to_r.get("deduction_limits", {})
        all_sections = set(from_limits.keys()).union(set(to_limits.keys()))
        for sec in sorted(all_sections):
            f_sec = from_limits.get(sec, {})
            t_sec = to_limits.get(sec, {})
            if f_sec != t_sec:
                changes.append(
                    RuleDiffItem(
                        field_path=f"regimes.old.deduction_limits.{sec}",
                        category="deduction_limits",
                        change_type=ChangeType.MODIFIED if f_sec and t_sec else (ChangeType.ADDED if t_sec else ChangeType.REMOVED),
                        old_value=f_sec,
                        new_value=t_sec,
                        description=f"Deduction rules for {sec} modified between versions.",
                    )
                )

        # Allowed deductions (New Regime)
        from_allowed = from_r.get("allowed_deductions", {})
        to_allowed = to_r.get("allowed_deductions", {})
        for sec in sorted(set(from_allowed.keys()).union(set(to_allowed.keys()))):
            if from_allowed.get(sec) != to_allowed.get(sec):
                changes.append(
                    RuleDiffItem(
                        field_path=f"regimes.new.allowed_deductions.{sec}",
                        category="allowed_deductions",
                        change_type=ChangeType.MODIFIED,
                        old_value=from_allowed.get(sec),
                        new_value=to_allowed.get(sec),
                        description=f"New Regime allowed deduction '{sec}' modified.",
                    )
                )

    if not highlights:
        highlights.append(f"Configurations for {from_version} and {to_version} are functionally aligned with minor policy updates.")

    return RulesDiffResult(
        from_version=norm_from,
        to_version=norm_to,
        from_financial_year=from_cfg.get("financial_year", from_version),
        to_financial_year=to_cfg.get("financial_year", to_version),
        total_changes=len(changes),
        changes=changes,
        summary_highlights=highlights,
    )
