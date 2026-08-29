"""Integration tests for the tax simulator endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.domain import TaxProfile, IncomeDetails, DeductionDetails


@pytest.fixture
def client():
    """TestClient fixture for interacting with FastAPI app."""
    return TestClient(app)


def test_simulate_endpoint_calculates_savings(client):
    """Verify that simulate endpoint correctly applies overrides and computes tax liability change."""
    profile = {
        "financial_year": "2024-2025",
        "age": 30,
        "income": {
            "salary": 1500000.0
        },
        "deductions": {
            "section_80c": 50000.0  # Baseline 80C: 50k
        }
    }

    # Simulation payload: increase 80C deductions to 150,000 and use OLD tax regime
    payload = {
        "tax_profile": profile,
        "adjustments": {
            "deductions": {
                "section_80c": 150000.0  # Adjust 80C up by 100k
            }
        },
        "target_regime": "old"
    }

    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    # Check that response fields are returned as expected
    assert "original_liability" in data
    assert "projected_liability" in data
    assert "net_savings" in data
    assert "rule_breakdown" in data
    
    # Under old regime: reducing taxable income by 100,000 (from 80C increase) saves tax.
    # Tax rate for 10L+ is 30% under OLD regime, so savings should be ~30,000 + cess.
    assert data["net_savings"] > 0.0
    assert data["projected_liability"] < data["original_liability"]
    
    # Verify that the rule breakdown is populated
    assert len(data["rule_breakdown"]) > 0


def test_simulate_invalid_regime_error(client):
    """Verify that invalid parameters in simulation request return validation errors."""
    payload = {
        "tax_profile": {
            "financial_year": "2024-2025",
            "income": {"salary": 1000000.0}
        },
        "target_regime": "invalid_regime_value"  # Causes Pydantic/Enum validation error
    }

    response = client.post("/api/simulate", json=payload)
    assert response.status_code == 422  # Unprocessable entity
