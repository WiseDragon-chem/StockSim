"""Independent SQLite database for the bank module.

Follows the same pattern as mock_market/database.py:
- Separate engine/session/Base from the main app DB
- WAL mode for better concurrent read/write
- Dependency injection helper for FastAPI routes
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

BANK_DB_URL = "sqlite:///./data/bank.db"

bank_engine = create_engine(BANK_DB_URL, connect_args={"check_same_thread": False})


@event.listens_for(bank_engine, "connect")
def _set_wal_mode(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


BankSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=bank_engine)
BankBase = declarative_base()


def get_bank_db():
    """FastAPI dependency — yields a bank DB session, auto-closes."""
    db = BankSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_bank_db():
    """Create all bank tables if they don't exist."""
    from bank.models import BankAccount, LoanRecord, TransactionLog  # noqa: F401
    BankBase.metadata.create_all(bind=bank_engine)
