"""Unit tests for the PDF filing summary generator."""

import pytest
from app.schemas.api import AnalyzeResponse
from app.schemas.domain import TaxProfile, IncomeDetails, DeductionDetails, TaxRegime
from app.pdf.filing_summary import generate_filing_summary_pdf


def test_pdf_generation_returns_valid_bytes():
    """Verify that generating a filing summary PDF outputs a valid PDF byte stream."""
    profile = TaxProfile(
        profile_id="p-pdf-test",
        gross_total_income=1200000.0,
        total_deductions=75000.0,
        net_taxable_income=1125000.0,
        total_tax_liability=100000.0,
        income=IncomeDetails(salary=1200000.0),
        deductions=DeductionDetails(standard_deduction=75000.0)
    )
    analysis = AnalyzeResponse(
        tax_profile=profile,
        recommended_regime=TaxRegime.NEW,
        old_regime_liability=140000.0,
        new_regime_liability=100000.0,
        potential_savings=40000.0,
        applied_rules=[],
        optimization_tips=["Employer NPS option."]
    )

    explanation = "### Summary\n- Potential Savings: ₹40k\n- Optimized standard deduction."

    # Generate the PDF
    pdf_bytes = generate_filing_summary_pdf(
        profile=profile,
        analysis=analysis,
        explanation=explanation
    )

    # Assertions
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    # PDF specification magic number / signature header check
    assert pdf_bytes.startswith(b"%PDF-")
