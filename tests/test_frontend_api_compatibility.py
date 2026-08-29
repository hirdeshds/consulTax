"""Tests for frontend API contract compatibility."""

import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)



def test_frontend_analyze_flat_profile_contract():
    """Verify that frontend flat profile payload is parsed and returns all expected keys."""
    payload = {
        "profile": {
            "name": "Aarav Sharma",
            "financial_year": "2024-25",
            "age": 32,
            "is_resident": True,
            "residential_location": "metro",
            "dependent_parents": False,
            "parent_is_senior": False,
            "children_count": 0,
            "employment_income": 1200000,
            "business_revenue": 0,
            "business_expenses": 0,
            "other_income": 30000,
            "rental_income": 0,
            "dividend_income": 0,
            "capital_gains": 0,
            "basic_salary": 600000,
            "hra_received": 120000,
            "annual_rent_paid": 180000,
            "provident_fund": 50000,
            "elss_investment": 50000,
            "life_insurance_premium": 25000,
            "children_tuition_fees": 0,
            "health_insurance_self_family": 25000,
            "health_insurance_parents": 25000,
            "parent_medical_spend": 0,
            "home_loan_principal": 0,
            "home_loan_interest": 0,
            "education_loan_interest": 0,
            "eligible_medical_treatment": 0,
            "charity_donations": 10000,
            "tax_paid": 20000,
            "regime": "new",
        }
    }

    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Verify keys required by frontend
    assert "session_id" in data
    assert "explanation" in data
    assert "warnings" in data
    assert "result" in data
    assert "comparison" in data
    assert "recommendations" in data

    # Verify result structure
    res = data["result"]
    assert res["gross_income"] == 1230000.0
    assert "taxable_income" in res
    assert "total_tax" in res
    assert "standard_deduction" in res
    assert "deduction_breakdown" in res
    assert "trace" in res
    assert len(res["trace"]) > 0

    # Verify comparison structure
    comp = data["comparison"]
    assert "new" in comp
    assert "old" in comp
    assert "recommended_regime" in comp
    assert "estimated_savings" in comp
    assert "reason" in comp

    # Verify recommendations structure
    assert isinstance(data["recommendations"], list)
    if len(data["recommendations"]) > 0:
        rec = data["recommendations"][0]
        assert "section" in rec
        assert "title" in rec
        assert "reason" in rec
        assert "conditions" in rec


def test_frontend_qa_endpoint():
    """Verify that POST /api/qa accepts { session_id, question } and returns answer and reply."""
    # First create an analysis to get a session_id
    payload = {
        "profile": {
            "name": "Priya Patel",
            "financial_year": "2024-25",
            "age": 28,
            "employment_income": 1000000,
            "tax_paid": 10000,
        }
    }
    analyze_resp = client.post("/api/analyze", json=payload)
    assert analyze_resp.status_code == 200
    session_id = analyze_resp.json()["session_id"]

    # Now call QA
    qa_payload = {
        "session_id": session_id,
        "question": "Why is the new regime recommended for me?",
    }
    qa_resp = client.post("/api/qa", json=qa_payload)
    assert qa_resp.status_code == 200
    qa_data = qa_resp.json()

    assert "reply" in qa_data
    assert "answer" in qa_data
    assert len(qa_data["reply"]) > 0
    assert qa_data["answer"] == qa_data["reply"]
    assert "citations" in qa_data


def test_frontend_form16_summary_endpoint():
    """Verify that POST /api/form16/summary accepts PDF upload and returns Form16 summary structure."""
    # Create minimal mock PDF bytes
    mock_pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000102 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"

    files = {"file": ("form16_test.pdf", io.BytesIO(mock_pdf_content), "application/pdf")}
    resp = client.post("/api/form16/summary", files=files)
    assert resp.status_code == 200
    data = resp.json()

    assert "summary" in data
    assert "summary_source" in data
    assert "key_figures" in data
    assert "explainers" in data
    assert "warnings" in data
    assert "retrieved_chunks" in data
    assert len(data["explainers"]) > 0
