import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from core import models, schemas
from core.auth import get_current_user

from market_data import get_stock_kline
from mock_data import get_mock_latest_bar, is_mock_symbol
from mock_market.engine import MockPriceEngine

router = APIRouter()

_NEW_MOCK_RE = re.compile(r'^m\d{5}$', re.IGNORECASE)


def _get_current_price(symbol: str) -> float:
    """
    获取指定股票的当前市场价（服务器端权威价格）。

    模拟股票：从 MockPriceEngine / mock_data 获取实时 tick 价格。
    真实A股：从 get_stock_kline 获取最新日线收盘价（1小时缓存）。

    如果无法获取价格则抛出 HTTPException(503)。
    """
    if is_mock_symbol(symbol):
        if bool(_NEW_MOCK_RE.match(symbol)):
            engine = MockPriceEngine.get_instance()
            result = engine.get_latest_bar(symbol)
        else:
            result = get_mock_latest_bar(symbol)

        if result and result.get("data") and result["data"].get("close") is not None:
            return float(result["data"]["close"])
    else:
        data = get_stock_kline(symbol, "daily")
        if data and len(data) > 0 and data[0].get("close") is not None:
            return float(data[0]["close"])

    raise HTTPException(
        status_code=503,
        detail=f"无法获取 {symbol} 的当前市场价格，请稍后重试"
    )


@router.post("/buy")
def buy_stock(trade: schemas.TradeRequest,
              current_user: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):

    if trade.quantity <= 0:
        raise HTTPException(status_code=400, detail="数量必须大于0")

    # 服务器端获取当前市场价
    price = _get_current_price(trade.symbol)

    # 1. 计算总花费
    total_cost = price * trade.quantity

    # 2. 检查余额
    if current_user.cash_balance < total_cost:
        raise HTTPException(status_code=400, detail="余额不足")

    # 3. 扣除现金
    current_user.cash_balance -= total_cost

    # 4. 处理持仓 (Position)
    position = db.query(models.Position).filter(
        models.Position.user_id == current_user.id,
        models.Position.symbol == trade.symbol
    ).first()

    if position:
        # 如果已有持仓，更新成本价 (加权平均) 和数量
        new_total_qty = position.quantity + trade.quantity
        new_avg_cost = ((position.quantity * position.average_cost) + total_cost) / new_total_qty

        position.quantity = new_total_qty
        position.average_cost = new_avg_cost
    else:
        # 新建持仓
        new_position = models.Position(
            user_id=current_user.id,
            symbol=trade.symbol,
            quantity=trade.quantity,
            average_cost=price
        )
        db.add(new_position)

    # 5. 记录订单 (Order)
    new_order = models.Order(
        user_id=current_user.id,
        symbol=trade.symbol,
        order_type="buy",
        price=price,
        quantity=trade.quantity
    )
    db.add(new_order)

    # 6. 提交事务
    db.commit()

    return {"msg": "买入成功", "price": price, "new_balance": current_user.cash_balance}


@router.post("/sell")
def sell_stock(trade: schemas.TradeRequest,
               current_user: models.User = Depends(get_current_user),
               db: Session = Depends(get_db)):

    if trade.quantity <= 0:
        raise HTTPException(status_code=400, detail="数量必须大于0")

    # 1. 检查是否有持仓
    position = db.query(models.Position).filter(
        models.Position.user_id == current_user.id,
        models.Position.symbol == trade.symbol
    ).first()

    if not position or position.quantity < trade.quantity:
        raise HTTPException(status_code=400, detail="持仓不足")

    # 服务器端获取当前市场价
    price = _get_current_price(trade.symbol)

    # 2. 计算收入
    income = price * trade.quantity

    # 3. 增加现金
    current_user.cash_balance += income

    # 4. 更新持仓
    position.quantity -= trade.quantity

    # 如果卖光了，可以删除记录，也可以保留数量为0
    if position.quantity == 0:
        db.delete(position)

    # 5. 记录订单
    new_order = models.Order(
        user_id=current_user.id,
        symbol=trade.symbol,
        order_type="sell",
        price=price,
        quantity=trade.quantity
    )
    db.add(new_order)

    # 6. 提交事务
    db.commit()

    return {"msg": "卖出成功", "price": price, "new_balance": current_user.cash_balance}
