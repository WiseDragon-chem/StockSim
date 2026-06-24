from fastapi import APIRouter

from market_data import get_stock_kline, get_stock_name

router = APIRouter()


@router.get("/{symbol}")
def get_market_data(symbol: str, period: str = "daily"):
    data = get_stock_kline(symbol, period)
    return data


@router.get("/{symbol}/name")
def get_stock_name_endpoint(symbol: str):
    """获取股票中文名称（7 天缓存）。"""
    name = get_stock_name(symbol)
    return {"name": name}
