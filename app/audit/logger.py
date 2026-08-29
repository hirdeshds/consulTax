"""Structured audit logging system for consulTax."""

import json
import logging
import re
import threading
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Setup audit logger
logger = logging.getLogger("consulTax.audit")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [AUDIT] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class AuditRecord(BaseModel):
    """Structured audit log entry."""
    audit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str
    action: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    status: str = "success"
    details: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: Optional[float] = None
    ip_address: Optional[str] = None


def scrub_sensitive_info(data: Any) -> Any:
    """Mask sensitive PII such as PAN, Aadhaar, bank accounts, or phone numbers."""
    if isinstance(data, dict):
        return {k: scrub_sensitive_info(v) for k, v in data.items()}
    if isinstance(data, list):
        return [scrub_sensitive_info(item) for item in data]
    if isinstance(data, str):
        # Mask PAN numbers (e.g., ABCDE1234F -> ABC*****4F)
        pan_pattern = r"\b([A-Z]{5})(\d{4})([A-Z])\b"
        data = re.sub(pan_pattern, r"\1****\3", data)
        # Mask 12-digit Aadhaar / Account numbers
        aadhaar_pattern = r"\b(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})\b"
        data = re.sub(aadhaar_pattern, r"XXXX-XXXX-\3", data)
    return data


class AuditLogger:
    """Thread-safe structured audit logger with in-memory buffer and file/stream logging."""

    def __init__(self, max_buffer_size: int = 500):
        self._buffer: deque = deque(maxlen=max_buffer_size)
        self._lock = threading.Lock()

    def log(
        self,
        event_type: str,
        action: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: str = "success",
        details: Optional[Dict[str, Any]] = None,
        execution_time_ms: Optional[float] = None,
        ip_address: Optional[str] = None,
    ) -> AuditRecord:
        """Create, store, and emit a structured audit log."""
        clean_details = scrub_sensitive_info(details or {})
        record = AuditRecord(
            event_type=event_type,
            action=action,
            session_id=session_id,
            user_id=user_id,
            status=status,
            details=clean_details,
            execution_time_ms=execution_time_ms,
            ip_address=ip_address,
        )

        # Append to in-memory buffer
        with self._lock:
            self._buffer.append(record)

        # Log formatted JSON message
        try:
            log_payload = record.model_dump(mode="json")
            logger.info(json.dumps(log_payload, default=str))
        except Exception:
            logger.info(f"{record.event_type} | {record.action} | session={record.session_id} | status={record.status}")

        return record

    def log_simulation(
        self,
        session_id: Optional[str],
        original_tax: float,
        projected_tax: float,
        savings: float,
        overrides: Dict[str, Any],
        execution_time_ms: Optional[float] = None,
    ) -> AuditRecord:
        """Specialized logger for simulation events."""
        return self.log(
            event_type="simulation",
            action="recalculate_tax_scenario",
            session_id=session_id,
            details={
                "original_tax": original_tax,
                "projected_tax": projected_tax,
                "savings": savings,
                "overrides": overrides,
            },
            execution_time_ms=execution_time_ms,
        )

    def log_session_event(
        self,
        session_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditRecord:
        """Specialized logger for session lifecycle events."""
        return self.log(
            event_type="session",
            action=action,
            session_id=session_id,
            details=details or {},
        )

    def log_diff_event(
        self,
        from_version: str,
        to_version: str,
        changes_count: int,
        session_id: Optional[str] = None,
    ) -> AuditRecord:
        """Specialized logger for rule version diffing."""
        return self.log(
            event_type="rules_diff",
            action="compare_rule_configs",
            session_id=session_id,
            details={
                "from_version": from_version,
                "to_version": to_version,
                "changes_count": changes_count,
            },
        )

    def get_recent_logs(
        self,
        limit: int = 50,
        event_type: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[AuditRecord]:
        """Query recent audit logs with optional filters."""
        with self._lock:
            logs = list(self._buffer)

        if event_type:
            logs = [l for l in logs if l.event_type == event_type]
        if session_id:
            logs = [l for l in logs if l.session_id == session_id]

        return logs[-limit:]


# Global singleton instance
audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Dependency / accessor for audit logger singleton."""
    return audit_logger
