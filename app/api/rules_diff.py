"""Rules diff and version comparison API endpoints."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.audit.logger import audit_logger
from app.diff.config_diff import RulesDiffResult, compare_rule_configs
from app.rules_engine.loader import (
    get_available_rule_versions,
    load_rules_config,
)

router = APIRouter(prefix="/rules", tags=["Rules Diff"])


@router.get("/versions", response_model=List[str])
def list_available_versions():
    """List all registered tax rule configuration versions."""
    versions = get_available_rule_versions()
    return versions


@router.get("/config/{version}", response_model=Dict[str, Any])
def get_rule_configuration(version: str):
    """Retrieve full tax rule configuration for a specified financial year / version."""
    try:
        config = load_rules_config(version)
        return config
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/diff", response_model=RulesDiffResult)
def diff_rule_versions(
    from_version: str = Query("2024-25", description="Baseline rule version/FY"),
    to_version: str = Query("2025-26", description="Target rule version/FY to compare against"),
    session_id: Optional[str] = Query(None, description="Optional session ID for audit tracking"),
):
    """
    Compare two tax rule configurations (e.g., FY 2024-25 vs FY 2025-26)
    and return structural differences, slab revisions, and policy highlights.
    """
    try:
        diff_report = compare_rule_configs(from_version=from_version, to_version=to_version)
        
        audit_logger.log_diff_event(
            from_version=from_version,
            to_version=to_version,
            changes_count=diff_report.total_changes,
            session_id=session_id,
        )

        return diff_report
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
