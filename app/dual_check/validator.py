"""Dual-check validator comparing OCR extracted totals with rules engine computed tax values."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.schemas.domain import TaxProfile, DocumentData


class DualCheckResult(BaseModel):
    """Schema representing the results of a sanity validation between OCR and computed values."""
    is_consistent: bool = True
    discrepancies: List[str] = Field(default_factory=list)
    ocr_totals: Dict[str, float] = Field(default_factory=dict)
    computed_totals: Dict[str, float] = Field(default_factory=dict)
    differences: Dict[str, float] = Field(default_factory=dict)


def validate_ocr_vs_computed(
    profile: TaxProfile,
    document: DocumentData,
    tolerance: float = 100.0
) -> DualCheckResult:
    """
    Validates OCR-extracted totals from documents (Form 16, Salary slips, etc.)
    against rules-engine computed totals.
    """
    discrepancies = []
    ocr_totals = {}
    computed_totals = {}
    differences = {}
    
    extracted = document.extracted_fields or {}
    
    # 1. Gross Total Income Check
    ocr_gross = None
    for key in ("gross_total_income", "gross_income", "gross_total", "gross"):
        if key in extracted:
            val = extracted[key]
            if val is not None:
                try:
                    ocr_gross = float(val)
                    break
                except (ValueError, TypeError):
                    pass
                    
    if ocr_gross is not None:
        computed_gross = profile.gross_total_income
        diff = abs(ocr_gross - computed_gross)
        ocr_totals["gross_total_income"] = ocr_gross
        computed_totals["gross_total_income"] = computed_gross
        differences["gross_total_income"] = diff
        
        if diff > tolerance:
            discrepancies.append(
                f"Gross Total Income mismatch: OCR reports ₹{ocr_gross:,.2f} but rules engine "
                f"computed ₹{computed_gross:,.2f} (diff: ₹{diff:,.2f} exceeds tolerance ₹{tolerance:,.2f})"
            )
            
    # 2. Total Deductions Check
    ocr_deductions = None
    for key in ("total_deductions", "deductions_total", "deductions", "total_deduction"):
        if key in extracted:
            val = extracted[key]
            if val is not None:
                try:
                    ocr_deductions = float(val)
                    break
                except (ValueError, TypeError):
                    pass
                    
    if ocr_deductions is not None:
        computed_deductions = profile.total_deductions
        diff = abs(ocr_deductions - computed_deductions)
        ocr_totals["total_deductions"] = ocr_deductions
        computed_totals["total_deductions"] = computed_deductions
        differences["total_deductions"] = diff
        
        if diff > tolerance:
            discrepancies.append(
                f"Total Deductions mismatch: OCR reports ₹{ocr_deductions:,.2f} but rules engine "
                f"computed ₹{computed_deductions:,.2f} (diff: ₹{diff:,.2f} exceeds tolerance ₹{tolerance:,.2f})"
            )
            
    # 3. Net Taxable Income Check
    ocr_taxable = None
    for key in ("taxable_income", "net_taxable_income", "taxable", "net_taxable"):
        if key in extracted:
            val = extracted[key]
            if val is not None:
                try:
                    ocr_taxable = float(val)
                    break
                except (ValueError, TypeError):
                    pass
                    
    if ocr_taxable is not None:
        computed_taxable = profile.net_taxable_income
        diff = abs(ocr_taxable - computed_taxable)
        ocr_totals["net_taxable_income"] = ocr_taxable
        computed_totals["net_taxable_income"] = computed_taxable
        differences["net_taxable_income"] = diff
        
        if diff > tolerance:
            discrepancies.append(
                f"Net Taxable Income mismatch: OCR reports ₹{ocr_taxable:,.2f} but rules engine "
                f"computed ₹{computed_taxable:,.2f} (diff: ₹{diff:,.2f} exceeds tolerance ₹{tolerance:,.2f})"
            )
            
    # 4. Check specific deductions
    sections = ["section_80c", "section_80d", "section_80ccd_2", "section_24b", "standard_deduction"]
    for section in sections:
        ocr_val = None
        if section in extracted:
            try:
                ocr_val = float(extracted[section])
            except (ValueError, TypeError):
                pass
                
        computed_val = 0.0
        if section == "standard_deduction":
            computed_val = profile.deductions.standard_deduction
        else:
            computed_val = getattr(profile.deductions, section, 0.0)
            
        if ocr_val is not None:
            diff = abs(ocr_val - computed_val)
            if diff > tolerance:
                ocr_totals[section] = ocr_val
                computed_totals[section] = computed_val
                differences[section] = diff
                discrepancies.append(
                    f"{section.replace('_', ' ').title()} mismatch: OCR reports ₹{ocr_val:,.2f} "
                    f"but rules engine computed ₹{computed_val:,.2f} (diff: ₹{diff:,.2f} exceeds tolerance ₹{tolerance:,.2f})"
                )

    is_consistent = len(discrepancies) == 0
    return DualCheckResult(
        is_consistent=is_consistent,
        discrepancies=discrepancies,
        ocr_totals=ocr_totals,
        computed_totals=computed_totals,
        differences=differences
    )
