"""Session management API endpoints."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, Field

from app.audit.logger import audit_logger
from app.schemas.domain import DocumentData, TaxProfile
from app.session.store import SessionData, get_session_store

router = APIRouter(prefix="/session", tags=["Session"])


class CreateSessionRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="Optional custom session ID")
    tax_profile: Optional[TaxProfile] = None
    ttl_seconds: Optional[int] = Field(3600, description="Session TTL in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionSummaryResponse(BaseModel):
    session_id: str
    has_tax_profile: bool
    tax_profile: Optional[TaxProfile] = None
    documents_count: int
    chat_messages_count: int
    simulations_count: int
    created_at: str
    updated_at: str
    expires_at: str
    metadata: Dict[str, Any]


@router.post("", response_model=SessionSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_new_session(payload: Optional[CreateSessionRequest] = None):
    """Create a new user session for managing tax state, documents, and chat history."""
    store = get_session_store()
    req = payload or CreateSessionRequest()
    
    session = store.create_session(
        session_id=req.session_id,
        tax_profile=req.tax_profile,
        ttl_seconds=req.ttl_seconds,
        metadata=req.metadata,
    )
    
    audit_logger.log_session_event(
        session_id=session.session_id,
        action="session_created",
        details={"has_initial_profile": req.tax_profile is not None},
    )

    return SessionSummaryResponse(
        session_id=session.session_id,
        has_tax_profile=session.tax_profile is not None,
        tax_profile=session.tax_profile,
        documents_count=len(session.documents),
        chat_messages_count=len(session.chat_history),
        simulations_count=len(session.simulation_history),
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        expires_at=session.expires_at.isoformat(),
        metadata=session.metadata,
    )


@router.get("/{session_id}", response_model=SessionSummaryResponse)
def get_session_details(session_id: str = Path(..., description="Unique Session ID")):
    """Get metadata and current status of an active session."""
    store = get_session_store()
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found or has expired.",
        )

    return SessionSummaryResponse(
        session_id=session.session_id,
        has_tax_profile=session.tax_profile is not None,
        tax_profile=session.tax_profile,
        documents_count=len(session.documents),
        chat_messages_count=len(session.chat_history),
        simulations_count=len(session.simulation_history),
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        expires_at=session.expires_at.isoformat(),
        metadata=session.metadata,
    )


@router.put("/{session_id}/profile", response_model=TaxProfile)
def update_session_profile(
    session_id: str = Path(..., description="Unique Session ID"),
    tax_profile: TaxProfile = ...,
):
    """Update or save the active TaxProfile for this session."""
    store = get_session_store()
    session = store.set_tax_profile(session_id, tax_profile)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    audit_logger.log_session_event(
        session_id=session_id,
        action="profile_updated",
        details={
            "financial_year": tax_profile.financial_year,
            "regime": tax_profile.regime_preference.value,
        },
    )

    return session.tax_profile


@router.get("/{session_id}/profile", response_model=TaxProfile)
def get_session_profile(session_id: str = Path(..., description="Unique Session ID")):
    """Get the current TaxProfile associated with this session."""
    store = get_session_store()
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    if not session.tax_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No tax profile has been set for session '{session_id}'.",
        )
    return session.tax_profile


@router.get("/{session_id}/documents", response_model=List[DocumentData])
def get_session_documents(session_id: str = Path(..., description="Unique Session ID")):
    """List all uploaded and processed documents in this session."""
    store = get_session_store()
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return list(session.documents.values())


@router.delete("/{session_id}", status_code=status.HTTP_200_OK)
def delete_session(session_id: str = Path(..., description="Unique Session ID")):
    """Terminate and clear a session."""
    store = get_session_store()
    deleted = store.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    
    audit_logger.log_session_event(
        session_id=session_id,
        action="session_deleted",
    )
    return {"status": "success", "message": f"Session '{session_id}' successfully deleted."}
