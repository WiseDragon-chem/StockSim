"""
mock_market 服务层 —— 连接 Engine + DB → API routers 的无状态函数。
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime

from mock_market.database import MockSessionLocal
from mock_market.engine import MockPriceEngine
from mock_market.models import DailyBar, MockCompany


# ══════════════════════════════════════════════════════════════════════
# K 线查询
# ══════════════════════════════════════════════════════════════════════

def get_mock_kline(code: str, period: str = "daily") -> list[dict]:
    """
    返回模拟公司 K 线数据（倒序，最新在前）。
    从 daily_bars 表查询历史日线，聚合为周线/月线；
    在最前面拼接引擎当前 in-progress 日线。
    """
    db = MockSessionLocal()
    try:
        company = db.query(MockCompany).filter(MockCompany.code == code).first()
        if company is None:
            return []

        # 查历史日线（倒序）
        bars = (
            db.query(DailyBar)
            .filter(DailyBar.company_id == company.id)
            .order_by(DailyBar.date.desc())
            .all()
        )

        daily_list = [_bar_to_dict(b) for b in bars]

        # 拼接当前进行中的日线（引擎状态）
        engine = MockPriceEngine.get_instance()
        ticker = engine.tickers.get(code)
        if ticker is not None:
            cur = ticker.current_bar()
            if cur is not None:
                # 检查是否与最新历史日线同一天
                if daily_list and daily_list[0]["time"] == cur["time"]:
                    daily_list[0] = cur  # 用引擎状态覆盖
                else:
                    daily_list.insert(0, cur)

        if period == "daily":
            return daily_list
        elif period == "weekly":
            return _aggregate_weekly(daily_list)
        elif period == "monthly":
            return _aggregate_monthly(daily_list)
        return daily_list

    finally:
        db.close()


def get_mock_company_name(code: str) -> str:
    """返回模拟公司中文名称。"""
    db = MockSessionLocal()
    try:
        c = db.query(MockCompany).filter(MockCompany.code == code).first()
        return c.name if c else f"模拟公司 {code}"
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════
# 公司 CRUD
# ══════════════════════════════════════════════════════════════════════

def get_all_companies() -> list[MockCompany]:
    db = MockSessionLocal()
    try:
        return db.query(MockCompany).order_by(MockCompany.code).all()
    finally:
        db.close()


def get_company_by_code(code: str) -> MockCompany | None:
    db = MockSessionLocal()
    try:
        return db.query(MockCompany).filter(MockCompany.code == code).first()
    finally:
        db.close()


def create_company(data: dict) -> MockCompany:
    """在 DB 中创建公司，返回 ORM 对象。"""
    db = MockSessionLocal()
    try:
        c = MockCompany(**data)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c
    finally:
        db.close()


def update_company(code: str, data: dict) -> MockCompany | None:
    """部分更新公司字段。"""
    db = MockSessionLocal()
    try:
        c = db.query(MockCompany).filter(MockCompany.code == code).first()
        if c is None:
            return None
        for key, val in data.items():
            if val is not None:
                setattr(c, key, val)
        c.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(c)
        return c
    finally:
        db.close()


def delete_company(code: str) -> bool:
    """软删除：设置 is_active=False。"""
    db = MockSessionLocal()
    try:
        c = db.query(MockCompany).filter(MockCompany.code == code).first()
        if c is None:
            return False
        c.is_active = False
        c.updated_at = datetime.utcnow()
        db.commit()
        return True
    finally:
        db.close()


def get_company_bar_count(code: str) -> int:
    """返回某公司的历史日线数量。"""
    db = MockSessionLocal()
    try:
        c = db.query(MockCompany).filter(MockCompany.code == code).first()
        if c is None:
            return 0
        return db.query(DailyBar).filter(
            DailyBar.company_id == c.id
        ).count()
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════
# 聚合工具
# ══════════════════════════════════════════════════════════════════════

def _bar_to_dict(bar: DailyBar) -> dict:
    return {
        "time": bar.date,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
    }


def _aggregate_weekly(daily_bars: list[dict]) -> list[dict]:
    """将日线（倒序）聚合为周线（倒序）。"""
    sorted_bars = sorted(daily_bars, key=lambda b: b["time"])

    weeks = OrderedDict()
    for bar in sorted_bars:
        d = datetime.strptime(bar["time"], "%Y-%m-%d").date()
        iso_year, iso_week, _ = d.isocalendar()
        key = (iso_year, iso_week)

        if key not in weeks:
            weeks[key] = {
                "time": bar["time"],
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
            }
        else:
            w = weeks[key]
            w["time"] = bar["time"]
            w["high"] = max(w["high"], bar["high"])
            w["low"] = min(w["low"], bar["low"])
            w["close"] = bar["close"]
            w["volume"] += bar["volume"]

    result = list(weeks.values())
    result.reverse()
    return result


def _aggregate_monthly(daily_bars: list[dict]) -> list[dict]:
    """将日线（倒序）聚合为月线（倒序）。"""
    sorted_bars = sorted(daily_bars, key=lambda b: b["time"])

    months = OrderedDict()
    for bar in sorted_bars:
        key = bar["time"][:7]  # "YYYY-MM"

        if key not in months:
            months[key] = {
                "time": bar["time"],
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
            }
        else:
            m = months[key]
            m["time"] = bar["time"]
            m["high"] = max(m["high"], bar["high"])
            m["low"] = min(m["low"], bar["low"])
            m["close"] = bar["close"]
            m["volume"] += bar["volume"]

    result = list(months.values())
    result.reverse()
    return result
