"""
mock_market 独立数据库层
使用独立的 SQLite 数据库 mock_market.db，与主 sql_app.db 隔离。
启用 WAL 日志模式以支持并发读写。
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

MOCK_DB_URL = "sqlite:///./mock_market.db"

mock_engine = create_engine(
    MOCK_DB_URL,
    connect_args={"check_same_thread": False},
)

# 启用 WAL 模式，提升并发读写性能
@event.listens_for(mock_engine, "connect")
def _set_wal_mode(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


MockSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=mock_engine)
MockBase = declarative_base()


def get_mock_db():
    """FastAPI 依赖：每个请求一个 mock DB 会话。"""
    db = MockSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_mock_db():
    """
    创建所有 mock DB 表，如果 companies 表为空则自动播种 10 家默认公司。
    """
    from mock_market.models import MockCompany  # noqa: F811 — 确保模型已注册

    MockBase.metadata.create_all(bind=mock_engine)

    db = MockSessionLocal()
    try:
        if db.query(MockCompany).count() == 0:
            _seed_default_companies(db)
    finally:
        db.close()


_DEFAULT_COMPANIES = [
    # (code,    name,             initial_price, mu,      sigma,   mean_rev, tick_sigma, tick_interval, ticks_per_day)
    ("m00001", "星辰科技",         68.00,   0.0003,  0.018,   0.05,     0.0025,     30,            240),
    ("m00002", "深海能源",         42.50,   0.0001,  0.022,   0.07,     0.0030,     25,            240),
    ("m00003", "银河生物",         25.80,   0.0004,  0.025,   0.06,     0.0035,     35,            240),
    ("m00004", "极光半导体",       150.00,  0.0002,  0.030,   0.04,     0.0040,     20,            240),
    ("m00005", "天穹材料",         33.20,   0.0000,  0.020,   0.06,     0.0028,     30,            240),
    ("m00006", "磐石重工",         18.90,   -0.0001, 0.015,   0.08,     0.0020,     40,            240),
    ("m00007", "云端数据",         88.00,   0.0005,  0.028,   0.05,     0.0032,     22,            240),
    ("m00008", "绿洲农业",         12.60,   0.0000,  0.018,   0.07,     0.0022,     35,            240),
    ("m00009", "量子金融",         55.50,   0.0002,  0.026,   0.05,     0.0038,     28,            240),
    ("m00010", "远航物流",         20.30,   0.0001,  0.019,   0.06,     0.0026,     30,            240),
]


def _seed_default_companies(db):
    """向 companies 表插入 10 家默认模拟公司。"""
    from mock_market.models import MockCompany
    import datetime

    now = datetime.datetime.utcnow()
    for (code, name, init_price, mu, sigma, mr, ts, ti, tpd) in _DEFAULT_COMPANIES:
        company = MockCompany(
            code=code,
            name=name,
            initial_price=init_price,
            daily_drift_mu=mu,
            daily_sigma=sigma,
            mean_reversion=mr,
            tick_sigma=ts,
            tick_interval_seconds=ti,
            ticks_per_day=tpd,
            created_at=now,
            updated_at=now,
        )
        db.add(company)
    db.commit()
