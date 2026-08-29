"""Router for session management endpoints."""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.schemas.domain import TaxProfile
from app.session import get_session_store, SessionStore
from app.session.store import SessionData

router = APIRouter(prefix="/session", tags=["session"])


class CreateSessionRequest(BaseModel):
    session_id: Optional[str] = None
    tax_profile: Optional[TaxProfile] = None
    metadata: Optional[Dict[str, Any]] = None


@router.get("/health")
def health():
    return {"status": "ok", "service": "session"}


@router.post("", response_model=SessionData, status_code=status.HTTP_201_CREATED)
def create_session(
    request: Optional[CreateSessionRequest] = None,
    session_store: SessionStore = Depends(get_session_store)
):
    """Create a new user tax session."""
    request = request or CreateSessionRequest()
    try:
        session = session_store.create_session(
            session_id=request.session_id,
            tax_profile=request.tax_profile,
            metadata=request.metadata
        )
        return session
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


@router.get("/{session_id}", response_model=SessionData)
def get_session(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store)
):
    """Retrieve an active session by ID."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found or has expired."
        )
    return session


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store)
):
    """Close and delete a session."""
    deleted = session_store.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found or could not be deleted."
        )
    return {"status": "success", "message": f"Session {session_id} successfully closed."}

