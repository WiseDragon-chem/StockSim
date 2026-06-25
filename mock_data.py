"""
模拟股票数据源 — 独立模块，与 market_data.py / AkShare 完全解耦。

当股票代码以 "mock" 开头时（不区分大小写），由本模块提供模拟 K 线数据，
支持日线/周线/月线和 WebSocket 实时推送。
"""

from __future__ import annotations

import hashlib
import math
import random
from collections import OrderedDict
from datetime import date, datetime, timedelta

# ══════════════════════════════════════════════════════════════════════
# 随机游走参数
# ══════════════════════════════════════════════════════════════════════
_DAILY_DRIFT = 0.0002          # 日均对数收益率（年化 ~5% 向上漂移）
_DAILY_SIGMA = 0.02            # 日波动率 2%（年化 ~32%）
_INTRADAY_RANGE_MIN = 0.005    # 日内振幅下限 0.5%
_INTRADAY_RANGE_MAX = 0.04     # 日内振幅上限 4%
_VOLUME_MIN = 1_000_000
_VOLUME_MAX = 200_000_000
_DATA_START_DATE = date(2020, 1, 1)

# 内存缓存（不写磁盘）
_daily_cache: dict[str, list[dict]] = {}
_weekly_cache: dict[str, list[dict]] = {}
_monthly_cache: dict[str, list[dict]] = {}


# ══════════════════════════════════════════════════════════════════════
# 公开工具函数
# ══════════════════════════════════════════════════════════════════════

def is_mock_symbol(symbol: str) -> bool:
    """判断是否为模拟股票代码（以 'mock' 开头，不区分大小写）。"""
    return symbol.lower().startswith("mock")


# ══════════════════════════════════════════════════════════════════════
# 内部工具
# ══════════════════════════════════════════════════════════════════════

def _make_seed(symbol: str) -> int:
    """利用 SHA-256 从 symbol 计算 32-bit 确定性随机种子。"""
    h = hashlib.sha256(symbol.lower().encode()).hexdigest()
    return int(h[:8], 16)


def _trading_days(start: date, end: date):
    """生成 start~end 之间所有周一至周五的日期（升序）。"""
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


# ══════════════════════════════════════════════════════════════════════
# 日 K 线生成（确定性随机游走）
# ══════════════════════════════════════════════════════════════════════

def _generate_daily_bars(symbol: str) -> list[dict]:
    """
    从 _DATA_START_DATE 到今天，用确定性随机游走生成日 K 线。
    返回按时间**倒序**排列的列表（最新在前，与 get_stock_kline 一致）。
    """
    seed = _make_seed(symbol)
    rng = random.Random(seed)

    # 初始价格：在 5~300 区间内由种子决定
    base_price = 5.0 + rng.random() * 295.0
    prev_close = base_price

    bars: list[dict] = []
    today = date.today()

    for td in _trading_days(_DATA_START_DATE, today):
        # 对数收益率
        daily_return = rng.gauss(mu=_DAILY_DRIFT, sigma=_DAILY_SIGMA)

        open_price = round(prev_close, 2)
        close_price = round(open_price * math.exp(daily_return), 2)

        # 价格下限保护
        if close_price < 1.0:
            close_price = 1.0

        # 日内高/低
        intraday_pct = rng.uniform(_INTRADAY_RANGE_MIN, _INTRADAY_RANGE_MAX)
        high_price = round(max(open_price, close_price) * (1.0 + rng.uniform(0, intraday_pct)), 2)
        low_price = round(min(open_price, close_price) * (1.0 - rng.uniform(0, intraday_pct)), 2)

        volume = int(rng.uniform(_VOLUME_MIN, _VOLUME_MAX))

        bars.append({
            "time": td.strftime("%Y-%m-%d"),
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
        })

        prev_close = close_price

    # 倒序：最新在前
    bars.reverse()
    return bars


# ══════════════════════════════════════════════════════════════════════
# 周线 / 月线聚合
# ══════════════════════════════════════════════════════════════════════

def _aggregate_weekly(daily_bars: list[dict]) -> list[dict]:
    """将日线（倒序）聚合为周线（倒序）。按 ISO 周分组。"""
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
            w["time"] = bar["time"]          # 最后一天的日期
            w["high"] = max(w["high"], bar["high"])
            w["low"] = min(w["low"], bar["low"])
            w["close"] = bar["close"]        # 最后一天的收盘
            w["volume"] += bar["volume"]

    result = list(weeks.values())
    result.reverse()
    return result


def _aggregate_monthly(daily_bars: list[dict]) -> list[dict]:
    """将日线（倒序）聚合为月线（倒序）。按 YYYY-MM 分组。"""
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


# ══════════════════════════════════════════════════════════════════════
# 公开：K 线数据接口
# ══════════════════════════════════════════════════════════════════════

def generate_mock_kline(symbol: str, period: str = "daily") -> list[dict]:
    """
    返回模拟 K 线数据，格式与 get_stock_kline() 完全一致。
    period: 'daily' | 'weekly' | 'monthly'
    """
    sym = symbol.lower()

    # 确保日线数据已生成
    if sym not in _daily_cache:
        _daily_cache[sym] = _generate_daily_bars(sym)

    if period == "daily":
        return _daily_cache[sym]

    if period == "weekly":
        if sym not in _weekly_cache:
            _weekly_cache[sym] = _aggregate_weekly(_daily_cache[sym])
        return _weekly_cache[sym]

    if period == "monthly":
        if sym not in _monthly_cache:
            _monthly_cache[sym] = _aggregate_monthly(_daily_cache[sym])
        return _monthly_cache[sym]

    # 未知 period 兜底
    return _daily_cache[sym]


