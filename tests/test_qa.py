"""Integration and API tests for the QA/chat endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.domain import TaxProfile, IncomeDetails, DeductionDetails
from app.session import session_store


@pytest.fixture
def client():
    """TestClient fixture for interacting with FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_session_store():
    """Ensure session store is empty before each test."""
    session_store.clear()
    yield
    session_store.clear()


def test_root_endpoint_health(client):
    """Verify that root endpoint is healthy and online."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_chat_interaction_basic(client, monkeypatch):
    """Test standard chat query with mocked LLM generation."""
    mock_reply = "Mocked Response: Under Section 80C, you can invest in PPF or ELSS up to ₹1.5 Lakhs."
    
    # Patch generate_answer to return mock reply
    monkeypatch.setattr(
        "app.api.qa.generate_answer",
        lambda *args, **kwargs: mock_reply
    )

    payload = {
        "message": "Tell me about Section 80C investment options",
        "preferred_language": "en"
    }

    response = client.post("/api/qa/chat", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "session_id" in data
    assert data["reply"] == mock_reply
    assert len(data["citations"]) > 0
    # Citations should be from Section 80C
    assert any("80C" in c["source_title"] for c in data["citations"])
    assert len(data["suggested_actions"]) > 0


def test_chat_interaction_with_session_and_profile(client, monkeypatch):
    """Verify chat remembers session history and incorporates tax profile details."""
    mock_reply = "Based on your salary of ₹12L and age 65, standard deduction of ₹75,000 applies."
    
    monkeypatch.setattr(
        "app.api.qa.generate_answer",
        lambda *args, **kwargs: mock_reply
    )

    profile = {
        "financial_year": "2024-2025",
        "age": 65,
        "is_senior_citizen": True,
        "income": {
            "salary": 1200000.0
        },
        "deductions": {
            "section_80c": 150000.0
        }
    }

    payload = {
        "session_id": "test-session-123",
        "message": "What is my standard deduction?",
        "tax_profile": profile,
        "preferred_language": "en"
    }

    # 1. Send first request
    response = client.post("/api/qa/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "test-session-123"
    assert data["reply"] == mock_reply

    # Verify session is created and holds the state
    assert session_store.exists("test-session-123")
    session = session_store.get_session("test-session-123")
    assert session.tax_profile.age == 65
    assert len(session.chat_history) == 2  # User message and assistant reply

    # 2. Second request without sending profile again (should be retrieved from session)
    payload_second = {
        "session_id": "test-session-123",
        "message": "Confirming my age"
    }
    
    # Custom mock to inspect context/profile passed to generator
    captured_profile = None
    def mock_gen(query, retrieved_chunks, history, preferred_language, tax_profile):
        nonlocal captured_profile
        captured_profile = tax_profile
        return "Age confirmed."

    monkeypatch.setattr("app.api.qa.generate_answer", mock_gen)

    response = client.post("/api/qa/chat", json=payload_second)
    assert response.status_code == 200
    assert captured_profile is not None
    assert captured_profile.age == 65


def test_chat_interaction_streaming(client, monkeypatch):
    """Verify stream mode returns chunks and registers conversation in history."""
    chunks = ["Chunk1 ", "Chunk2 ", "Chunk3"]

    def mock_stream(*args, **kwargs):
        for chunk in chunks:
            yield chunk

    monkeypatch.setattr("app.api.qa.generate_answer_stream", mock_stream)

    payload = {
        "session_id": "stream-session-1",
        "message": "Stream this query",
        "stream": True
    }

    response = client.post("/api/qa/chat", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    
    # Read response body stream
    body = response.text
    assert body == "".join(chunks)

    # Verify history is registered in session
    session = session_store.get_session("stream-session-1")
    assert len(session.chat_history) == 2
    assert session.chat_history[0].role == "user"
    assert session.chat_history[0].content == "Stream this query"
    assert session.chat_history[1].role == "assistant"
    assert session.chat_history[1].content == "".join(chunks)


def test_chat_empty_message_error(client):
    """Test validation errors for empty messages."""
    response = client.post("/api/qa/chat", json={"message": ""})
    assert response.status_code == 400
    assert "Message cannot be empty" in response.json()["detail"]
