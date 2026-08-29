from pathlib import Path

from app.document.normalize import normalize_extracted_fields
from app.ocr.claude_vision_parser import ClaudeVisionParser


def test_normalize_extracted_fields_standardizes_common_inputs():
    raw = {
        "Document Type": " Form 16 ",
        "Gross Total Income": "₹ 1,250,000.50",
        "Salary": " 50000 ",
        "Taxable Income": " 950000.00 ",
        "deductions": [" 80C ", "Standard Deduction"],
        "notes": "  verified  ",
    }

    normalized = normalize_extracted_fields(raw)

    assert normalized["document_type"] == "form_16"
    assert normalized["gross_total_income"] == 1250000.5
    assert normalized["salary"] == 50000.0
    assert normalized["taxable_income"] == 950000.0
    assert normalized["deductions"] == ["80c", "standard_deduction"]
    assert normalized["notes"] == "verified"


def test_claude_vision_parser_builds_document_data(monkeypatch):
    class FakeMessage:
        def __init__(self, text):
            self.text = text

    class FakeResponse:
        content = [FakeMessage('{"document_id":"doc-1","document_type":"form_16","filename":"form16.pdf","raw_text":"hello","extracted_fields":{"salary":50000},"confidence_scores":{"salary":0.92},"is_validated":true,"validation_errors":[],"metadata":{"source":"claude"}}')]

    class FakeClient:
        class messages:
            @staticmethod
            def create(**kwargs):
                return FakeResponse()

    parser = ClaudeVisionParser(api_key="test-key")
    parser.client = FakeClient()

    document = parser.parse_document(
        file_path=Path("sample.pdf"),
        mime_type="application/pdf",
        document_type="form_16",
    )

    assert document.document_id == "doc-1"
    assert document.document_type.value == "form_16"
    assert document.extracted_fields["salary"] == 50000.0
    assert document.metadata["source"] == "claude"
