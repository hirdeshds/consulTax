"""Rule configuration loader with caching and version normalization."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

# Base directory for rule configuration files
CONFIG_RULES_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "rules"

# Version alias mapping to canonical filenames
VERSION_ALIASES = {
    "2024-25": "v2024-25.json",
    "2024-2025": "v2024-25.json",
    "v2024-25": "v2024-25.json",
    "v2024-2025": "v2024-25.json",
    "2025-26": "v2025-26.json",
    "2025-2026": "v2025-26.json",
    "v2025-26": "v2025-26.json",
    "v2025-2026": "v2025-26.json",
    "2026-27": "v2026-27.json",
    "2026-2027": "v2026-27.json",
    "v2026-27": "v2026-27.json",
    "v2026-2027": "v2026-27.json",
    "latest": "v2026-27.json",
    "default": "v2024-25.json",
}


def normalize_version(version: Optional[str] = None) -> str:
    """Normalize user or API version string into canonical format."""
    if not version:
        return "2024-25"
    
    clean = version.strip().lower()
    if clean in VERSION_ALIASES:
        return clean
    
    # Handle forms like '2024-25', 'ay2025-26', etc.
    clean = clean.replace("ay", "").replace("fy", "").strip()
    if clean in VERSION_ALIASES:
        return clean
        
    return clean


def resolve_rule_file_path(version_or_fy: Optional[str] = None) -> Path:
    """Resolve file path for a given financial year / version."""
    norm_version = normalize_version(version_or_fy)
    filename = VERSION_ALIASES.get(norm_version, f"v{norm_version}.json" if not norm_version.endswith(".json") else norm_version)
    
    path = CONFIG_RULES_DIR / filename
    if not path.exists():
        # Fallback to scanning config directory
        for f in CONFIG_RULES_DIR.glob("*.json"):
            if norm_version in f.stem:
                return f
        raise FileNotFoundError(f"Tax rule configuration not found for '{version_or_fy}' (looked at {path})")
    
    return path


@lru_cache(maxsize=32)
def load_rules_config(version_or_fy: Optional[str] = "2024-25") -> Dict[str, Any]:
    """Load and parse rule configuration JSON for the given financial year with LRU caching."""
    file_path = resolve_rule_file_path(version_or_fy)
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def get_regime_config(version_or_fy: Optional[str] = "2024-25", regime: str = "new") -> Dict[str, Any]:
    """Get rules configuration for a specific tax regime ('new' or 'old')."""
    rules = load_rules_config(version_or_fy)
    regime_key = regime.lower().strip()
    
    regimes = rules.get("regimes", {})
    if regime_key not in regimes:
        raise ValueError(f"Regime '{regime}' not supported. Available regimes: {list(regimes.keys())}")
    
    return regimes[regime_key]


def get_available_rule_versions() -> List[str]:
    """List all available tax rule version configurations."""
    if not CONFIG_RULES_DIR.exists():
        return []
    
    versions = []
    for p in CONFIG_RULES_DIR.glob("v*.json"):
        # e.g. v2024-25.json -> 2024-25
        stem = p.stem.lstrip("v")
        versions.append(stem)
    return sorted(versions)


def clear_rules_cache() -> None:
    """Clear memory cache for rules configurations."""
    load_rules_config.cache_clear()
