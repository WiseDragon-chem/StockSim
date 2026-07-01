"""Bank ORM models — BankAccount, LoanRecord, TransactionLog.

All models use BankBase (separate from the main app's Base) so bank tables
live in data/bank.db, isolated from the core trading database.
"""

import datetime

from sqlalchemy import Column, Integer, Float, String, DateTime
from bank.database import BankBase


class BankAccount(BankBase):
    """One row per user — created lazily on the first bank operation."""

    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    savings_balance = Column(Float, default=0.0)
    savings_interest_rate = Column(Float, default=0.000041)   # daily rate (0.0041% ≈ 1.5% APR)
    last_savings_interest_date = Column(String(10), nullable=True)  # "YYYY-MM-DD"
    loan_principal = Column(Float, default=0.0)        # total borrowed, not yet repaid
    accrued_interest = Column(Float, default=0.0)      # outstanding loan interest
    interest_rate = Column(Float, default=0.0002)      # daily loan rate (0.02% ≈ 7.3% APR)
    last_interest_date = Column(String(10), nullable=True)  # "YYYY-MM-DD" of last loan accrual
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class LoanRecord(BankBase):
    """Audit trail — one row per individual loan."""

    __tablename__ = "loan_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    amount = Column(Float, nullable=False)              # loan principal amount
    interest_rate = Column(Float, nullable=False)       # snapshot of rate at time of loan
    status = Column(String, default="active")            # "active" | "repaid"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    repaid_at = Column(DateTime, nullable=True)


class TransactionLog(BankBase):
    """Unified audit log for all bank actions."""

    __tablename__ = "transaction_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    type = Column(String, nullable=False)               # deposit | withdraw | borrow | repay | interest
    amount = Column(Float, nullable=False)
    detail = Column(String, nullable=True)              # e.g. "Repaid principal: 5000.00, interest: 120.00"
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
