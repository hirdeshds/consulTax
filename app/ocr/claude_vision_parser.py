"""OCR parser built on Anthropic Claude vision/document capabilities."""

from __future__ import annotations

import base64
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from app.document.normalize import normalize_extracted_fields
from app.schemas.domain import DocumentData, DocumentType


class ClaudeVisionParser:
    """Send documents to Claude and map the JSON result into a `DocumentData` payload."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None

    def _extract_text_from_response(self, response: Any) -> str:
        if hasattr(response, "content"):
            blocks = response.content
            if isinstance(blocks, list):
                text_parts = []
                for block in blocks:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                if text_parts:
                    return "\n".join(text_parts)
        text = str(response)
        return text

    def _parse_json_payload(self, raw_text: str) -> dict[str, Any]:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, flags=re.DOTALL | re.IGNORECASE)
        if match:
            raw_text = match.group(1)
        cleaned = raw_text.strip()
        if cleaned.startswith("```") and cleaned.endswith("```"):
            cleaned = cleaned[3:-3].strip()
        return json.loads(cleaned)

    def _build_document_request(self, file_path: Path, mime_type: str, document_type: str | DocumentType | None) -> dict[str, Any]:
        if file_path.exists():
            with file_path.open("rb") as handle:
                file_bytes = handle.read()
        else:
            file_bytes = b""

        base64_data = base64.b64encode(file_bytes).decode("utf-8")
        file_label = file_path.name or "document"
        doc_type = document_type.value if isinstance(document_type, DocumentType) else str(document_type or "other")

        prompt = (
            "Extract the document into structured JSON with keys: document_id, document_type, "
            "filename, raw_text, extracted_fields, confidence_scores, is_validated, "
            "validation_errors, metadata. Keep `document_type` one of: form_16, salary_slip, form_26as, ais, "
            "investment_proof, rent_receipt, home_loan_certificate, insurance_premium, donation_receipt, other. "
            "Return valid JSON only."
        )

        return {
            "model": self.model,
            "max_tokens": 2000,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt + f" Target document type hint: {doc_type}"},
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": base64_data,
                            },
                            "title": file_label,
                        },
                    ],
                }
            ],
        }

    def parse_document(
        self,
        file_path: str | Path,
        mime_type: str,
        document_type: str | DocumentType | None = None,
        filename: str | None = None,
    ) -> DocumentData:
        if self.client is None:
            raise ValueError("ANTHROPIC_API_KEY is not configured for ClaudeVisionParser.")

        path = Path(file_path)
        payload = self._build_document_request(path, mime_type, document_type)
        response = self.client.messages.create(**payload)
        raw_text = self._extract_text_from_response(response)
        parsed = self._parse_json_payload(raw_text)

        extracted_fields = normalize_extracted_fields(parsed.get("extracted_fields", {}))
        confidence_scores = {
            str(k): float(v) for k, v in dict(parsed.get("confidence_scores", {})).items()
        }
        document_type_value = parsed.get("document_type") or document_type or "other"
        doc_type_enum = None
        try:
            doc_type_enum = DocumentType(document_type_value)
        except ValueError:
            doc_type_enum = DocumentType.OTHER

        document = DocumentData(
            document_id=str(parsed.get("document_id") or uuid.uuid4()),
            document_type=doc_type_enum,
            filename=parsed.get("filename") or filename or path.name,
            content_type=mime_type,
            raw_text=str(parsed.get("raw_text") or raw_text),
            extracted_fields=extracted_fields,
            confidence_scores=confidence_scores,
            is_validated=bool(parsed.get("is_validated", False)),
            validation_errors=list(parsed.get("validation_errors", []) or []),
            metadata=dict(parsed.get("metadata", {}) or {}),
        )
        return document


def parse_with_claude(
    file_path: str | Path,
    mime_type: str,
    document_type: str | DocumentType | None = None,
    filename: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> DocumentData:
    parser = ClaudeVisionParser(api_key=api_key, model=model)
    return parser.parse_document(file_path=file_path, mime_type=mime_type, document_type=document_type, filename=filename)
