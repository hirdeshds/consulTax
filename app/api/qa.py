"""FastAPI router for tax assistant Q&A conversational interface."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from typing import List, Optional

from app.schemas.api import ChatRequest, ChatResponse, ChatMessage, ChatCitation
from app.session import get_session_store, SessionStore
from app.qa.retrieval import get_retriever, TFIDFRetriever
from app.qa.answer_generator import generate_answer, generate_answer_stream
from app.rules_engine.evaluator import evaluate_tax_profile

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("/chat", response_model=ChatResponse)
async def chat_interaction(
    request: ChatRequest,
    session_store: SessionStore = Depends(get_session_store),
    retriever: TFIDFRetriever = Depends(get_retriever)
):
    """
    Handle user conversational queries. Performs RAG retrieval against vetted tax schemes,
    invokes the LLM to generate an answer, updates session history, and returns citations.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty."
        )

    # 1. Retrieve or initialize user session
    session_id = request.session_id
    if not session_id:
        # Create a new session if none is provided
        session = session_store.create_session(tax_profile=request.tax_profile)
        session_id = session.session_id
    else:
        session = session_store.get_session(session_id)
        if not session:
            # Create session if requested ID doesn't exist
            session = session_store.create_session(session_id=session_id, tax_profile=request.tax_profile)
            
    # Update profile in session if provided in request
    if request.tax_profile:
        session = session_store.set_tax_profile(session_id, request.tax_profile)

    # 2. Retrieve relevant context chunks from vetted schemes corpus
    retrieved_chunks = retriever.retrieve(request.message, top_k=3)
    citations = [
        ChatCitation(
            source_title=c.source_title,
            source_section=c.source_section,
            snippet=c.snippet,
            url=c.url
        ) for c in retrieved_chunks
    ]

    # 3. Handle Streaming Response
    if request.stream:
        # Save user message to session history
        user_msg = ChatMessage(role="user", content=request.message)
        session_store.add_chat_message(session_id, user_msg)
        
        # Determine history to pass (history from request or session)
        history = request.history if request.history else session.chat_history[:-1]

        def event_generator():
            full_reply = ""
            try:
                for chunk in generate_answer_stream(
                    query=request.message,
                    retrieved_chunks=retrieved_chunks,
                    history=history,
                    preferred_language=request.preferred_language,
                    tax_profile=session.tax_profile
                ):
                    full_reply += chunk
                    yield chunk
            except Exception as e:
                yield f"\n[Error: {str(e)}]"
            finally:
                if full_reply:
                    assistant_msg = ChatMessage(role="assistant", content=full_reply)
                    session_store.add_chat_message(session_id, assistant_msg)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # 4. Handle standard Non-Streaming Response
    # Determine history to pass
    history = request.history if request.history else session.chat_history

    try:
        reply = generate_answer(
            query=request.message,
            retrieved_chunks=retrieved_chunks,
            history=history,
            preferred_language=request.preferred_language,
            tax_profile=session.tax_profile
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate answer: {str(e)}"
        )

    # Save user and assistant messages in session history
    session_store.add_chat_message(session_id, ChatMessage(role="user", content=request.message))
    session_store.add_chat_message(session_id, ChatMessage(role="assistant", content=reply))

    # 5. Evaluate Rule Results if profile is present
    rule_results = []
    if session.tax_profile:
        try:
            analyze_res = evaluate_tax_profile(session.tax_profile)
            rule_results = analyze_res.applied_rules
        except Exception:
            # Fail silently on rules evaluation to not block chatbot
            pass

    # 6. Generate Context-Aware Suggested Actions
    suggested_actions = ["Compare Old vs New Tax Regime", "Check Section 80C limits"]
    msg_lower = request.message.lower()
    if "80c" in msg_lower:
        suggested_actions = ["Calculate Section 80C remaining headroom", "Eligible Section 80C investments"]
    elif "80d" in msg_lower or "health" in msg_lower or "medical" in msg_lower:
        suggested_actions = ["Deductions for senior citizen parents", "Preventive health check-up deduction"]
    elif "hra" in msg_lower or "rent" in msg_lower:
        suggested_actions = ["Calculate HRA exemption amount", "Deduction under Section 80GG"]
    elif "nps" in msg_lower or "80ccd" in msg_lower:
        suggested_actions = ["Employer NPS contribution rules", "Section 80CCD(1B) voluntary contribution"]

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        citations=citations,
        suggested_actions=suggested_actions,
        rule_results=rule_results,
        created_at=datetime.utcnow(),
        metadata={"preferred_language": request.preferred_language}
    )
