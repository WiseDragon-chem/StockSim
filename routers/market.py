from fastapi import APIRouter
from market_data import get_stock_kline

router = APIRouter()

@router.get("/{symbol}")
def get_market_data(symbol: str):
    data = get_stock_kline(symbol)
    return data