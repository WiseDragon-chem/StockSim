from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from core.database import engine, Base
from mock_market.database import init_mock_db
from mock_market.engine import MockPriceEngine
from routers import users, market, trade, ws, mock_admin

# 1. 创建数据库表 (如果不存在) —— 主 DB
Base.metadata.create_all(bind=engine)

# 2. 初始化 mock DB（建表 + 播种默认公司）
init_mock_db()


# 3.  lifespan：控制 MockPriceEngine 后台任务
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    mock_engine = MockPriceEngine.get_instance()
    await mock_engine.start()
    yield
    # 关闭
    await mock_engine.stop()


app = FastAPI(
    title="StockSim API",
    description="股票模拟交易系统API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 4. 注册路由
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(market.router, prefix="/api/market", tags=["Market"])
app.include_router(trade.router, prefix="/api/trade", tags=["Trade"])
app.include_router(ws.router, prefix="/api", tags=["WebSocket"])
app.include_router(mock_admin.router, prefix="/api/admin", tags=["Admin"])

# 5. 根路径直接返回静态页面
@app.get("/")
async def root():
    """根路径返回静态页面"""
    return FileResponse("static/index.html")

# 6. 挂载静态文件服务（用于CSS、JS等资源）
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7999)