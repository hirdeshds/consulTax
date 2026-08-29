from pydantic import BaseModel, Field
from typing import Literal


class Income(BaseModel):
    salary: float = Field(default=0, ge=0)
    business_income: float = Field(default=0, ge=0)
    rental_income: float = Field(default=0, ge=0)
    other_income: float = Field(default=0, ge=0)


class Expenses(BaseModel):
    medical: float = Field(default=0, ge=0)
    education: float = Field(default=0, ge=0)
    insurance: float = Field(default=0, ge=0)
    other: float = Field(default=0, ge=0)


class Investments(BaseModel):
    section_80c: float = Field(default=0, ge=0)
    health_insurance: float = Field(default=0, ge=0)
    home_loan_interest: float = Field(default=0, ge=0)
    other: float = Field(default=0, ge=0)


class TaxDocument(BaseModel):
    income: Income
    expenses: Expenses = Expenses()
    investments: Investments = Investments()