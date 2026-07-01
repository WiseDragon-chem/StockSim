"""Bank service layer — business logic for savings, loans, and interest.

Each function opens its own BankSessionLocal() and receives the main DB session
from the router for cash_balance mutations.  This follows the same pattern as
mock_market/service.py.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session as MainSession

from bank.database import BankSessionLocal
from bank.models import BankAccount, LoanRecord, TransactionLog

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_or_create_account(bank_db, user_id: int) -> BankAccount:
    """Return the BankAccount for *user_id*, creating it if missing."""
    account = bank_db.query(BankAccount).filter(BankAccount.user_id == user_id).first()
    if account is None:
        account = BankAccount(user_id=user_id)
        bank_db.add(account)
        bank_db.commit()
        bank_db.refresh(account)
    return account


def _accrue_loan_interest(account: BankAccount, bank_db) -> None:
    """Accrue daily simple interest on outstanding loan principal.

    Idempotent — skips if already accrued today or if principal ≤ 0.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if account.loan_principal <= 0 or account.last_interest_date == today:
        return

    if account.last_interest_date:
        try:
            last_date = datetime.strptime(account.last_interest_date, "%Y-%m-%d")
            today_date = datetime.strptime(today, "%Y-%m-%d")
            days = (today_date - last_date).days
        except ValueError:
            days = 1
        if days <= 0:
            return
    else:
        days = 1  # first accrual — one day

    interest = round(account.loan_principal * account.interest_rate * days, 2)
    if interest <= 0:
        return

    account.accrued_interest = round(account.accrued_interest + interest, 2)
    account.last_interest_date = today

    log = TransactionLog(
        user_id=account.user_id,
        type="interest",
        amount=interest,
        detail=f"Loan interest × {days} day(s) on principal ¥{account.loan_principal:.2f}",
    )
    bank_db.add(log)
    bank_db.commit()


