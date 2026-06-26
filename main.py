import os
from contextlib import asynccontextmanager

import markdown
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

# 5. 编译教程 Markdown → HTML（启动时执行一次）
def build_help_page():
    """将 docs/tutorial.md 转换为 static/help.html。"""
    md_path = os.path.join(os.path.dirname(__file__), "docs", "tutorial.md")
    html_path = os.path.join(os.path.dirname(__file__), "static", "help.html")
    if not os.path.exists(md_path):
        return
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc"])
    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>StockSim 使用教程</title>
<link rel="stylesheet" href="style.css">
<style>
  body {{ background: var(--bg); }}
  .tutorial-wrapper {{
    max-width: 820px;
    margin: 0 auto;
    padding: 32px 24px 64px;
  }}
  .tutorial-wrapper h1 {{ font-size: 28px; color: var(--primary); margin-bottom: 8px; }}
  .tutorial-wrapper h2 {{
    font-size: 20px; color: var(--text); margin-top: 36px; margin-bottom: 12px;
    padding-bottom: 6px; border-bottom: 2px solid var(--border);
  }}
  .tutorial-wrapper h3 {{ font-size: 16px; color: var(--text); margin-top: 24px; }}
  .tutorial-wrapper p {{ line-height: 1.8; color: var(--text); }}
  .tutorial-wrapper ul, .tutorial-wrapper ol {{ line-height: 1.8; padding-left: 24px; }}
  .tutorial-wrapper li {{ margin-bottom: 4px; }}
  .tutorial-wrapper table {{
    width: 100%; border-collapse: collapse; margin: 12px 0;
  }}
  .tutorial-wrapper th {{
    background: var(--border-light); padding: 8px 12px; text-align: left;
    font-size: 13px; font-weight: 600; color: var(--text-secondary);
  }}
  .tutorial-wrapper td {{
    padding: 8px 12px; border-bottom: 1px solid var(--border-light); font-size: 14px;
  }}
  .tutorial-wrapper code {{
    background: var(--border-light); padding: 2px 6px; border-radius: 4px;
    font-family: 'Consolas', 'Courier New', monospace; font-size: 13px;
  }}
  .tutorial-wrapper pre {{
    background: #f5f5f5; padding: 14px 18px; border-radius: 6px;
    overflow-x: auto; font-size: 13px; line-height: 1.6;
  }}
  .tutorial-wrapper blockquote {{
    border-left: 3px solid var(--primary); margin: 12px 0;
    padding: 8px 16px; background: var(--primary-light);
    border-radius: 0 6px 6px 0; color: var(--text-secondary); font-size: 14px;
  }}
  .tutorial-wrapper hr {{ border: none; border-top: 1px solid var(--border); margin: 32px 0; }}
  .tutorial-wrapper strong {{ color: var(--text); }}
  .tutorial-wrapper a {{ color: var(--primary); }}
  .back-link {{
    display: inline-block; margin-bottom: 20px; color: var(--primary);
    text-decoration: none; font-size: 14px;
  }}
  .back-link:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="tutorial-wrapper">
  <a href="/" class="back-link">← 返回 StockSim</a>
  {body}
</div>
</body>
</html>"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

build_help_page()

@app.get("/help")
async def help_page():
    """教程页面"""
    return FileResponse("static/help.html")

# 6. 根路径直接返回静态页面
@app.get("/")
async def root():
    """根路径返回静态页面"""
    return FileResponse("static/index.html")

# 6. 挂载静态文件服务（用于CSS、JS等资源）
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7999)