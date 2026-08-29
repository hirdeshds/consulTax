"""FastAPI router for tax assistant Q&A conversational interface."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas.api import ChatCitation, ChatMessage, ChatRequest, ChatResponse
from app.session import get_session_store, SessionStore
from app.qa.retrieval import get_retriever, TFIDFRetriever
from app.qa.answer_generator import generate_answer, generate_answer_stream
from app.rules_engine.evaluator import evaluate_tax_profile

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("", response_model=ChatResponse)
@router.post("/chat", response_model=ChatResponse)
async def chat_interaction(
    request: ChatRequest,
    session_store: SessionStore = Depends(get_session_store),
    retriever: TFIDFRetriever = Depends(get_retriever),
):
    """
    Handle user conversational queries. Performs RAG retrieval against vetted tax schemes,
    invokes the LLM to generate an answer, updates session history, and returns citations.
    Supports both { question, session_id } and { message, session_id } formats.
    """
    query_text = request.question or request.message
    if not query_text or not query_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty.",
        )
    query_text = query_text.strip()

    # 1. Retrieve or initialize user session
    session_id = request.session_id or request.sessionId
    if not session_id:
        session = session_store.create_session(tax_profile=request.tax_profile)
        session_id = session.session_id
    else:
        session = session_store.get_session(session_id)
        if not session:
            session = session_store.create_session(session_id=session_id, tax_profile=request.tax_profile)

    # Update profile in session if provided in request
    if request.tax_profile:
        session = session_store.set_tax_profile(session_id, request.tax_profile)

    # 2. Retrieve relevant context chunks from vetted schemes corpus
    retrieved_chunks = retriever.retrieve(query_text, top_k=3)
    citations = [
        ChatCitation(
            source_title=c.source_title,
            source_section=c.source_section,
            snippet=c.snippet,
            url=c.url,
        )
        for c in retrieved_chunks
    ]

    # 3. Handle Streaming Response
    if request.stream:
        user_msg = ChatMessage(role="user", content=query_text)
        session_store.add_chat_message(session_id, user_msg)
        history = request.history if request.history else session.chat_history[:-1]

        def event_generator():
            full_reply = ""
            try:
                for chunk in generate_answer_stream(
                    query=query_text,
                    retrieved_chunks=retrieved_chunks,
                    history=history,
                    preferred_language=request.preferred_language,
                    tax_profile=session.tax_profile,
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
    history = request.history if request.history else session.chat_history

    try:
        reply = generate_answer(
            query=query_text,
            retrieved_chunks=retrieved_chunks,
            history=history,
            preferred_language=request.preferred_language,
            tax_profile=session.tax_profile,
        )
    except Exception as e:
        # Grounded fallback if LLM endpoint fails
        reply = (
            f"Based on tax rules for your query '{query_text}': "
            + (f"\nRelevant provision: {citations[0].source_title} - {citations[0].snippet}" if citations else "Please refer to Section 80C/80D provisions.")
        )

    # Save user and assistant messages in session history
    session_store.add_chat_message(session_id, ChatMessage(role="user", content=query_text))
    session_store.add_chat_message(session_id, ChatMessage(role="assistant", content=reply))

    # 5. Evaluate Rule Results if profile is present
    rule_results = []
    if session.tax_profile:
        try:
            analyze_res = evaluate_tax_profile(session.tax_profile)
            rule_results = analyze_res.applied_rules
        except Exception:
            pass

    # 6. Generate Context-Aware Suggested Actions
    suggested_actions = ["Compare Old vs New Tax Regime", "Check Section 80C limits"]
    msg_lower = query_text.lower()
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
        answer=reply,
        citations=citations,
        suggested_actions=suggested_actions,
        rule_results=rule_results,
        created_at=datetime.now(timezone.utc),
        metadata={"preferred_language": request.preferred_language},
    )
