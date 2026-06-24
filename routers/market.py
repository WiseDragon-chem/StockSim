from fastapi import APIRouter

from market_data import get_stock_kline, get_stock_name
from mock_data import generate_mock_kline, get_mock_stock_name, is_mock_symbol

router = APIRouter()


@router.get("/{symbol}")
def get_market_data(symbol: str, period: str = "daily"):
    if is_mock_symbol(symbol):
        return generate_mock_kline(symbol, period)
    data = get_stock_kline(symbol, period)
    return data


@router.get("/{symbol}/name")
def get_stock_name_endpoint(symbol: str):
    """获取股票中文名称（7 天缓存）。"""
    if is_mock_symbol(symbol):
        return {"name": get_mock_stock_name(symbol)}
    name = get_stock_name(symbol)
    return {"name": name}
