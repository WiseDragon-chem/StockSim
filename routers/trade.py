from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from auth import get_current_user

router = APIRouter()

@router.post("/buy")
def buy_stock(trade: schemas.TradeRequest, 
              current_user: models.User = Depends(get_current_user), 
              db: Session = Depends(get_db)):

    if trade.price <= 0 or trade.quantity <= 0:
        raise HTTPException(status_code=400, detail="价格和数量必须大于0")
    
    # 1. 计算总花费
    total_cost = trade.price * trade.quantity
    
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
        # 新成本 = (旧数量*旧成本 + 新数量*新价格) / 总数量
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
            average_cost=trade.price
        )
        db.add(new_position)

    # 5. 记录订单 (Order)
    new_order = models.Order(
        user_id=current_user.id,
        symbol=trade.symbol,
        order_type="buy",
        price=trade.price,
        quantity=trade.quantity
    )
    db.add(new_order)

    # 6. 提交事务
    db.commit()
    
    return {"msg": "买入成功", "new_balance": current_user.cash_balance}


@router.post("/sell")
def sell_stock(trade: schemas.TradeRequest, 
               current_user: models.User = Depends(get_current_user), 
               db: Session = Depends(get_db)):
    
    # 1. 检查是否有持仓
    position = db.query(models.Position).filter(
        models.Position.user_id == current_user.id,
        models.Position.symbol == trade.symbol
    ).first()

    if not position or position.quantity < trade.quantity:
        raise HTTPException(status_code=400, detail="持仓不足")

    # 2. 计算收入
    income = trade.price * trade.quantity

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
        price=trade.price,
        quantity=trade.quantity
    )
    db.add(new_order)

    # 6. 提交事务
    db.commit()

    return {"msg": "卖出成功", "new_balance": current_user.cash_balance}