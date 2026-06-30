# StockSim — 股市模拟交易系统

一个 **A 股模拟交易平台**，支持真实 A 股行情和 24/7 内置模拟公司，用虚拟资金练习买卖。初始资金 **100,000 元**。

## 主要功能

- 🏭 **模拟公司** — 10 家内置公司（星辰科技、深海能源…），24/7 实时价格引擎，永不收盘
- 📊 **真实 A 股** — 接入东方财富行情，支持任意 A 股代码查询
- 📈 **K 线图表** — 蜡烛图 + MA5/MA10/MA20 均线 + 成交量柱，悬浮查看 OHLCV 明细
- 💰 **模拟交易** — 买入/卖出，加权平均成本，实时计算盈亏
- 🔄 **实时推送** — WebSocket 推送行情，价格和盈亏自动刷新
- 👤 **用户系统** — 注册/登录，JWT 鉴权，持仓与资产看板

## 快速开始

```bash
pip install -r requirements.txt   # 安装依赖
python main.py                     # 启动服务 → http://127.0.0.1:7999
```

首次启动自动创建数据库。打开浏览器注册账号即可使用。详细教程见 `/help` 页面。

## 技术栈

**后端：** FastAPI + SQLite + SQLAlchemy + AkShare + JWT  
**前端：** 原生 JavaScript + Lightweight Charts（CDN），无框架无构建  
**模拟引擎：** 布朗桥价格模型，独立 SQLite 持久化，崩溃恢复

## 项目结构

```
├── main.py              # 入口，路由注册，教程编译
├── core/                # 数据层（DB、ORM、Schema、Auth）
├── routers/             # API 路由（users、market、trade、ws、mock_admin）
├── mock_market/         # 模拟市场子系统（引擎、模型、管理 API）
├── market_data.py       # AkShare 封装 + 文件缓存
├── static/              # 前端 SPA（index.html + 6 JS 模块）
├── docs/                # 教程文档（tutorial.md）
├── data/ cache/         # 数据库 & 行情缓存（gitignore）
└── requirements.txt
```

## API 速览

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/users/register` | 注册 | — |
| POST | `/api/users/login` | 登录 | — |
| GET | `/api/users/me` | 用户资产与持仓 | JWT |
| GET | `/api/market/{symbol}` | K 线数据 | — |
| POST | `/api/trade/buy` | 买入 | JWT |
| POST | `/api/trade/sell` | 卖出 | JWT |
| WS | `/api/ws/{symbol}` | 实时行情推送 | — |
| GET | `/api/admin/companies` | 模拟公司列表 | — |
