# StockSim — 股市模拟交易系统

A股模拟交易平台，使用真实的行情数据（AkShare），让用户在不投入真金白银的情况下练习股票交易。初始资金 100,000 元。

## 功能

- **用户系统** — 注册、登录、JWT 鉴权
- **K线图表** — 日K / 月K 切换，基于 Lightweight Charts（TradingView 开源版）
- **实时推送** — WebSocket 每 3 秒推送最新行情，实时更新日K
- **模拟交易** — 买入、卖出，加权平均成本计算，持仓管理
- **资产看板** — 持仓列表、现金余额、交易记录
- **行情缓存** — 本地 JSON 文件缓存（1 小时），增量更新，API 失败时自动回退

## 技术栈

| 层面 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | SQLite + SQLAlchemy ORM |
| 认证 | bcrypt + JWT (python-jose) |
| 行情数据 | AkShare（同花顺数据源） |
| 前端 | 原生 JS + Lightweight Charts CDN |
| 数据校验 | Pydantic |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python main.py
```

服务默认监听 `192.168.7.3:7999`，首次启动会自动创建 `data/sql_app.db`。

如需修改地址 / 端口，编辑 `main.py` 底部的 `uvicorn.run()` 参数。

### 3. 打开页面

浏览器访问 `http://192.168.7.3:7999`，注册账号后即可使用。

Swagger API 文档：`http://192.168.7.3:7999/docs`

## 项目结构

```
├── main.py              # 应用入口，路由注册，静态文件挂载
├── core/                # 核心数据层
│   ├── database.py      # SQLAlchemy 引擎与 Session 管理
│   ├── models.py        # ORM 模型：User / Position / Order
│   ├── schemas.py       # Pydantic 请求/响应模型
│   └── auth.py          # 密码哈希、JWT 生成与校验
├── market_data.py       # AkShare 封装 + 文件缓存
├── mock_data.py         # 模拟数据生成器
├── routers/             # API 路由
│   ├── users.py         # 注册 / 登录 / 用户信息
│   ├── market.py        # K线数据 / 股票名称
│   ├── trade.py         # 买入 / 卖出
│   ├── ws.py            # WebSocket 实时行情推送
│   └── mock_admin.py    # 模拟公司管理
├── mock_market/         # 模拟市场子系统（持久化 24/7 模拟公司）
├── static/              # 前端
│   ├── index.html       # 前端页面
│   ├── style.css        # 样式
│   └── js/              # 前端 JS 模块（6 个文件）
├── data/                # 数据库文件（已 gitignore）
├── cache/               # 行情缓存目录（已 gitignore）
├── test_cache.py        # 缓存功能测试脚本
├── requirements.txt
└── CLAUDE.md
```

## API 概览

| 方法 | 路径 | 说明 | 需登录 |
|------|------|------|--------|
| POST | `/api/users/register` | 注册 | ❌ |
| POST | `/api/users/login` | 登录（OAuth2 表单） | ❌ |
| GET | `/api/users/me` | 当前用户资产与持仓 | ✅ |
| GET | `/api/market/{symbol}` | K线数据 | ❌ |
| GET | `/api/market/{symbol}/name` | 股票中文名称 | ❌ |
| POST | `/api/trade/buy` | 买入 | ✅ |
| POST | `/api/trade/sell` | 卖出 | ✅ |
| WS | `/api/ws/{symbol}` | 实时行情推送 | ❌ |

## 注意事项

- 行情数据来自同花顺，频繁请求可能导致 IP 被封，系统已内置 1 小时缓存
- 交易价格为前端传入的当前显示价格，服务器不做价格校验
- 仅支持 A 股代码（如 `600519` 贵州茅台），不包含 `sh`/`sz` 前缀
- 实时推送仅在交易日开盘时段有数据更新
