"""In-memory thread-safe session store with TTL support for user tax sessions."""

import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.api import ChatMessage
from app.schemas.domain import DocumentData, TaxProfile


DEFAULT_SESSION_TTL_SECONDS = 3600  # 1 hour


class SessionData(BaseModel):
    """Session representation containing user state, tax profile, and history."""
    session_id: str
    tax_profile: Optional[TaxProfile] = None
    documents: Dict[str, DocumentData] = Field(default_factory=dict)
    chat_history: List[ChatMessage] = Field(default_factory=list)
    simulation_history: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(seconds=DEFAULT_SESSION_TTL_SECONDS))

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def touch(self, ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS) -> None:
        self.updated_at = datetime.utcnow()
        self.expires_at = self.updated_at + timedelta(seconds=ttl_seconds)


class SessionStore:
    """Thread-safe in-memory cache and session store."""

    def __init__(self, default_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS):
        self._store: Dict[str, SessionData] = {}
        self._lock = threading.RLock()
        self._default_ttl_seconds = default_ttl_seconds

    def create_session(
        self,
        session_id: Optional[str] = None,
        tax_profile: Optional[TaxProfile] = None,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionData:
        """Create a new user session."""
        with self._lock:
            sid = session_id or str(uuid.uuid4())
            ttl = ttl_seconds or self._default_ttl_seconds
            now = datetime.utcnow()
            session = SessionData(
                session_id=sid,
                tax_profile=tax_profile,
                metadata=metadata or {},
                created_at=now,
                updated_at=now,
                expires_at=now + timedelta(seconds=ttl),
            )
            self._store[sid] = session
            return session.model_copy(deep=True)

    def get_session(self, session_id: str, auto_touch: bool = True) -> Optional[SessionData]:
        """Retrieve a session by ID, automatically removing it if expired."""
        with self._lock:
            session = self._store.get(session_id)
            if not session:
                return None

            if session.is_expired():
                del self._store[session_id]
                return None

            if auto_touch:
                session.touch(self._default_ttl_seconds)

            return session.model_copy(deep=True)

    def set_tax_profile(self, session_id: str, tax_profile: TaxProfile) -> Optional[SessionData]:
        """Set or update the TaxProfile in a session."""
        with self._lock:
            session = self._store.get(session_id)
            if not session:
                # Auto-create session if not exists
                session = self.create_session(session_id=session_id, tax_profile=tax_profile)
                return session

            session.tax_profile = tax_profile
            session.touch(self._default_ttl_seconds)
            return session.model_copy(deep=True)

    def add_document(self, session_id: str, document: DocumentData) -> Optional[SessionData]:
        """Add or update an uploaded document in the session."""
        with self._lock:
            session = self._store.get(session_id)
            if not session:
                session = self.create_session(session_id=session_id)

            session.documents[document.document_id] = document
            session.touch(self._default_ttl_seconds)
            return session.model_copy(deep=True)

    def get_document(self, session_id: str, document_id: str) -> Optional[DocumentData]:
        """Retrieve a specific document from a session."""
        with self._lock:
            session = self.get_session(session_id, auto_touch=False)
            if not session:
                return None
            return session.documents.get(document_id)

    def add_chat_message(self, session_id: str, message: ChatMessage) -> Optional[SessionData]:
        """Append a message to the session's chat history."""
        with self._lock:
            session = self._store.get(session_id)
            if not session:
                session = self.create_session(session_id=session_id)

            session.chat_history.append(message)
            session.touch(self._default_ttl_seconds)
            return session.model_copy(deep=True)

    def add_simulation_result(self, session_id: str, simulation_data: Dict[str, Any]) -> Optional[SessionData]:
        """Store a simulation result in session history."""
        with self._lock:
            session = self._store.get(session_id)
            if not session:
                session = self.create_session(session_id=session_id)

            session.simulation_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "data": simulation_data,
            })
            session.touch(self._default_ttl_seconds)
            return session.model_copy(deep=True)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]
                return True
            return False

    def exists(self, session_id: str) -> bool:
        """Check if a valid active session exists."""
        with self._lock:
            session = self._store.get(session_id)
            if not session:
                return False
            if session.is_expired():
                del self._store[session_id]
                return False
            return True

    def cleanup_expired(self) -> int:
        """Clean up all expired sessions from memory."""
        with self._lock:
            expired_keys = [
                sid for sid, sess in self._store.items() if sess.is_expired()
            ]
            for sid in expired_keys:
                del self._store[sid]
            return len(expired_keys)

    def clear(self) -> None:
        """Clear all sessions."""
        with self._lock:
            self._store.clear()

    def count(self) -> int:
        """Return number of currently stored active sessions."""
        with self._lock:
            self.cleanup_expired()
            return len(self._store)


# Global singleton instance
session_store = SessionStore()


def get_session_store() -> SessionStore:
    """Dependency / accessor for the global session store."""
    return session_store
