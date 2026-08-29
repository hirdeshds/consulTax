"""End-to-end integration tests verifying the full tax planning user flow."""

import io
import pytest
from fastapi.testclient import TestClient

from app.main import app
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


def test_end_to_end_user_flow(client):
    """
    Test the full user flow from document upload to PDF download.
    1. Initialize a session.
    2. Upload a Form 16 document (extracted fields: salary, section_80c, etc.).
    3. Analyze the tax assessment (should auto-map documents from session to profile).
    4. Simulate an adjustment (e.g. voluntary NPS contributions).
    5. Download the filing summary PDF.
    """
    # Step 1: Create a session
    session_res = client.post("/api/session", json={})
    assert session_res.status_code == 201
    session_data = session_res.json()
    session_id = session_data["session_id"]
    assert session_id is not None

    # Step 2: Upload a Form 16 document to this session
    file_content = b"Form 16 sample text with salary and investments."
    file_obj = io.BytesIO(file_content)
    
    upload_res = client.post(
        "/api/ocr/upload",
        files={"file": ("form_16_tax_docs.pdf", file_obj, "application/pdf")},
        data={"session_id": session_id, "document_type": "form_16"}
    )
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    assert upload_data["status"] == "success"
    
    # Step 3: Run analysis (request references session_id, no explicit document/profile passed)
    analyze_payload = {
        "sessionId": session_id,
        "include_recommendations": True
    }
    analyze_res = client.post("/api/analyze", json=analyze_payload)
    assert analyze_res.status_code == 200
    analyze_data = analyze_res.json()
    
    # Check that analysis auto-mapped values from the Form 16 document in session
    profile = analyze_data["tax_profile"]
    assert profile["income"]["salary"] == 1200000.0
    assert profile["deductions"]["section_80c"] == 150000.0
    assert profile["deductions"]["section_80d"] == 25000.0
    assert profile["deductions"]["section_24b"] == 50000.0
    
    # Verify standard deduction is applied under new regime (75,000)
    assert profile["deductions"]["standard_deduction"] == 75000.0
    
    # Recommended regime should be computed (typically new is recommended)
    assert analyze_data["recommended_regime"] is not None
    assert "explanation" in profile["metadata"]
    
    # Step 4: Simulate a voluntary NPS contribution of 50,000 under the old regime
    simulate_payload = {
        "tax_profile": profile,
        "adjustments": {
            "deductions": {
                "section_80ccd_1b": 50000.0
            }
        },
        "target_regime": "old"
    }
    simulate_res = client.post("/api/simulate", json=simulate_payload)
    assert simulate_res.status_code == 200
    simulate_data = simulate_res.json()
    assert simulate_data["net_savings"] >= 0.0
    assert simulate_data["projected_liability"] <= simulate_data["original_liability"]
    
    # Step 5: Export the filing summary PDF
    export_res = client.get(f"/api/export/pdf?session_id={session_id}")
    assert export_res.status_code == 200
    assert export_res.headers["content-type"] == "application/pdf"
    assert export_res.headers["content-disposition"].startswith("attachment;")
    
    # Verify PDF signature in binary response content
    pdf_content = export_res.content
    assert pdf_content.startswith(b"%PDF-")
    assert len(pdf_content) > 1000
