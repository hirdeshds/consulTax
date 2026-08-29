"""Unit tests for the tax analysis explanation generator and translator modules."""

import pytest
from app.schemas.api import AnalyzeResponse
from app.schemas.domain import TaxProfile, IncomeDetails, DeductionDetails, TaxRegime
from app.explanation.generator import generate_explanation, get_local_fallback_explanation
from app.explanation.translate import translate_explanation


@pytest.fixture
def sample_analysis():
    """AnalyzeResponse fixture representing a calculated tax summary."""
    profile = TaxProfile(
        profile_id="p-1",
        gross_total_income=1200000.0,
        total_deductions=75000.0,
        net_taxable_income=1125000.0,
        total_tax_liability=100000.0,
        income=IncomeDetails(salary=1200000.0),
        deductions=DeductionDetails(standard_deduction=75000.0)
    )
    return AnalyzeResponse(
        tax_profile=profile,
        recommended_regime=TaxRegime.NEW,
        old_regime_liability=140000.0,
        new_regime_liability=100000.0,
        potential_savings=40000.0,
        applied_rules=[],
        optimization_tips=["Consider opting for employer NPS to save more tax."]
    )


def test_local_fallback_explanation_content(sample_analysis):
    """Verify that the offline fallback creates structured explanations in English and Hindi."""
    # English summary
    explanation_en = get_local_fallback_explanation(sample_analysis, lang="en")
    assert "Tax Analysis Explanation" in explanation_en
    assert "Recommended Regime: NEW" in explanation_en
    assert "Potential Savings: ₹40,000.00" in explanation_en

    # Hindi summary
    explanation_hi = get_local_fallback_explanation(sample_analysis, lang="hi")
    assert "कर विश्लेषण सारांश" in explanation_hi
    assert "अनुशंसित व्यवस्था: NEW" in explanation_hi
    assert "संभावित बचत: ₹40,000.00" in explanation_hi


def test_generate_explanation_falls_back_without_api_keys(sample_analysis, monkeypatch):
    """Verify generate_explanation utilizes the fallback format when API keys are absent."""
    # Ensure no API keys are present in config for testing the fallback
    monkeypatch.setattr("app.config.settings.GROQ_API_KEY", None)
    monkeypatch.setattr("app.config.settings.COHERE_API_KEY", None)

    explanation = generate_explanation(sample_analysis, preferred_language="en")
    assert "Tax Analysis Explanation" in explanation
    assert "₹40,000.00" in explanation


def test_translate_explanation_returns_original_if_english():
    """Verify translation returns the same text if the target language is English."""
    text = "This is a tax report."
    translated = translate_explanation(text, target_lang="en")
    assert translated == text
    
    translated_title = translate_explanation(text, target_lang="english")
    assert translated_title == text


def test_translate_explanation_offline_fallback(monkeypatch):
    """Verify translation falls back gracefully when API keys are absent."""
    monkeypatch.setattr("app.config.settings.GROQ_API_KEY", None)
    monkeypatch.setattr("app.config.settings.COHERE_API_KEY", None)
    
    text = "Report content"
    translated = translate_explanation(text, target_lang="hi")
    assert "Hindi Translation" in translated
    assert text in translated
