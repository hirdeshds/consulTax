"""Integration tests for the OCR document upload endpoint."""

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


def test_ocr_upload_creates_session_if_not_provided(client):
    """Verify that uploading a document without a session_id auto-creates a session."""
    file_content = b"Dummy Form 16 text content."
    file_obj = io.BytesIO(file_content)

    response = client.post(
        "/api/ocr/upload",
        files={"file": ("my_form_16.pdf", file_obj, "application/pdf")},
        data={"document_type": "form_16"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "document" in data
    doc = data["document"]
    assert doc["document_type"] == "form_16"
    assert doc["extracted_fields"]["salary"] == 1200000.0

    # Retrieve and verify that the session was created
    session_id = response.json()["message"].split("session ")[-1].strip(".")
    assert session_store.exists(session_id)
    session = session_store.get_session(session_id)
    assert len(session.documents) == 1
    assert doc["document_id"] in session.documents


def test_ocr_upload_attaches_to_existing_session(client):
    """Verify that uploading a document with a session_id attaches it to the specified session."""
    session_id = "test-ocr-session"
    session_store.create_session(session_id=session_id)

    file_content = b"Salary slip content."
    file_obj = io.BytesIO(file_content)

    response = client.post(
        "/api/ocr/upload",
        files={"file": ("salary_slip.pdf", file_obj, "application/pdf")},
        data={"session_id": session_id, "document_type": "salary_slip"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    doc = data["document"]
    assert doc["document_type"] == "salary_slip"
    assert doc["extracted_fields"]["salary"] == 100000.0

    # Verify session has the document
    session = session_store.get_session(session_id)
    assert len(session.documents) == 1
    assert doc["document_id"] in session.documents


def test_ocr_upload_unsupported_document_type_falls_back(client):
    """Verify other files fall back correctly to standard mock data."""
    file_content = b"Some random file."
    file_obj = io.BytesIO(file_content)

    response = client.post(
        "/api/ocr/upload",
        files={"file": ("random_receipt.png", file_obj, "image/png")},
        data={"document_type": "other"}
    )

    assert response.status_code == 200
    data = response.json()
    doc = data["document"]
    assert doc["document_type"] == "other"
    assert doc["extracted_fields"]["gross_total_income"] == 500000.0
