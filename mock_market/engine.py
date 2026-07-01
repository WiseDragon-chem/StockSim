"""
mock_market 价格生成引擎

核心组件：
- CompanyTicker：单家公司的日内价格模拟（布朗桥模型，24/7 运行）
- MockPriceEngine：单例管理器，维护所有 ticker 的后台循环 + 持久化 + 恢复
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import pickle
import random
import threading
from datetime import date, datetime, timedelta

from mock_market.database import MockSessionLocal
from mock_market.models import DailyBar, MockCompany, TickerSnapshot

# ══════════════════════════════════════════════════════════════════════
# CompanyTicker — 单家公司日内价格模拟
# ══════════════════════════════════════════════════════════════════════


class CompanyTicker:
    """
    单家模拟公司的日内 tick 状态。
    使用布朗桥模型：价格在日内从 open 走向 close_target，同时叠加
    均值回归 + 随机噪声。每天结束时生成一根完整的日 K 线存入数据库，
    然后自动开始新一天。
    """

    __slots__ = (
        "company_id", "code", "name",
        "initial_price", "daily_drift_mu", "daily_sigma",
        "mean_reversion", "tick_sigma",
        "tick_interval_seconds", "ticks_per_day",
        "price_min", "price_max", "is_active",
        # ── 日内状态 ──
        "price", "current_date", "day_open", "day_high", "day_low",
        "day_close_target", "tick_index",
        "session_high", "session_low", "volume",
        # ── 内部 ──
        "rng", "lock", "_last_tick_time",
    )

    def __init__(self, company: MockCompany):
        self.company_id = company.id
        self.code = company.code
        self.name = company.name
        self.initial_price = company.initial_price
        self.daily_drift_mu = company.daily_drift_mu
        self.daily_sigma = company.daily_sigma
        self.mean_reversion = company.mean_reversion
        self.tick_sigma = company.tick_sigma
        self.tick_interval_seconds = company.tick_interval_seconds
        self.ticks_per_day = company.ticks_per_day
        self.price_min = company.price_min
        self.price_max = company.price_max
        self.is_active = company.is_active

        self.lock = threading.Lock()
        self._last_tick_time = datetime.utcnow()

    # ── RNG ─────────────────────────────────────────────────────────

    def _seed_for_date(self, day_str: str) -> random.Random:
        """从 code + date 生成确定性种子。"""
        raw = f"{self.code}:{day_str}"
        h = hashlib.sha256(raw.encode()).hexdigest()
        seed = int(h[:8], 16)
        return random.Random(seed)

    # ── 日内操作 ────────────────────────────────────────────────────

    def _start_new_day(self, day_str: str) -> None:
        """开始一个新的模拟交易日。"""
        rng = self._seed_for_date(day_str)

        # 日收益率
        daily_return = rng.gauss(mu=self.daily_drift_mu, sigma=self.daily_sigma)
        self.day_open = self.price  # 新一天开盘 = 上一 tick 收盘价
        target = self.day_open * math.exp(daily_return)
        # 价格上下限钳制
        target = max(self.price_min, min(self.price_max, target))
        self.day_close_target = round(target, 2)

        self.day_high = self.day_open
        self.day_low = self.day_open
        self.current_date = day_str
        self.tick_index = 0
        self.volume = 0
        self.rng = rng

    def advance(self) -> dict:
        """
        前进一个 tick，返回 WebSocket / K 线格式的当前日线快照 dict。
        调用方负责持锁。
        """
        if self.tick_index == 0 and self.current_date is None:
            # 首次启动
            today_str = date.today().strftime("%Y-%m-%d")
            self._start_new_day(today_str)

        if self.tick_index >= self.ticks_per_day:
            # 当天已走完 → 下一天
            next_date = _add_days(self.current_date, 1)
            self._start_new_day(next_date)

        progress = self.tick_index / max(self.ticks_per_day, 1)
        self.tick_index += 1

        # 布朗桥目标
        target = self.day_open + (self.day_close_target - self.day_open) * progress

        # 均值回归 + 噪声
        reversion = (target - self.price) * self.mean_reversion
        noise = self.price * self.rng.gauss(mu=0.0, sigma=self.tick_sigma)

        self.price = round(self.price + reversion + noise, 2)
        if self.price < self.price_min:
            self.price = self.price_min
        elif self.price > self.price_max:
            self.price = self.price_max

        # 极值更新
        if self.price > self.day_high:
            self.day_high = self.price
        if self.price < self.day_low:
            self.day_low = self.price
        if self.price > self.session_high:
            self.session_high = self.price
        if self.price < self.session_low:
            self.session_low = self.price

        # 模拟成交量（均匀累加）
        base_vol = int(self.price * 100_000)
        self.volume = int(base_vol * progress)

        self._last_tick_time = datetime.utcnow()

        return _make_bar_dict(
            self.current_date, self.day_open, self.day_high,
            self.day_low, self.price, self.volume,
        )

    def current_bar(self) -> dict | None:
        """返回当前日线快照（不推进 tick，用于 WebSocket 读取）。"""
        if self.current_date is None:
            return None
        return _make_bar_dict(
            self.current_date, self.day_open, self.day_high,
            self.day_low, self.price, self.volume,
        )

    def should_tick(self) -> bool:
        """检查距上次 tick 是否已超过配置的间隔。"""
        elapsed = (datetime.utcnow() - self._last_tick_time).total_seconds()
        return elapsed >= self.tick_interval_seconds

    # ── 持久化 ─────────────────────────────────────────────────────

    def to_snapshot_dict(self) -> dict:
        """序列化当前状态为 dict，供写入 TickerSnapshot 表。"""
        return {
            "company_id": self.company_id,
            "last_price": self.price,
            "current_date": self.current_date or "",
            "day_open": self.day_open,
            "day_high": self.day_high,
            "day_low": self.day_low,
            "day_close_target": self.day_close_target,
            "tick_index": self.tick_index,
            "session_high": self.session_high,
            "session_low": self.session_low,
            "volume": self.volume,
            "rng_state": pickle.dumps(self.rng.getstate())
            if self.rng is not None else None,
        }

    def apply_snapshot(self, snap: TickerSnapshot) -> None:
        """从数据库快照恢复状态。"""
        self.price = snap.last_price
        self.current_date = snap.current_date
        self.day_open = snap.day_open
        self.day_high = snap.day_high
        self.day_low = snap.day_low
        self.day_close_target = snap.day_close_target
        self.tick_index = snap.tick_index
        self.session_high = snap.session_high
        self.session_low = snap.session_low
        self.volume = snap.volume
        if snap.rng_state is not None:
            try:
                state = pickle.loads(snap.rng_state)
                self.rng = random.Random()
                self.rng.setstate(state)
            except Exception:
                self.rng = self._seed_for_date(self.current_date or "2020-01-01")
        else:
            self.rng = self._seed_for_date(self.current_date or "2020-01-01")


# ══════════════════════════════════════════════════════════════════════
# MockPriceEngine — 单例后台引擎
# ══════════════════════════════════════════════════════════════════════

_SNAPSHOT_INTERVAL = 10  # 每 N tick 写一次快照，减少 DB 写入


class MockPriceEngine:
    """
    单例价格引擎。
     - start()   → 从 DB 加载公司，恢复状态，启动后台循环
     - stop()    → 停止循环，flush 所有快照
     - get_latest_bar(code) → 返回当前 tick 快照（供 WebSocket 用）
    """

    _instance: MockPriceEngine | None = None

    def __init__(self):
        self.tickers: dict[str, CompanyTicker] = {}   # code → ticker
        self._task: asyncio.Task | None = None
        self._running = False

    @classmethod
    def get_instance(cls) -> MockPriceEngine:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── 生命周期 ───────────────────────────────────────────────────

    async def start(self) -> None:
        """启动引擎：加载公司 → 恢复/创建 ticker → 后台循环。"""
        self._running = True
        db = MockSessionLocal()
        try:
            companies = db.query(MockCompany).filter(MockCompany.is_active == True).all()
            for c in companies:
                ticker = CompanyTicker(c)
                snap = db.query(TickerSnapshot).filter(
                    TickerSnapshot.company_id == c.id
                ).first()

                if snap is not None:
                    ticker.apply_snapshot(snap)
                    # 快进：补上停机期间流逝的天数
                    await self._fast_forward(ticker, db)
                    # 如果当天 tick 已完成，切到新一天
                    if ticker.tick_index >= ticker.ticks_per_day:
                        next_date = _add_days(ticker.current_date, 1)
                        ticker._start_new_day(next_date)
                else:
                    # 首运行：以 initial_price 为基准生成历史日线 + 从今天开始
                    await self._generate_history(ticker, db)
                    today_str = date.today().strftime("%Y-%m-%d")
                    ticker._start_new_day(today_str)

                self.tickers[ticker.code] = ticker
                # 写一次初始快照
                self._save_snapshot(ticker, db)

            db.commit()
        finally:
            db.close()

        self._task = asyncio.create_task(self._run_loop())
        print(f"[MockEngine] 已启动，{len(self.tickers)} 家模拟公司就绪")

    async def stop(self) -> None:
        """停止引擎，保存所有快照。"""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # 最后一次 flush
        db = MockSessionLocal()
        try:
            for ticker in self.tickers.values():
                self._save_snapshot(ticker, db)
            db.commit()
        finally:
            db.close()
        print("[MockEngine] 已停止，所有状态已保存")

    # ── 后台循环 ───────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        """
        无限循环：遍历 ticker，对到时的执行 advance()，
        按间隔写快照，检测日切换时落库日线。
        """
        tick_counter: dict[str, int] = {}
        while self._running:
            db = MockSessionLocal()
            try:
                for code, ticker in self.tickers.items():
                    if not ticker.is_active:
                        continue
                    if not ticker.should_tick():
                        continue

                    with ticker.lock:
                        prev_date = ticker.current_date
                        ticker.advance()

                        # 日切换 → 保存已完成日线
                        if prev_date and ticker.current_date != prev_date:
                            self._save_daily_bar(ticker, prev_date, db)

                        # 定期快照
                        cnt = tick_counter.get(code, 0) + 1
                        tick_counter[code] = cnt
                        if cnt % _SNAPSHOT_INTERVAL == 0:
                            self._save_snapshot(ticker, db)

                db.commit()
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                db.close()

            await asyncio.sleep(1)  # 每秒检查一次，避免忙等

    # ── 持久化辅助 ─────────────────────────────────────────────────

    def _save_snapshot(self, ticker: CompanyTicker, db) -> None:
        """将 ticker 状态写入 ticker_snapshots 表（upsert）。"""
        data = ticker.to_snapshot_dict()
        snap = db.query(TickerSnapshot).filter(
            TickerSnapshot.company_id == ticker.company_id
        ).first()
        if snap is None:
            snap = TickerSnapshot(**data)
            db.add(snap)
        else:
            for k, v in data.items():
                setattr(snap, k, v)

    def _save_daily_bar(self, ticker: CompanyTicker, day_str: str, db) -> None:
        """保存一根已完成的日线到 daily_bars 表。"""
        existing = db.query(DailyBar).filter(
            DailyBar.company_id == ticker.company_id,
            DailyBar.date == day_str,
        ).first()
        if existing is not None:
            return  # 已有，跳过

        bar = DailyBar(
            company_id=ticker.company_id,
            date=day_str,
            open=round(ticker.day_open, 2),
            high=round(ticker.session_high, 2),
            low=round(ticker.session_low, 2),
            close=round(ticker.price, 2),
            volume=ticker.volume,
        )
        db.add(bar)

    # ── 恢复 / 历史 ────────────────────────────────────────────────

    async def _fast_forward(self, ticker: CompanyTicker, db) -> None:
        """
        补上停机期间流逝的交易日。
        对每个逝去的 UTC 日，生成一根日线并入库。
        """
        if not ticker.current_date:
            return
        today_str = date.today().strftime("%Y-%m-%d")
        current = ticker.current_date
        while current < today_str:
            # 把当天剩下的 tick 走完（用快速 bulk 模拟代替逐 tick）
            self._simulate_day_close(ticker)
            self._save_daily_bar(ticker, current, db)
            next_date = _add_days(current, 1)
            ticker.price = ticker.day_close_target
            ticker._start_new_day(next_date)
            current = next_date

    def _simulate_day_close(self, ticker: CompanyTicker) -> None:
        """将当天剩余 tick 快速模拟完成（不逐 tick 写 DB）。"""
        remaining = ticker.ticks_per_day - ticker.tick_index
        if remaining <= 0:
            return
        for _ in range(remaining):
            progress = ticker.tick_index / max(ticker.ticks_per_day, 1)
            ticker.tick_index += 1
            target = ticker.day_open + (ticker.day_close_target - ticker.day_open) * progress
            reversion = (target - ticker.price) * ticker.mean_reversion
            noise = ticker.price * ticker.rng.gauss(mu=0.0, sigma=ticker.tick_sigma)
            ticker.price = round(ticker.price + reversion + noise, 2)
            if ticker.price < ticker.price_min:
                ticker.price = ticker.price_min
            elif ticker.price > ticker.price_max:
                ticker.price = ticker.price_max
            if ticker.price > ticker.session_high:
                ticker.session_high = ticker.price
            if ticker.price < ticker.session_low:
                ticker.session_low = ticker.price

    async def _generate_history(self, ticker: CompanyTicker, db) -> None:
        """
        首运行：从 2020-01-01 到昨天，用确定性随机游走生成历史日线。
        """
        start = date(2020, 1, 1)
        end = date.today() - timedelta(days=1)
        if end < start:
            return

        price = ticker.initial_price
        d = start
        while d <= end:
            day_str = d.strftime("%Y-%m-%d")
            rng = ticker._seed_for_date(day_str)
            daily_return = rng.gauss(mu=ticker.daily_drift_mu, sigma=ticker.daily_sigma)
            open_p = round(price, 2)
            close_p = round(open_p * math.exp(daily_return), 2)
            if close_p < ticker.price_min:
                close_p = ticker.price_min
            elif close_p > ticker.price_max:
                close_p = ticker.price_max

            intraday_pct = rng.uniform(0.005, 0.04)
            high_p = round(max(open_p, close_p) * (1.0 + rng.uniform(0, intraday_pct)), 2)
            low_p = round(min(open_p, close_p) * (1.0 - rng.uniform(0, intraday_pct)), 2)
            vol = int(rng.uniform(1_000_000, 200_000_000))

            existing = db.query(DailyBar).filter(
                DailyBar.company_id == ticker.company_id,
                DailyBar.date == day_str,
            ).first()
            if existing is None:
                bar = DailyBar(
                    company_id=ticker.company_id,
                    date=day_str,
                    open=open_p,
                    high=high_p,
                    low=low_p,
                    close=close_p,
                    volume=vol,
                )
                db.add(bar)

            price = close_p
            d += timedelta(days=1)

        # 设置当前价格
        ticker.price = price
        ticker.session_high = price
        ticker.session_low = price
        db.flush()

    # ── 公开 API ───────────────────────────────────────────────────

    def get_latest_bar(self, code: str) -> dict | None:
        """
        返回当前日线快照（供 WebSocket 推送）。
        不推进 tick，只读取当前 state（线程安全）。
        """
        ticker = self.tickers.get(code)
        if ticker is None:
            return None
        with ticker.lock:
            bar = ticker.current_bar()
        if bar is None:
            return None
        return {"type": "update", "data": bar}

    def get_all_ticker_prices(self) -> dict[str, dict]:
        """
        返回所有活跃 ticker 的完整日线快照（供 WebSocket 全量推送）。
        不推进 tick，只读取当前 state（线程安全）。
        返回格式：{code: {time, open, high, low, close, volume}, ...}
        """
        result = {}
        for code, ticker in self.tickers.items():
            with ticker.lock:
                bar = ticker.current_bar()
                if bar is not None:
                    result[code] = bar
        return result

    async def reload_company(self, code: str) -> bool:
        """重新从 DB 加载公司配置（管理员修改超参数后调用）。"""
        db = MockSessionLocal()
        try:
            c = db.query(MockCompany).filter(MockCompany.code == code).first()
            if c is None:
                return False
            ticker = self.tickers.get(code)
            if ticker is not None:
                with ticker.lock:
                    ticker.daily_drift_mu = c.daily_drift_mu
                    ticker.daily_sigma = c.daily_sigma
                    ticker.mean_reversion = c.mean_reversion
                    ticker.tick_sigma = c.tick_sigma
                    ticker.tick_interval_seconds = c.tick_interval_seconds
                    ticker.ticks_per_day = c.ticks_per_day
                    ticker.price_min = c.price_min
                    ticker.price_max = c.price_max
                    ticker.is_active = c.is_active
                    ticker.name = c.name
            return True
        finally:
            db.close()

    async def reset_company(self, code: str) -> bool:
        """
        重置公司：清除历史日线，价格回到 initial_price。
        """
        db = MockSessionLocal()
        try:
            c = db.query(MockCompany).filter(MockCompany.code == code).first()
            if c is None:
                return False

            # 清除历史日线
            db.query(DailyBar).filter(
                DailyBar.company_id == c.id
            ).delete()
            # 清除快照
            db.query(TickerSnapshot).filter(
                TickerSnapshot.company_id == c.id
            ).delete()
            db.commit()

            # 重建 ticker
            ticker = CompanyTicker(c)
            ticker.price = c.initial_price
            ticker.session_high = c.initial_price
            ticker.session_low = c.initial_price
            await self._generate_history(ticker, db)
            today_str = date.today().strftime("%Y-%m-%d")
            ticker._start_new_day(today_str)
            self._save_snapshot(ticker, db)
            db.commit()

            self.tickers[code] = ticker
            return True
        finally:
            db.close()

    async def remove_company(self, code: str) -> bool:
        """停止并移除指定公司的 ticker（管理员硬删除后调用）。"""
        ticker = self.tickers.pop(code, None)
        return ticker is not None

    async def add_company(self, code: str) -> bool:
        """动态添加新公司到引擎（管理员创建后调用）。"""
        db = MockSessionLocal()
        try:
            c = db.query(MockCompany).filter(MockCompany.code == code).first()
            if c is None:
                return False
            ticker = CompanyTicker(c)
            ticker.price = c.initial_price
            ticker.session_high = c.initial_price
            ticker.session_low = c.initial_price
            await self._generate_history(ticker, db)
            today_str = date.today().strftime("%Y-%m-%d")
            ticker._start_new_day(today_str)
            self._save_snapshot(ticker, db)
            db.commit()
            self.tickers[code] = ticker
            return True
        finally:
            db.close()

    def has_company(self, code: str) -> bool:
        return code in self.tickers


# ══════════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════════


def _make_bar_dict(time_str: str, open_p: float, high_p: float,
                   low_p: float, close_p: float, volume: int) -> dict:
    return {
        "time": time_str,
        "open": round(open_p, 2),
        "high": round(high_p, 2),
        "low": round(low_p, 2),
        "close": round(close_p, 2),
        "volume": volume,
    }


def _add_days(date_str: str, n: int) -> str:
    """日期字符串加 n 天 → 返回 'YYYY-MM-DD'。"""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    d += timedelta(days=n)
    return d.strftime("%Y-%m-%d")
