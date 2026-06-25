# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server (listens on 192.168.7.3:7999)
python main.py

# Run the cache test
python test_cache.py

# Dev: run with auto-reload
uvicorn main:app --host 192.168.7.3 --port 7999 --reload
```

API docs are auto-generated at `http://<host>:7999/docs` (Swagger UI) and `/redoc`.

## Architecture Overview

This is a **Chinese A-share stock market simulator** — a fullstack FastAPI + vanilla JS SPA that lets users register, browse real stock data via AkShare, and simulate buy/sell trades with fake money.

### Backend: FastAPI + SQLite + AkShare

**Data flow:** AkShare (web-scraped A-share data) → `market_data.py` (with JSON file cache) → routers → JSON responses → frontend (Lightweight Charts candlestick chart).

**Layers:**
| File | Role |
|---|---|
| `main.py` | App factory, lifespan (starts WebSocket price updater), route registration, static file mount |
| `core/database.py` | SQLAlchemy engine/session/Base — SQLite at `data/sql_app.db`, `check_same_thread=False` for FastAPI async |
| `core/models.py` | 3 ORM tables: `User` (cash_balance default 100k), `Position` (per-symbol holdings), `Order` (trade audit log) |
| `core/schemas.py` | Pydantic request/response models — `TradeRequest`, `UserDisplay` (nests `PositionDisplay`), `OrderDisplay` |
| `core/auth.py` | bcrypt password hashing + JWT (HS256, 30min expiry); `get_current_user` is the Depends callable that protects trade routes |
| `market_data.py` | AkShare wrapper: fetches `stock_zh_a_hist`, caches to `cache/{symbol}_{period}.json` (1h expiry), incremental update + merge, fallback to stale cache on API failure |
| `routers/users.py` | POST `/register`, POST `/login` (OAuth2 form, returns JWT), GET `/me` |
| `routers/market.py` | GET `/{symbol}` (K-line, `?period=daily|weekly|monthly`), GET `/{symbol}/name` (stock Chinese name from `stock_individual_info_em`) |
| `routers/trade.py` | POST `/buy`, POST `/sell` — weighted average cost on buy, deletes Position row when quantity reaches 0 on sell |
| `routers/ws.py` | WebSocket at `/ws/{symbol}` — pushes latest daily bar every 3s; frontend updates the candlestick chart in real-time |

### Frontend: Single HTML + vanilla JS + Lightweight Charts

`static/index.html` loads Lightweight Charts from CDN and split JS modules from `static/js/`. No build step, no framework.

**UI sections:** login/register header → left chart area → right sidebar (symbol lookup, trade panel, period toggle) → bottom dashboard (positions table + cash balance).

**State flow in frontend JS modules (`static/js/`):**
- `token` stored in `localStorage`; auto-login on page load via `/api/users/me`
- `currentPrice` is set by the last K-line's close — used as the trade execution price (frontend-determined price)
- WebSocket lifecycle: manual connect button → 3s push cycle → updates `candlestickSeries.update()` (daily only) + price panel
- `refreshAccount()` called after login and after every buy/sell to re-render the position table

### Key Design Decisions & Gotchas

- **Trade price is frontend-supplied**, not locked by the server. The `TradeRequest` schema accepts `price` from the client — this is intentional for a simulator but means the server trusts the client on price.
- **`routers/` has no `__init__.py`** — relies on implicit namespace packages (Python 3.3+).
- **`config.py` and `crud.py` have been deleted** — they were empty stubs from the original design; all logic now lives in `core/` or inline in routers.
- **`main.py:12` imports `price_updater` from `routers.ws` but `routers/ws.py` doesn't define it** — this will crash at startup if the lifespan runs. Either implement the function or remove the lifespan block.
- **SQLite + concurrent access**: `check_same_thread=False` is required; writes from multiple requests need `SessionLocal` per-request (the `get_db` dependency handles this).
- **AkShare rate-limiting**: the guide warns users not to query too fast or the upstream (同花顺) will block the IP. The 1h cache is partly to mitigate this.
- **bcrypt password truncation**: `core/auth.py:23` in users router truncates passwords to 72 chars for bcrypt compatibility (`user.password[:72]`).
- **Candlestick colors are inverted vs Western convention**: red = up (China), green = down — matching Chinese market display norms.
