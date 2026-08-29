"""FastAPI dependencies for session retrieval and validation."""

from typing import Optional
from fastapi import Header, HTTPException, status

from app.session.store import SessionData, get_session_store


def get_current_session(
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
) -> SessionData:
    """Dependency that retrieves an existing session or creates a new one if not present."""
    store = get_session_store()
    if x_session_id:
        session = store.get_session(x_session_id)
        if session:
            return session
    
    # Create new session if none provided or expired
    return store.create_session(session_id=x_session_id)


def require_existing_session(
    x_session_id: str = Header(..., alias="X-Session-ID"),
) -> SessionData:
    """Dependency that requires an existing, non-expired session."""
    store = get_session_store()
    session = store.get_session(x_session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{x_session_id}' not found or expired.",
        )
    return session
