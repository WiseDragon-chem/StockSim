"""
mock_market Pydantic schemas — 管理 API 的请求/响应模型。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════════
# 创建 / 更新
# ══════════════════════════════════════════════════════════════════════

class MockCompanyCreate(BaseModel):
    """创建模拟公司。code 和 name 必填，其余超参数使用默认值。"""
    code: str = Field(..., pattern=r"^m\d{5}$",
                      description="股票代码，格式 m00001~m99999")
    name: str = Field(..., min_length=1, max_length=50,
                      description="公司名称")
    initial_price: float = Field(default=50.0, ge=0.01, le=100000.0,
                                 description="初始价格")
    daily_drift_mu: float = Field(default=0.0002, ge=-0.05, le=0.05,
                                  description="日均对数收益率")
    daily_sigma: float = Field(default=0.02, ge=0.001, le=0.20,
                               description="日波动率")
    mean_reversion: float = Field(default=0.06, ge=0.0, le=1.0,
                                  description="均值回归强度")
    tick_sigma: float = Field(default=0.003, ge=0.0, le=0.10,
                              description="单 tick 噪声标准差")
    tick_interval_seconds: int = Field(default=30, ge=1, le=3600,
                                       description="tick 间隔（秒）")
    ticks_per_day: int = Field(default=240, ge=10, le=1440,
                               description="每天 tick 数")
    price_min: float = Field(default=0.50, ge=0.01, le=100000.0,
                             description="价格下限")
    price_max: float = Field(default=10000.0, ge=1.0, le=1000000.0,
                             description="价格上限")


class MockCompanyUpdate(BaseModel):
    """更新公司超参数（所有字段可选）。"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    initial_price: Optional[float] = Field(default=None, ge=0.01, le=100000.0)
    daily_drift_mu: Optional[float] = Field(default=None, ge=-0.05, le=0.05)
    daily_sigma: Optional[float] = Field(default=None, ge=0.001, le=0.20)
    mean_reversion: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    tick_sigma: Optional[float] = Field(default=None, ge=0.0, le=0.10)
    tick_interval_seconds: Optional[int] = Field(default=None, ge=1, le=3600)
    ticks_per_day: Optional[int] = Field(default=None, ge=10, le=1440)
    price_min: Optional[float] = Field(default=None, ge=0.01, le=100000.0)
    price_max: Optional[float] = Field(default=None, ge=1.0, le=1000000.0)
    is_active: Optional[bool] = Field(default=None)


# ══════════════════════════════════════════════════════════════════════
# 展示
# ══════════════════════════════════════════════════════════════════════

class MockCompanyDisplay(BaseModel):
    """返回给前端的公司完整信息。"""
    id: int
    code: str
    name: str
    initial_price: float
    daily_drift_mu: float
    daily_sigma: float
    mean_reversion: float
    tick_sigma: float
    tick_interval_seconds: int
    ticks_per_day: int
    price_min: float
    price_max: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MockCompanyList(BaseModel):
    """公司列表。"""
    companies: list[MockCompanyDisplay]
    total: int
