from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    # 初始资金设为 100,000
    cash_balance = Column(Float, default=100000.0)

    positions = relationship("Position", back_populates="owner")
    orders = relationship("Order", back_populates="owner")

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    symbol = Column(String, index=True) # 股票代码，如 "600519"
    quantity = Column(Integer)          # 持股数量
    average_cost = Column(Float)        # 持仓成本均价

    owner = relationship("User", back_populates="positions")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    symbol = Column(String)
    order_type = Column(String) # "buy" or "sell"
    price = Column(Float)       # 成交单价
    quantity = Column(Integer)  # 成交数量
    timestamp = Column(DateTime, default=datetime.datetime.now)

    owner = relationship("User", back_populates="orders")