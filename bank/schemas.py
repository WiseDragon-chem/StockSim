"""Pydantic schemas for the bank module."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class BankOperationRequest(BaseModel):
    amount: float = Field(..., gt=0, description="操作金额，必须大于0")


class BankStatusResponse(BaseModel):
    savings_balance: float
    savings_interest_rate: float              # daily savings rate (e.g. 0.000041)
    savings_annual_rate_pct: float            # computed: ~1.50
    loan_principal: float
    accrued_interest: float
    loan_interest_rate: float                 # daily loan rate (e.g. 0.0002)
    loan_annual_rate_pct: float               # computed: ~7.30
    available_credit: float                   # computed: 50% × market value − loan_principal − accrued_interest
    total_loan_and_interest: float            # loan_principal + accrued_interest
    has_account: bool                         # True if BankAccount row exists


class TransactionDisplay(BaseModel):
    id: int
    type: str
    amount: float
    detail: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True
