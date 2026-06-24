import asyncio
import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
import akshare as ak
import pandas as pd

router = APIRouter()

def fetch_latest_daily_bar(symbol: str):
    try:
        # 1. 动态计算时间范围
        start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y%m%d")
        end_date = datetime.datetime.now().strftime("%Y%m%d")

        # 2. 获取数据
        df = ak.stock_zh_a_hist(
            symbol=symbol, 
            period="daily", 
            start_date=start_date, 
            end_date=end_date, 
            adjust="qfq"
        )
        
        if df.empty:
            return None

        # 3. 取最后一行
        latest = df.iloc[-1]
        
        # === 关键修正开始 ===
        # AkShare 返回的 '日期' 列通常是字符串 "2023-10-27" 或者 datetime.date 对象
        # 我们统一强制转换为字符串，Lightweight Charts 需要 "YYYY-MM-DD" 格式
        date_val = latest['日期']
        if isinstance(date_val, (datetime.date, datetime.datetime)):
            date_str = date_val.strftime("%Y-%m-%d")
        else:
            date_str = str(date_val) # 如果已经是字符串
        # === 关键修正结束 ===

        return {
            "type": "update", 
            "data": {
                "time": date_str,  # <--- 使用处理后的字符串
                "open": float(latest['开盘']),
                "high": float(latest['最高']),
                "low": float(latest['最低']),
                "close": float(latest['收盘']),
                "volume": int(latest['成交量']),
                "change": float(latest['涨跌幅'])
            }
        }
    except Exception as e:
        # 打印详细错误堆栈，方便调试
        import traceback
        traceback.print_exc()
        print(f"数据获取逻辑错误: {e}")
        return None

@router.websocket("/ws/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    await websocket.accept()
    print(f"WS 连接建立: {symbol}")
    
    try:
        while True:
            # 1. 获取数据 (后台线程)
            data = await run_in_threadpool(fetch_latest_daily_bar, symbol)
            
            if data:
                # 2. 尝试发送数据 (关键修改点)
                try:
                    await websocket.send_json(data)
                except (WebSocketDisconnect, RuntimeError):
                    # RuntimeError: Cannot call "send" once a close message has been sent.
                    print(f"检测到客户端断开 ({symbol})，停止推送")
                    break # <--- 必须 break 跳出 while 循环
            
            # 3. 休眠
            await asyncio.sleep(3) 

    except WebSocketDisconnect:
        print(f"客户端主动断开: {symbol}")
    except Exception as e:
        print(f"WS 未知异常: {e}")
    finally:
        # 确保资源释放
        try:
            print('free')
            await websocket.close()
        except:
            pass