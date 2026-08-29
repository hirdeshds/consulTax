"""Integration tests verifying complete frontend-to-backend API contract and connectivity."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_get_sample_documents(client):
    """Verify clean sample documents endpoint for 1-click loading."""
    response = client.get("/api/sample-documents")
    assert response.status_code == 200
    docs = response.json()
    assert len(docs) >= 4
    for d in docs:
        assert "id" in d
        assert "title" in d
        assert "document_type" in d
        assert "text_content" in d
        assert "mapped_profile" in d


def test_get_rules_config(client):
    """Verify rules config endpoint for interactive rules & slabs inspector."""
    response = client.get("/api/rules/config")
    assert response.status_code == 200
    configs = response.json()
    assert "2024-25" in configs
    assert "2025-26" in configs
    assert "new_regime" in configs["2025-26"]
    assert "old_regime" in configs["2025-26"]
    assert len(configs["2025-26"]["new_regime"]["slabs"]) > 0


def test_analyze_from_frontend_profile(client):
    """Verify /api/analyze with web profile payload returns full comparison & 8 schemes."""
    frontend_profile = {
        "name": "Aarav Sharma",
        "financial_year": "2025-26",
        "age": 32,
        "is_resident": True,
        "residential_location": "metro",
        "employment_income": 1885000,
        "basic_salary": 900000,
        "hra_received": 180000,
        "annual_rent_paid": 240000,
        "provident_fund": 90000,
        "elss_investment": 60000,
        "life_insurance_premium": 35000,
        "nps_tier1_80ccd": 50000,
        "savings_interest": 12000,
        "health_insurance_self_family": 25000,
        "tax_paid": 145000,
        "regime": "new",
    }

    response = client.post("/api/analyze", json={"profile": frontend_profile})
    assert response.status_code == 200
    data = response.json()

    # Assert frontend expected structure
    assert "session_id" in data
    assert "explanation" in data
    assert "result" in data
    assert "comparison" in data
    assert "new" in data["comparison"]
    assert "old" in data["comparison"]
    assert "recommended_regime" in data["comparison"]
    assert "estimated_savings" in data["comparison"]
    assert "recommendations" in data

    # Assert 8 schemes are returned with trigger rules
    schemes = data["comparison"]["new"]["schemes"]
    assert len(schemes) == 8
    scheme_ids = [s["scheme_id"] for s in schemes]
    assert "80c" in scheme_ids
    assert "80ccd_1b" in scheme_ids
    assert "80d" in scheme_ids
    assert "24b" in scheme_ids
    assert "80e" in scheme_ids


def test_qa_endpoint_with_question(client, monkeypatch):
    """Verify /api/qa handles question payload from web UI."""
    monkeypatch.setattr(
        "app.api.qa.generate_answer",
        lambda *args, **kwargs: "You can claim up to ₹1.5L under Section 80C."
    )

    response = client.post("/api/qa", json={"question": "What is the 80C limit?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "reply" in data
    assert "Section 80C" in data["answer"]


def test_parse_sample_document_text(client):
    """Verify /api/document/parse-text extracts structured fields from text."""
    sample_text = """
    Form 16
    Gross Salary as per sec 17(1): Rs. 18,85,000
    Section 80C: Rs. 1,50,000
    TDS Deducted: Rs. 1,45,000
    """
    response = client.post("/api/document/parse-text", json={"text": sample_text})
    assert response.status_code == 200
    data = response.json()
    assert "mapped_profile" in data
    assert data["mapped_profile"]["employment_income"] == 1885000.0
    assert data["mapped_profile"]["tax_paid"] == 145000.0
    assert "key_figures" in data
    assert "explainers" in data


def test_simulate_from_frontend(client):
    """Verify /api/simulate applies what-if adjustments and recalculates savings."""
    base_profile = {
        "name": "Aarav Sharma",
        "financial_year": "2024-25",
        "age": 32,
        "employment_income": 1885000,
        "basic_salary": 900000,
        "provident_fund": 90000,
        "nps_tier1_80ccd": 0,
        "tax_paid": 145000,
    }

    response = client.post("/api/simulate", json={
        "profile": base_profile,
        "changes": {
            "nps_tier1_80ccd": 50000,
            "health_insurance_parents": 50000,
        }
    })
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert "comparison" in data
    assert data["comparison"]["new"]["total_tax"] is not None