def get_mock_stock_name(symbol: str) -> str:
    """返回模拟股票的中文名称。"""
    return f"模拟股票 {symbol.upper()}"


# ══════════════════════════════════════════════════════════════════════
# 日内 Tick 模拟引擎（有状态，每次 WebSocket 调用前进一个 tick）
# ══════════════════════════════════════════════════════════════════════

_TICKS_PER_DAY = 240               # 每个模拟交易日 240 tick（≈4 小时 × 每分钟 1 tick）
_TICK_SIGMA = 0.003                # 单 tick 对数波动率（~0.3%，价格变化更明显）
_TICK_MEAN_REVERSION = 0.06        # 均值回归强度（向 target 靠拢的速度）
_CYCLE_BAR_COUNT = 10              # 循环使用最近 10 根日线（≈两周交易日）


class _TickerState:
    """单个 mock 符号的日内 Tick 模拟状态。"""
    __slots__ = (
        'symbol', 'bars', 'bar_idx', 'tick_idx',
        'price', 'day_open', 'day_high', 'day_low', 'day_close',
        'day_time', 'session_high', 'session_low',
        'rng', 'volume_base',
    )

    def __init__(self, symbol: str, bars: list[dict]):
        self.symbol = symbol
        self.bars = bars                              # 日线列表（倒序，最新在前）
        self.rng = random.Random(_make_seed(symbol + ":tick"))
        self._start_new_day(0)                        # 从最新日线开始

    def _start_new_day(self, bar_idx: int) -> None:
        """切换到 bars[bar_idx] 这根日线，开始新一天模拟。"""
        bar = self.bars[bar_idx]
        self.bar_idx = bar_idx
        self.tick_idx = 0
        self.day_open = float(bar["open"])
        self.day_high = float(bar["high"])
        self.day_low = float(bar["low"])
        self.day_close = float(bar["close"])
        self.day_time = bar["time"]
        self.price = self.day_open           # 从开盘价起步
        self.session_high = self.day_open
        self.session_low = self.day_open
        self.volume_base = int(bar.get("volume", 10_000_000))

    def advance(self) -> dict:
        """
        前进一个 tick，返回 WebSocket 推送格式的 dict。
        使用布朗桥模型：价格在日内从 open 走向 close，同时叠加随机噪声。
        """
        if self.tick_idx >= _TICKS_PER_DAY:
            # 当天 tick 耗尽 → 切换到上一天（倒序遍历）
            next_idx = (self.bar_idx + 1) % min(len(self.bars), _CYCLE_BAR_COUNT)
            self._start_new_day(next_idx)

        progress = self.tick_idx / _TICKS_PER_DAY   # 0 → 1
        self.tick_idx += 1

        # ── 布朗桥：当前位置的期望价格 ──
        target = self.day_open + (self.day_close - self.day_open) * progress

        # 均值回归分量 + 随机噪声
        reversion = (target - self.price) * _TICK_MEAN_REVERSION
        noise = self.price * self.rng.gauss(mu=0.0, sigma=_TICK_SIGMA)

        self.price = round(self.price + reversion + noise, 2)

        # 价格下限保护
        if self.price < 0.50:
            self.price = 0.50

        # 更新日内极值
        if self.price > self.session_high:
            self.session_high = self.price
        if self.price < self.session_low:
            self.session_low = self.price

        # ── 模拟日内时间（A 股时段：9:30-11:30, 13:00-15:00）──
        total_trading = 240  # 4 小时
        elapsed = int(total_trading * progress)
        if elapsed < 120:
            # 上午 9:30-11:30
            hour = 9 + (elapsed + 30) // 60
            minute = (elapsed + 30) % 60
        else:
            # 下午 13:00-15:00
            afternoon = elapsed - 120
            hour = 13 + afternoon // 60
            minute = afternoon % 60
        sim_time = f"{self.day_time}T{hour:02d}:{minute:02d}:00"

        # ── 模拟成交量 ──
        tick_volume = int(self.volume_base * (self.tick_idx / _TICKS_PER_DAY))

        return {
            "type": "update",
            "data": {
                "time": self.day_time,   # 纯日期格式 "YYYY-MM-DD"，与 setData 格式一致
                "open": self.day_open,
                "high": round(self.session_high, 2),
                "low": round(self.session_low, 2),
                "close": self.price,
                "volume": tick_volume,
            },
        }


# 全局 ticker 状态表（symbol → _TickerState）
_ticker_states: dict[str, _TickerState] = {}


# ══════════════════════════════════════════════════════════════════════
# 公开：WebSocket 实时推送接口
# ══════════════════════════════════════════════════════════════════════

def get_mock_latest_bar(symbol: str) -> dict | None:
    """
    返回 WebSocket 推送格式的日内 tick 数据。
    每次调用前进一个 tick，价格在日内从 open 走向 close，
    叠加随机波动。当天 tick 耗尽后自动切换到下一个历史交易日。
    """
    sym = symbol.lower()

    if sym not in _daily_cache:
        _daily_cache[sym] = _generate_daily_bars(sym)

    bars = _daily_cache[sym]
    if not bars:
        return None

    # 获取或创建 ticker 状态
    if sym not in _ticker_states:
        _ticker_states[sym] = _TickerState(sym, bars)

    return _ticker_states[sym].advance()
