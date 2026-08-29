"""Utilities for standardizing extracted document field values."""

from __future__ import annotations

import re
from typing import Any, Mapping


def _snake_case(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def _parse_decimal(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return ""
        cleaned = cleaned.replace(",", "")
        cleaned = cleaned.replace("₹", "").replace("$", "")
        cleaned = cleaned.replace("%", "")
        cleaned = cleaned.replace("_", " ")
        cleaned = cleaned.strip()
        if re.fullmatch(r"[-+]?\d+\.?\d*", cleaned):
            return float(cleaned)
        if re.fullmatch(r"[-+]?\d+\.?\d*\s+[a-zA-Z]+", cleaned):
            numeric_match = re.search(r"[-+]?\d+(?:\.\d+)?", cleaned)
            if numeric_match:
                return float(numeric_match.group(0))
    return value


def _normalize_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            return value
        return float(value)
    if isinstance(value, str):
        trimmed = " ".join(value.strip().split())
        if not trimmed:
            return ""
        lowered = trimmed.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        decimal_value = _parse_decimal(trimmed)
        if isinstance(decimal_value, float):
            return decimal_value
        if re.search(r"\s|[-/]|_", trimmed) and len(trimmed) <= 80 and not trimmed.endswith((".", "!", "?")):
            return _snake_case(trimmed)
        return lowered
    if isinstance(value, list):
        return [_normalize_scalar(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_scalar(item) for item in value]
    if isinstance(value, dict):
        return {str(k).strip(): _normalize_scalar(v) for k, v in value.items()}
    return value


def normalize_extracted_fields(raw_fields: Mapping[str, Any]) -> dict[str, Any]:
    """Standardize incoming extraction fields to a consistent normalized key/value form."""

    normalized: dict[str, Any] = {}
    for key, value in raw_fields.items():
        normalized_key = _snake_case(str(key))
        if isinstance(value, list):
            normalized[normalized_key] = [_normalize_scalar(item) for item in value]
            if normalized[normalized_key] and all(isinstance(item, str) for item in normalized[normalized_key]):
                normalized[normalized_key] = [
                    re.sub(r"\s+", "_", item.strip()).strip("_").lower()
                    for item in normalized[normalized_key]
                ]
        elif isinstance(value, dict):
            normalized[normalized_key] = normalize_extracted_fields(value)
        else:
            normalized[normalized_key] = _normalize_scalar(value)
    return normalized
 