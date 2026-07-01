import asyncio
import datetime
import re
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from market_data import get_stock_kline
from mock_data import get_mock_latest_bar, is_mock_symbol
from mock_market.engine import MockPriceEngine

router = APIRouter()

_NEW_MOCK_RE = re.compile(r'^m\d{5}$', re.IGNORECASE)


# ── 交易日判断 ────────────────────────────────────────────────────
def is_trading_time() -> bool:
    """A股交易时间：周一至周五 9:30-11:30, 13:00-15:00"""
    now = datetime.datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    t = now.time()
    return (
        datetime.time(9, 30) <= t <= datetime.time(11, 30)
        or datetime.time(13, 0) <= t <= datetime.time(15, 0)
    )


def fetch_latest_daily_bar(symbol: str):
    """获取最新一根日K线（走缓存或引擎，不直接调 API）。"""
    if is_mock_symbol(symbol):
        if bool(_NEW_MOCK_RE.match(symbol)):
            engine = MockPriceEngine.get_instance()
            return engine.get_latest_bar(symbol)
        return get_mock_latest_bar(symbol)

    try:
        data = get_stock_kline(symbol, "daily")  # 复用 1 小时缓存
        if not data:
            return None

        latest = data[0]  # 数据按时间倒序，第一条即最新

        return {
            "type": "update",
            "data": {
                "time": latest["time"],
                "open": float(latest["open"]),
                "high": float(latest["high"]),
                "low": float(latest["low"]),
                "close": float(latest["close"]),
            },
        }
    except Exception:
        import traceback
        traceback.print_exc()
        return None


@router.websocket("/ws/mock/all")
async def websocket_all_prices(websocket: WebSocket):
    """推送所有模拟公司的当前价格（全量广播，2s 间隔）。"""
    await websocket.accept()
    print("WS 全量推送连接建立（模拟公司）")
    engine = MockPriceEngine.get_instance()

    try:
        while True:
            prices = await run_in_threadpool(engine.get_all_ticker_prices)
            if prices:
                try:
                    await websocket.send_json({
                        "type": "update_all",
                        "data": prices,
                    })
                except (WebSocketDisconnect, RuntimeError):
                    print("全量推送检测到客户端断开，停止推送")
                    break
            await asyncio.sleep(2)

    except WebSocketDisconnect:
        print("全量推送客户端主动断开")
    except Exception as e:
        print(f"全量推送 WS 未知异常: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    await websocket.accept()
    print(f"WS 连接建立: {symbol}")

    try:
        while True:
            data = await run_in_threadpool(fetch_latest_daily_bar, symbol)

            if data:
                try:
                    await websocket.send_json(data)
                except (WebSocketDisconnect, RuntimeError):
                    print(f"检测到客户端断开 ({symbol})，停止推送")
                    break

            # 交易时间每 10s 刷新，非交易时间每 60s；mock 每 2s 推 tick
            if is_mock_symbol(symbol):
                sleep_sec = 2
            else:
                sleep_sec = 10 if is_trading_time() else 60
            await asyncio.sleep(sleep_sec)

    except WebSocketDisconnect:
        print(f"客户端主动断开: {symbol}")
    except Exception as e:
        print(f"WS 未知异常: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
