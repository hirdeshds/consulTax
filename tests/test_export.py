"""Integration tests for the PDF export endpoint."""

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
    """Ensure session store is clean before/after tests."""
    session_store.clear()
    yield
    session_store.clear()


def test_export_pdf_missing_session_returns_404(client):
    """Verify that exporting PDF for a non-existent session ID yields 404."""
    response = client.get("/api/export/pdf?session_id=non-existent-session-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_export_pdf_empty_session_returns_400(client):
    """Verify that exporting PDF for a session without a tax profile yields 400."""
    session_id = "empty-session"
    session_store.create_session(session_id=session_id)

    response = client.get(f"/api/export/pdf?session_id={session_id}")
    assert response.status_code == 400
    assert "no tax profile" in response.json()["detail"].lower()


def test_export_pdf_success(client):
    """Verify successful ReportLab PDF generation and stream retrieval for a valid session."""
    session_id = "valid-session"
    profile = TaxProfile(
        profile_id="p-export-test",
        gross_total_income=1000000.0,
        total_deductions=150000.0,
        net_taxable_income=850000.0,
        income=IncomeDetails(salary=1000000.0),
        deductions=DeductionDetails(section_80c=150000.0)
    )
    
    # Store profile in session
    session_store.create_session(session_id=session_id, tax_profile=profile)

    response = client.get(f"/api/export/pdf?session_id={session_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment;")
    
    # Verify PDF signature in binary content
    pdf_content = response.content
    assert pdf_content.startswith(b"%PDF-")
    assert len(pdf_content) > 1000
