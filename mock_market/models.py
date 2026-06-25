"""
mock_market ORM 模型 —— 模拟公司、日线数据、引擎快照。
"""

import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey,
    UniqueConstraint, LargeBinary,
)
from mock_market.database import MockBase


class MockCompany(MockBase):
    """模拟公司配置 —— 一家 24/7 交易的模拟股票及其超参数。"""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False, index=True)     # e.g. "m00001"
    name = Column(String, nullable=False)                              # e.g. "星辰科技"
    initial_price = Column(Float, default=50.0)
    daily_drift_mu = Column(Float, default=0.0002)
    daily_sigma = Column(Float, default=0.02)
    mean_reversion = Column(Float, default=0.06)
    tick_sigma = Column(Float, default=0.003)
    tick_interval_seconds = Column(Integer, default=30)
    ticks_per_day = Column(Integer, default=240)
    price_min = Column(Float, default=0.50)
    price_max = Column(Float, default=10000.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)


class DailyBar(MockBase):
    """已完成的日 K 线（持久化到数据库，用于历史查询）。"""
    __tablename__ = "daily_bars"
    __table_args__ = (
        UniqueConstraint("company_id", "date", name="uq_company_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False)    # "YYYY-MM-DD" (UTC)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, default=0)


class TickerSnapshot(MockBase):
    """
    引擎状态快照（每家公司一行）。
    用于服务器重启后的状态恢复。
    """
    __tablename__ = "ticker_snapshots"

    company_id = Column(Integer, ForeignKey("companies.id"),
                        primary_key=True, index=True)
    last_price = Column(Float, nullable=False)
    current_date = Column(String(10), nullable=False)
    day_open = Column(Float, nullable=False)
    day_high = Column(Float, nullable=False)
    day_low = Column(Float, nullable=False)
    day_close_target = Column(Float, nullable=False)
    tick_index = Column(Integer, default=0)
    session_high = Column(Float, nullable=False)
    session_low = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False, default=0)
    rng_state = Column(LargeBinary, nullable=True)  # pickled random.Random state
