这是一个非常棒的入门全栈练手项目。结合了现代Web框架（FastAPI）、金融数据处理（AkShare）、数据库操作（SQLite）以及数据可视化（Lightweight Charts）。

我为你规划了详细的项目架构和开发文档，分为 **技术选型**、**项目结构**、**数据库设计**、**核心逻辑** 和 **开发步骤** 五个部分。

> **📝 实际实现说明**：以下为原始设计文档。实际代码已做如下调整：
> - 核心模块（database/models/schemas/auth）已移入 `core/` 包
> - 空壳文件 `config.py` 和 `crud.py` 已删除
> - 数据库文件移入 `data/` 目录
> - 前端 JS 拆分为 `static/js/` 下的 6 个功能模块
> - 新增 `mock_market/` 子系统（10 家持久化 24/7 模拟公司）

---

### 一、 技术选型与工具链

*   **后端框架**: **FastAPI**
    *   *理由*: 比Flask性能更高（原生支持异步），自带API文档（Swagger UI），结合Pydantic的数据验证非常适合处理交易逻辑。
*   **数据库**: **SQLite** + **SQLAlchemy**
    *   *理由*: SQLite无需配置服务器，单文件存储；SQLAlchemy是Python最流行的ORM，方便操作数据库。
*   **数据源**: **AkShare**
    *   *理由*: 开源免费，接口丰富，特别适合获取A股历史行情数据。
*   **前端**: **HTML/JS** + **Lightweight Charts** (TradingView开源)
    *   *理由*: 轻量级，专门用于金融K线图展示，交互流畅。
*   **认证**: **JWT (JSON Web Tokens)** + **Passlib**
    *   *理由*: 无状态认证，标准的安全做法。

---

### 二、 项目目录结构

建议采用如下结构，保持代码清晰：

```text
stock_sim/
├── main.py                  # 项目入口
├── config.py                # 配置信息 (密钥等)
├── database.py              # 数据库连接与Session管理
├── models.py                # 数据库表模型 (User, Position, Order)
├── schemas.py               # Pydantic模型 (用于数据传输/验证)
├── crud.py                  # 数据库增删改查操作
├── auth.py                  # 登录认证逻辑 (Hash密码, JWT生成)
├── market_data.py           # AkShare 数据获取封装
├── routers/                 # API 路由
│   ├── users.py             # 用户注册/登录
│   ├── market.py            # 股市数据接口
│   └── trade.py             # 交易接口
├── static/                  # 静态文件 (前端)
│   ├── index.html           # 主页
│   └── app.js               # 前端逻辑
└── requirements.txt         # 依赖列表
```

**requirements.txt 内容:**
```text
fastapi
uvicorn
sqlalchemy
pydantic
passlib[bcrypt]
python-jose[cryptography]
python-multipart
akshare
pandas
```

---

### 三、 数据库设计 (models.py)

我们需要三张核心表：用户表、持仓表、交易记录表。

1.  **Users (用户表)**
    *   `id`: Integer, Primary Key
    *   `username`: String, Unique
    *   `hashed_password`: String
    *   `cash_balance`: Float (当前可用现金，初始如 100,000)

2.  **Positions (持仓表 - 用户当前拥有的股票)**
    *   `id`: Integer, Primary Key
    *   `user_id`: ForeignKey(Users.id)
    *   `symbol`: String (股票代码，如 "sh600519")
    *   `quantity`: Integer (持股数量)
    *   `average_cost`: Float (持仓成本价)

3.  **Orders (交易记录表)**
    *   `id`: Integer, Primary Key
    *   `user_id`: ForeignKey(Users.id)
    *   `symbol`: String
    *   `order_type`: String ("buy" 或 "sell")
    *   `price`: Float (成交价)
    *   `quantity`: Integer (成交数量)
    *   `timestamp`: DateTime

---

### 四、 核心功能逻辑开发指南

#### 1. 初始化数据库 (database.py)
使用 SQLAlchemy 创建 SQLite 连接。

```python
# database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./data/sql_app.db"

# check_same_thread=False 是 SQLite 在 FastAPI 多线程下的特殊配置
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

#### 2. 获取股市数据 (market_data.py)
AkShare 返回的是 Pandas DataFrame，需要转换为 Lightweight Charts 接受的 JSON 格式（List of Dictionaries）。

*Lightweight Charts 格式要求*: `[{ time: '2023-01-01', open: 10, high: 12, low: 9, close: 11 }]`

```python
# market_data.py
import akshare as ak
import json

