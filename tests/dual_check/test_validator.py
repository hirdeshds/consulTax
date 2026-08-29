"""Unit tests for the dual-check OCR vs computed validator."""

import pytest
from app.schemas.domain import TaxProfile, DocumentData, IncomeDetails, DeductionDetails
from app.dual_check.validator import validate_ocr_vs_computed, DualCheckResult


def test_validator_consistent_match():
    """Verify that validator reports consistent when OCR totals match computed rules engine totals."""
    profile = TaxProfile(
        gross_total_income=1200000.0,
        total_deductions=225000.0,
        net_taxable_income=975000.0,
        income=IncomeDetails(salary=1200000.0),
        deductions=DeductionDetails(standard_deduction=75000.0, section_80c=150000.0)
    )
    
    document = DocumentData(
        document_id="doc-1",
        extracted_fields={
            "gross_total_income": 1200000.0,
            "total_deductions": 225000.0,
            "net_taxable_income": 975000.0,
            "standard_deduction": 75000.0,
            "section_80c": 150000.0
        }
    )

    result = validate_ocr_vs_computed(profile, document, tolerance=10.0)
    assert result.is_consistent is True
    assert len(result.discrepancies) == 0
    assert result.ocr_totals["gross_total_income"] == 1200000.0
    assert result.computed_totals["gross_total_income"] == 1200000.0


def test_validator_flags_discrepancies():
    """Verify that validator flags mismatches exceeding the tolerance threshold."""
    profile = TaxProfile(
        gross_total_income=1200000.0,
        total_deductions=225000.0,
        net_taxable_income=975000.0,
        income=IncomeDetails(salary=1200000.0),
        deductions=DeductionDetails(standard_deduction=75000.0, section_80c=150000.0)
    )

    # Discrepancy in gross total income (diff = 50,000) and 80C (diff = 10,000)
    document = DocumentData(
        document_id="doc-2",
        extracted_fields={
            "gross_total_income": 1250000.0,
            "total_deductions": 225000.0,
            "net_taxable_income": 975000.0,
            "section_80c": 140000.0
        }
    )

    # High tolerance (e.g. 60,000) -> should be consistent
    result_high_tol = validate_ocr_vs_computed(profile, document, tolerance=60000.0)
    assert result_high_tol.is_consistent is True

    # Low tolerance (e.g. 1,000) -> should flag both discrepancies
    result_low_tol = validate_ocr_vs_computed(profile, document, tolerance=1000.0)
    assert result_low_tol.is_consistent is False
    assert len(result_low_tol.discrepancies) == 2
    
    # Check that discrepancy strings mention the field and details
    assert any("Gross Total Income" in d for d in result_low_tol.discrepancies)
    assert any("Section 80C" in d for d in result_low_tol.discrepancies)
