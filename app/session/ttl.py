"""TTL management utilities for user sessions."""

from datetime import datetime, timedelta
from typing import Optional


DEFAULT_TTL_SECONDS = 3600  # 1 hour


def calculate_expiry(ttl_seconds: Optional[int] = None) -> datetime:
    """Calculate expiry datetime from now."""
    seconds = ttl_seconds if ttl_seconds is not None else DEFAULT_TTL_SECONDS
    return datetime.utcnow() + timedelta(seconds=seconds)


def is_expired(expiry_dt: datetime) -> bool:
    """Check whether a given expiry datetime is in the past."""
    return datetime.utcnow() > expiry_dt
 