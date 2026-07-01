"""Bank API router — savings, margin loans, repayments, and transaction history.

All write endpoints require authentication (via JWT token).
Read endpoints (status, transactions) also require auth since data is per-user.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core import models as core_models
from core.auth import get_current_user
from bank import service as bank_service
from bank import schemas as bank_schemas

router = APIRouter()


# ── Status ──────────────────────────────────────────────────────────────

@router.get("/status", response_model=bank_schemas.BankStatusResponse)
def bank_status(
    current_user: core_models.User = Depends(get_current_user),
):
    """Return the current user's bank account summary."""
    try:
        return bank_service.get_bank_status(current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Deposit ─────────────────────────────────────────────────────────────

@router.post("/deposit")
def deposit(
    req: bank_schemas.BankOperationRequest,
    current_user: core_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move cash from trading account to bank savings."""
    try:
        bank_service.deposit(db, current_user.id, req.amount)
        db.refresh(current_user)
        return {
            "msg": f"成功存入 ¥{req.amount:.2f}",
            "new_cash_balance": current_user.cash_balance,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Withdraw ────────────────────────────────────────────────────────────

@router.post("/withdraw")
def withdraw(
    req: bank_schemas.BankOperationRequest,
    current_user: core_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move cash from bank savings to trading account."""
    try:
        bank_service.withdraw(db, current_user.id, req.amount)
        db.refresh(current_user)
        return {
            "msg": f"成功取出 ¥{req.amount:.2f}",
            "new_cash_balance": current_user.cash_balance,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Borrow ──────────────────────────────────────────────────────────────

@router.post("/borrow")
def borrow(
    req: bank_schemas.BankOperationRequest,
    current_user: core_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Take a margin loan — collateralized by position market value (50% LTV)."""
    try:
        bank_service.borrow(db, current_user.id, req.amount)
        db.refresh(current_user)
        return {
            "msg": f"成功借款 ¥{req.amount:.2f}",
            "new_cash_balance": current_user.cash_balance,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Repay ───────────────────────────────────────────────────────────────

@router.post("/repay")
def repay(
    req: bank_schemas.BankOperationRequest,
    current_user: core_models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Repay a loan — interest is paid first, then principal."""
    try:
        result = bank_service.repay(db, current_user.id, req.amount)
        db.refresh(current_user)
        result["new_cash_balance"] = current_user.cash_balance
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Transaction history ─────────────────────────────────────────────────

@router.get("/transactions", response_model=list[bank_schemas.TransactionDisplay])
def transactions(
    current_user: core_models.User = Depends(get_current_user),
):
    """Return bank transaction history, newest first."""
    txns = bank_service.get_transactions(current_user.id)
    return [bank_schemas.TransactionDisplay.model_validate(t) for t in txns]
