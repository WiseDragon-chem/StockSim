from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from routers import users, market, trade

# 1. 创建数据库表 (如果不存在)
Base.metadata.create_all(bind=engine)

app = FastAPI()

# 2. 注册路由
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(market.router, prefix="/api/market", tags=["Market"])
app.include_router(trade.router, prefix="/api/trade", tags=["Trade"])

# 3. 挂载静态文件 (前端)
# 确保你项目根目录下有一个叫 static 的文件夹，里面放 index.html
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)