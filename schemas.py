from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class TradeRequest(BaseModel):
    symbol: str
    price: float  # 模拟交易允许前端传入当前价格
    quantity: int

class PositionDisplay(BaseModel):
    symbol: str
    quantity: int
    average_cost: float
    class Config:
        from_attributes = True


class UserDisplay(UserBase):
    id: int
    cash_balance: float
    positions: List[PositionDisplay] = [] 
    class Config:
        from_attributes = True # 兼容 SQLAlchemy 对象

class OrderDisplay(BaseModel):
    id: int
    symbol: str
    order_type: str
    price: float
    quantity: int
    timestamp: datetime
    class Config:
        from_attributes = True
