# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server (listens on 127.0.0.1:7999)
python main.py

# Dev: run with auto-reload
uvicorn main:app --host 127.0.0.1 --port 7999 --reload
```

API docs are auto-generated at `http://<host>:7999/docs` (Swagger UI) and `/redoc`.
User tutorial (rendered from `docs/tutorial.md`) is served at `/help`.

## Architecture Overview

A **Chinese A-share stock market simulator** — Fullstack FastAPI + vanilla JS SPA. Users register, browse real A-share data via AkShare or 24/7 mock companies, and simulate buy/sell trades with virtual money. Initial cash: 100,000 ¥.

### Backend: FastAPI + SQLite + AkShare + Mock Engine

**Data flow:** AkShare / MockPriceEngine → `market_data.py` / `mock_market/` (with JSON cache) → routers → JSON → frontend (Lightweight Charts with MA lines + volume histogram).

**Layers:**

| File / Package | Role |
|---|---|
| `main.py` | App factory, lifespan (MockPriceEngine start/stop), route registration, `/help` page builder, static mount |
| `core/database.py` | SQLAlchemy engine/session/Base — SQLite `data/sql_app.db`, `check_same_thread=False` |
| `core/models.py` | ORM: `User` (cash 100k default), `Position` (per-symbol), `Order` (trade log) |
| `core/schemas.py` | Pydantic: `TradeRequest`, `UserDisplay`, `PositionDisplay`, `OrderDisplay` |
| `core/auth.py` | bcrypt + JWT (HS256, 30min); `get_current_user` dependency |
| `market_data.py` | AkShare wrapper: fetches A-share history, caches to `cache/{symbol}_{period}.json` (1h), incremental merge, stale-cache fallback |
| `routers/users.py` | POST `/register`, POST `/login`, GET `/me` |
| `routers/market.py` | GET `/{symbol}` (K-line, `?period=daily|weekly|monthly`), GET `/{symbol}/name` |
| `routers/trade.py` | POST `/buy`, POST `/sell` — weighted avg cost on buy, delete Position at qty 0 |
| `routers/ws.py` | WebSocket `/ws/{symbol}` — mock 2s push, real A-shares 10s/60s (trading/non-trading) |
| `routers/mock_admin.py` | Full CRUD for mock companies at `/api/admin/companies` |
| `mock_market/` | Standalone subsystem: own SQLite DB, Brownian bridge price engine, 10 default companies |
| `mock_market/schemas.py` | Pydantic schemas with relaxed limits: `ticks_per_day ≤ 86400`, `tick_sigma ≤ 0.30` |
| `docs/tutorial.md` | Markdown user guide; auto-converted to `static/help.html` at startup via `markdown` pkg |

### Frontend: SPA with vanilla JS + Lightweight Charts

`static/index.html` loads Lightweight Charts from CDN and 6 JS modules. No build step, no framework.

**UI layout:** top bar (logo, tutorial btn, login/assets) → tab bar (模拟公司 / 实时A股 / 我的资产) → sidebar + chart area → bottom trade bar.

**Chart features:** candlestick series, MA5/MA10/MA20 line overlays, volume histogram (separate pane), crosshair tooltip with OHLCV details.

**JS modules (`static/js/`):**

| File | Purpose |
|---|---|
| `app.js` | Global state (token, currentPrice, chart series), DOMContentLoaded init, tab switching, mock company sidebar, guide modal |
| `auth.js` | Login modal (unified login/register tabs), autoLogin, logout, top-bar UI update |
| `account.js` | `refreshAccount()` — fetches positions + names + prices, calculates P&L and total assets; `updatePositionPrice()` for real-time WS updates; `positionCache` for fast recalculation |
| `chart.js` | `loadChart()`, `switchPeriod()`, `updatePriceUI()`, `calcSMA()`, `setupChartTooltip()` |
| `trading.js` | `buy()`, `sell()`, `trade()` — validates token/price/qty, immediately updates top-bar cash after trade |
| `websocket.js` | `connectWebSocket()` (toggle), heartbeat, `onmessage` updates `currentPrice` global + chart series + price UI + P&L |

**Key chart globals:** `chartInstance`, `candlestickSeries`, `ma5Series`, `ma10Series`, `ma20Series`, `volumeSeries`.

### Key Design Decisions & Gotchas

- **Trade price is server-authoritative.** The server fetches the current market price from `MockPriceEngine` (mock) or `get_stock_kline` (real A-shares) at trade time. The client no longer sends a price.
- **`routers/` has no `__init__.py`** — implicit namespace packages (Python 3.3+).
- **SQLite + async**: `check_same_thread=False`. Use `SessionLocal` per-request (`get_db` dependency).
- **AkShare rate-limiting**: don't query too fast or 同花顺 blocks the IP. 1h cache mitigates this.
- **bcrypt truncation**: `core/auth.py` truncates passwords to 72 chars (`user.password[:72]`).
- **Candlestick colors (Chinese convention)**: red = up, green = down.
- **Mock engine tick flow**: `simulated_day = ticks_per_day × tick_interval_seconds` real seconds. Schema allows up to 86400 ticks/day for 1:1 real-time simulation.
- **MA lines + volume** are computed client-side from K-line data; `calcSMA()` in chart.js.
- **P&L updates in real-time**: WebSocket `onmessage` calls `updatePositionPrice()` to refresh the assets table without a full `refreshAccount()` fetch.
- **`/help` page** is auto-generated at startup from `docs/tutorial.md` using Python `markdown` with tables/fenced_code/toc extensions.
