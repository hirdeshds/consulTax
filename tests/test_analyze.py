"""Integration and API tests for the tax analysis endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.domain import TaxProfile, DocumentData
from app.session import session_store


@pytest.fixture
def client():
    """TestClient fixture for interacting with FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_session_store():
    """Ensure session store is clean before/after tests."""
    session_store.clear()
    yield
    session_store.clear()


def test_analyze_endpoint_simple_profile(client, monkeypatch):
    """Test POST /api/analyze with a clean TaxProfile."""
    # Mock LLM explanation call to keep test fast and offline
    monkeypatch.setattr(
        "app.api.analyze.generate_explanation",
        lambda *args, **kwargs: "Mocked AI Explanation: Opt for New Regime to save ₹25,000."
    )

    payload = {
        "tax_profile": {
            "financial_year": "2024-2025",
            "age": 30,
            "income": {
                "salary": 1000000.0
            },
            "deductions": {
                "section_80c": 150000.0
            }
        },
        "include_recommendations": True
    }

    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["recommended_regime"] == "new" # Salaried standard deduction is higher
    assert data["new_regime_liability"] is not None
    assert data["old_regime_liability"] is not None
    assert data["potential_savings"] >= 0.0
    
    # Assert deductions are populated
    assert len(data["deductions"]) > 0
    # Standard deduction should be flagged
    assert any("Standard Deduction" in d["title"] for d in data["deductions"])
    
    # Assert explanation is stored in profile metadata
    profile = data["tax_profile"]
    assert "explanation" in profile["metadata"]
    assert "Mocked AI Explanation" in profile["metadata"]["explanation"]


def test_analyze_endpoint_document_mapping(client, monkeypatch):
    """Test document mapping into profile in POST /api/analyze."""
    monkeypatch.setattr(
        "app.api.analyze.generate_explanation",
        lambda *args, **kwargs: "Mock Explanation"
    )

    payload = {
        "document": {
            "income": {
                "salary": 1200000.0,
                "rental_income": 100000.0
            },
            "investments": {
                "section_80c": 120000.0,
                "health_insurance": 25000.0,
                "home_loan_interest": 50000.0
            }
        },
        "include_recommendations": False
    }

    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    profile = data["tax_profile"]
    
    # Verify mapping succeeded
    assert profile["income"]["salary"] == 1200000.0
    assert profile["income"]["house_property"] == 100000.0
    assert profile["deductions"]["section_80c"] == 120000.0
    assert profile["deductions"]["section_80d"] == 25000.0
    assert profile["deductions"]["section_24b"] == 50000.0


def test_analyze_endpoint_dual_check_warnings(client, monkeypatch):
    """Verify that dual-check validator triggers warning when OCR mismatches computed rules."""
    monkeypatch.setattr(
        "app.api.analyze.generate_explanation",
        lambda *args, **kwargs: "Mock Explanation"
    )

    # 1. Create a session and seed it with a mismatched OCR document
    session_id = "session-dual-check-1"
    ocr_doc = DocumentData(
        document_id="doc-ocr-1",
        extracted_fields={
            "gross_total_income": 1500000.0  # Mismatch: compute will have 1,000,000
        }
    )
    session_store.create_session(session_id=session_id)
    session_store.add_document(session_id, ocr_doc)

    payload = {
        "sessionId": session_id,
        "tax_profile": {
            "financial_year": "2024-2025",
            "income": {
                "salary": 1000000.0
            }
        },
        "include_recommendations": False
    }

    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    # Check that mismatch warning was added
    assert len(data["warnings"]) > 0
    assert any("Gross Total Income mismatch" in w for w in data["warnings"])