def _accrue_savings_interest(account: BankAccount, bank_db) -> None:
    """Accrue daily simple interest on savings balance.

    Idempotent — skips if already accrued today or if balance ≤ 0.
    Interest is credited directly to savings_balance (compounding).
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if account.savings_balance <= 0 or account.last_savings_interest_date == today:
        return

    if account.last_savings_interest_date:
        try:
            last_date = datetime.strptime(account.last_savings_interest_date, "%Y-%m-%d")
            today_date = datetime.strptime(today, "%Y-%m-%d")
            days = (today_date - last_date).days
        except ValueError:
            days = 1
        if days <= 0:
            return
    else:
        days = 1

    interest = round(account.savings_balance * account.savings_interest_rate * days, 2)
    if interest <= 0:
        return

    account.savings_balance = round(account.savings_balance + interest, 2)
    account.last_savings_interest_date = today

    log = TransactionLog(
        user_id=account.user_id,
        type="savings_interest",
        amount=interest,
        detail=f"Savings interest × {days} day(s) on balance ¥{account.savings_balance - interest:.2f}",
    )
    bank_db.add(log)
    bank_db.commit()


def _calculate_available_credit_for_user(user_id: int, account: BankAccount | None) -> float:
    """Compute how much more the user can borrow (50 % of position market value).

    We need the main DB for positions — callers pass the pre-fetched User ORM
    object (with eager-loaded positions) to avoid circular imports.
    """
    from core.database import SessionLocal as MainSessionLocal
    from core.models import User

    main_db = MainSessionLocal()
    try:
        user = main_db.query(User).filter(User.id == user_id).first()
        if user is None:
            return 0.0

        positions = user.positions  # lazy-loaded via relationship
        total_mv = 0.0

        for pos in positions:
            latest_price = _get_latest_price(pos.symbol)
            total_mv += pos.quantity * latest_price

        loan_principal = account.loan_principal if account else 0.0
        accrued_interest = account.accrued_interest if account else 0.0
        return round(max(0.0, total_mv * 0.5 - loan_principal - accrued_interest), 2)
    finally:
        main_db.close()


def _get_latest_price(symbol: str) -> float:
    """Best-effort latest close price for *symbol*.

    Returns 0.0 for unknown symbols so they don't contribute to collateral.
    """
    # Mock companies (m00001–m99999) — ask the engine first
    if symbol.startswith("m") and len(symbol) == 6:
        try:
            from mock_market.engine import MockPriceEngine
            engine = MockPriceEngine.get_instance()
            ticker = engine.tickers.get(symbol)
            if ticker is not None:
                bar = ticker.current_bar()
                if bar is not None:
                    return bar["close"]
        except Exception:
            pass

        # Fallback: query daily_bars
        try:
            from mock_market.database import MockSessionLocal
            from mock_market.models import DailyBar, MockCompany
            mdb = MockSessionLocal()
            try:
                company = mdb.query(MockCompany).filter(MockCompany.code == symbol).first()
                if company is not None:
                    last_bar = (
                        mdb.query(DailyBar)
                        .filter(DailyBar.company_id == company.id)
                        .order_by(DailyBar.date.desc())
                        .first()
                    )
                    if last_bar is not None:
                        return last_bar.close
            finally:
                mdb.close()
        except Exception:
            pass
        return 0.0

    # Real A-share — try cache
    try:
        from market_data import load_from_cache
        data = load_from_cache(symbol, "daily")
        if data and len(data) > 0:
            return data[0].get("close", 0.0)
    except Exception:
        pass

    return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def deposit(main_db: MainSession, user_id: int, amount: float) -> BankAccount:
    """Move *amount* from trading cash → bank savings."""
    from core.models import User

    user = main_db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise ValueError("用户不存在")
    if user.cash_balance < amount:
        raise ValueError("余额不足")

    amount = round(amount, 2)
    user.cash_balance = round(user.cash_balance - amount, 2)

    bank_db = BankSessionLocal()
    try:
        account = _get_or_create_account(bank_db, user_id)
        account.savings_balance = round(account.savings_balance + amount, 2)

        log = TransactionLog(user_id=user_id, type="deposit", amount=amount,
                             detail=f"存入 ¥{amount:.2f}")
        bank_db.add(log)
        main_db.commit()
        bank_db.commit()
        bank_db.refresh(account)
        return account
    except Exception:
        bank_db.rollback()
        main_db.rollback()
        raise
    finally:
        bank_db.close()


def withdraw(main_db: MainSession, user_id: int, amount: float) -> BankAccount:
    """Move *amount* from bank savings → trading cash."""
    from core.models import User

    bank_db = BankSessionLocal()
    try:
        account = _get_or_create_account(bank_db, user_id)
        amount = round(amount, 2)
        if account.savings_balance < amount:
            raise ValueError("储蓄余额不足")

        account.savings_balance = round(account.savings_balance - amount, 2)

        user = main_db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise ValueError("用户不存在")
        user.cash_balance = round(user.cash_balance + amount, 2)

        log = TransactionLog(user_id=user_id, type="withdraw", amount=amount,
                             detail=f"取出 ¥{amount:.2f}")
        bank_db.add(log)
        main_db.commit()
        bank_db.commit()
        bank_db.refresh(account)
        return account
    except Exception:
        bank_db.rollback()
        main_db.rollback()
        raise
    finally:
        bank_db.close()


def borrow(main_db: MainSession, user_id: int, amount: float) -> BankAccount:
    """Take a margin loan — credit trading cash, record liability."""
    from core.models import User

    bank_db = BankSessionLocal()
    try:
        account = _get_or_create_account(bank_db, user_id)
        _accrue_loan_interest(account, bank_db)
        _accrue_savings_interest(account, bank_db)

        amount = round(amount, 2)
        available = _calculate_available_credit_for_user(user_id, account)
        if amount > available:
            raise ValueError(f"可用额度不足（最大可借 ¥{available:.2f}）")

        account.loan_principal = round(account.loan_principal + amount, 2)

        # Create individual loan record
        loan = LoanRecord(user_id=user_id, amount=amount, interest_rate=account.interest_rate)
        bank_db.add(loan)

        # Credit trading cash
        user = main_db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise ValueError("用户不存在")
        user.cash_balance = round(user.cash_balance + amount, 2)

        log = TransactionLog(user_id=user_id, type="borrow", amount=amount,
                             detail=f"借款 ¥{amount:.2f}，日利率 {account.interest_rate*100:.3f}%")
        bank_db.add(log)
        main_db.commit()
        bank_db.commit()
        bank_db.refresh(account)
        return account
    except Exception:
        bank_db.rollback()
        main_db.rollback()
        raise
    finally:
        bank_db.close()


def repay(main_db: MainSession, user_id: int, amount: float) -> dict:
    """Repay loan — interest first, then principal. Returns summary dict."""
    from core.models import User

    bank_db = BankSessionLocal()
    try:
        account = _get_or_create_account(bank_db, user_id)
        _accrue_loan_interest(account, bank_db)
        _accrue_savings_interest(account, bank_db)

        amount = round(amount, 2)
        total_owed = round(account.loan_principal + account.accrued_interest, 2)
        if total_owed <= 0:
            raise ValueError("当前无待还款项")

        user = main_db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise ValueError("用户不存在")
        if user.cash_balance < amount:
            raise ValueError("现金余额不足")

        repay_amount = round(min(amount, total_owed), 2)
        user.cash_balance = round(user.cash_balance - repay_amount, 2)

        interest_paid = 0.0
        principal_paid = 0.0

        # Interest first
        if account.accrued_interest > 0:
            interest_paid = round(min(repay_amount, account.accrued_interest), 2)
            account.accrued_interest = round(account.accrued_interest - interest_paid, 2)
            repay_amount = round(repay_amount - interest_paid, 2)

        # Then principal
        if repay_amount > 0 and account.loan_principal > 0:
            principal_paid = round(min(repay_amount, account.loan_principal), 2)
            account.loan_principal = round(account.loan_principal - principal_paid, 2)

        # If fully repaid, mark loans as repaid
        if account.loan_principal <= 0 and account.accrued_interest <= 0:
            account.loan_principal = 0.0
            account.accrued_interest = 0.0
            active_loans = (
                bank_db.query(LoanRecord)
                .filter(LoanRecord.user_id == user_id, LoanRecord.status == "active")
                .all()
            )
            for loan in active_loans:
                loan.status = "repaid"
                loan.repaid_at = datetime.utcnow()

        detail_parts = []
        if interest_paid > 0:
            detail_parts.append(f"利息 ¥{interest_paid:.2f}")
        if principal_paid > 0:
            detail_parts.append(f"本金 ¥{principal_paid:.2f}")

        log = TransactionLog(user_id=user_id, type="repay", amount=round(interest_paid + principal_paid, 2),
                             detail=f"还款：{'，'.join(detail_parts)}")
        bank_db.add(log)
        main_db.commit()
        bank_db.commit()
        bank_db.refresh(account)

        return {
            "msg": "还款成功",
            "interest_paid": interest_paid,
            "principal_paid": principal_paid,
            "remaining_principal": account.loan_principal,
            "remaining_interest": account.accrued_interest,
        }
    except Exception:
        bank_db.rollback()
        main_db.rollback()
        raise
    finally:
        bank_db.close()


def get_bank_status(user_id: int) -> dict:
    """Return full bank status for the current user — used by GET /api/bank/status."""
    bank_db = BankSessionLocal()
    try:
        account = bank_db.query(BankAccount).filter(BankAccount.user_id == user_id).first()

        if account is None:
            return {
                "savings_balance": 0.0,
                "savings_interest_rate": 0.000041,
                "savings_annual_rate_pct": round(0.000041 * 365 * 100, 2),
                "loan_principal": 0.0,
                "accrued_interest": 0.0,
                "loan_interest_rate": 0.0002,
                "loan_annual_rate_pct": round(0.0002 * 365 * 100, 2),
                "available_credit": _calculate_available_credit_for_user(user_id, None),
                "total_loan_and_interest": 0.0,
                "has_account": False,
            }

        _accrue_loan_interest(account, bank_db)
        _accrue_savings_interest(account, bank_db)
        bank_db.refresh(account)

        return {
            "savings_balance": account.savings_balance,
            "savings_interest_rate": account.savings_interest_rate,
            "savings_annual_rate_pct": round(account.savings_interest_rate * 365 * 100, 2),
            "loan_principal": account.loan_principal,
            "accrued_interest": account.accrued_interest,
            "loan_interest_rate": account.interest_rate,
            "loan_annual_rate_pct": round(account.interest_rate * 365 * 100, 2),
            "available_credit": _calculate_available_credit_for_user(user_id, account),
            "total_loan_and_interest": round(account.loan_principal + account.accrued_interest, 2),
            "has_account": True,
        }
    finally:
        bank_db.close()


def get_transactions(user_id: int) -> list[TransactionLog]:
    """Return all bank transactions for *user_id*, newest first."""
    bank_db = BankSessionLocal()
    try:
        return (
            bank_db.query(TransactionLog)
            .filter(TransactionLog.user_id == user_id)
            .order_by(TransactionLog.timestamp.desc())
            .all()
        )
    finally:
        bank_db.close()