def get_stock_history(symbol: str):
    # 示例：获取 A 股个股历史数据 (以前复权为例)
    # 注意：AkShare 的代码通常不需要 'sh'/'sz' 前缀，或者具体函数有具体要求，需查阅文档
    # 这里假设 symbol 传入 "600519"
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date="20230101", adjust="qfq")
        # 重命名列以适配前端图表
        df = df.rename(columns={
            "日期": "time",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume"
        })
        # 只需要这几列
        df = df[["time", "open", "high", "low", "close"]]
        return df.to_dict(orient="records")
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []
```

#### 3. 交易逻辑 (routers/trade.py)
这是后端最复杂的部分。

*   **买入 (Buy):**
    1.  获取用户当前现金 `cash_balance`。
    2.  计算总花费 `cost = price * quantity`。
    3.  判断 `cash_balance >= cost`？
    4.  如果够：
        *   扣除用户现金。
        *   查询 `Positions` 表：
            *   如果有该股，更新 `quantity` 和 `average_cost`。
            *   如果没有，创建新记录。
        *   记录到 `Orders` 表。
        *   Commit 事务。

*   **卖出 (Sell):**
    1.  查询 `Positions` 表看用户是否持有该股。
    2.  判断持仓数量 `holding_quantity >= sell_quantity`？
    3.  如果够：
        *   计算收入 `income = price * quantity`。
        *   增加用户现金。
        *   减少持仓数量（如果减为0，可以删除记录）。
        *   记录到 `Orders` 表。
        *   Commit 事务。

#### 4. 前端集成 (static/index.html + app.js)

在 `index.html` 中引入 Lightweight Charts CDN：
```html
<script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
```

在 `app.js` 中渲染图表：
```javascript
// 初始化图表
const chart = LightweightCharts.createChart(document.body, { width: 800, height: 400 });
const candlestickSeries = chart.addCandlestickSeries();

// 获取数据
async function loadMarketData(symbol) {
    const response = await fetch(`/api/market/${symbol}`);
    const data = await response.json();
    candlestickSeries.setData(data);
}
```

---

### 五、 开发步骤执行清单

#### 第一阶段：基础设施搭建
1.  安装 Python 环境和 `requirements.txt` 中的库。
2.  编写 `database.py` 和 `models.py`。
3.  在 `main.py` 中编写 `Base.metadata.create_all(bind=engine)` 以自动创建 SQLite 数据库文件。

#### 第二阶段：用户系统
1.  编写 `auth.py`：实现密码 Hash (bcrypt) 和 JWT Token 生成/解析。
2.  编写 `routers/users.py`：
    *   `POST /register`: 创建用户，初始资金设为 100,000。
    *   `POST /login`: 返回 access_token。
    *   `GET /users/me`: 获取当前用户信息（包含余额）。

#### 第三阶段：行情展示
1.  编写 `market_data.py` 对接 AkShare。
2.  编写 `routers/market.py`：
    *   `GET /market/{symbol}`: 调用 AkShare，返回清洗后的 JSON 数据。
3.  编写简单的前端页面，输入股票代码，显示 K 线图。

#### 第四阶段：交易系统
1.  编写 `routers/trade.py`：
    *   需要依赖 `auth.py` 中的 `get_current_user` 确保只有登录用户能交易。
    *   实现 `POST /trade/buy` 和 `POST /trade/sell`。
    *   接口入参建议使用 Pydantic 模型：`class TradeOrder(BaseModel): symbol: str, price: float, quantity: int`。
    *   **注意**: 真实场景下价格应该由后端获取当前市价，但在模拟学习系统中，你可以允许前端传入当前价格（或者后端再次请求 AkShare 获取最新价作为成交价）。

#### 第五阶段：前端整合
1.  构建一个简单的 Dashboard 页面。
2.  左侧：账户信息（现金余额、持仓列表）。
3.  右侧：K线图 + 买卖操作面板（输入框：代码、数量、买/卖按钮）。
4.  使用 AJAX/Fetch 与后端 API 交互。

### 示例代码片段：FastAPI 主入口 (main.py)

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from core.database import engine, Base
from routers import users, market, trade

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI()

# 注册路由
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(trade.router, prefix="/api/trade", tags=["trade"])

# 挂载静态文件 (前端页面)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

### 提示与建议

1.  **数据延迟**: AkShare 获取数据是爬虫原理，可能需要几秒钟。建议在获取数据时加上简单的缓存（例如使用 `functools.lru_cache` 或者存入 Redis/数据库），避免用户频繁刷新导致接口被封或响应过慢。
2.  **股票代码**: A股代码在 AkShare 通常是 "600519" 这种格式，但在绘图库里可能不需要区分。确保前端传给后端的代码格式统一。
3.  **安全性**: 虽然是模拟盘，但密码一定要 Hash 存储，不要明文存数据库。
4.  **资产计算**: 在 `/users/me` 接口返回时，除了返回现金，最好遍历用户的持仓，获取当前最新价，计算一下 **总资产 (Total Equity)** = 现金 + 持仓市值，这样用户体验更好。

按照这个文档一步步来，你就能完成一个功能闭环的股市模拟系统了！加油！