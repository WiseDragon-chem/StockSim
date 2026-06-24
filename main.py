from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import engine, Base
from routers import users, market, trade, ws
import asyncio
from contextlib import asynccontextmanager
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    from routers.ws import price_updater
    asyncio.create_task(price_updater())
    yield

# 1. 创建数据库表 (如果不存在)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="StockSim API",
    description="股票模拟交易系统API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 2. 注册路由
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(market.router, prefix="/api/market", tags=["Market"])
app.include_router(trade.router, prefix="/api/trade", tags=["Trade"])
app.include_router(ws.router, prefix="/api", tags=["WebSocket"])

# 3. 根路径直接返回静态页面
@app.get("/")
async def root():
    """根路径返回静态页面"""
    return FileResponse("static/index.html")

# 4. 挂载静态文件服务（用于CSS、JS等资源）
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="192.168.7.3", port=7999)