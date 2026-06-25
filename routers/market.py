import re

from fastapi import APIRouter

from market_data import get_stock_kline, get_stock_name
from mock_data import generate_mock_kline, get_mock_stock_name, is_mock_symbol
from mock_market.service import get_mock_kline as new_get_mock_kline
from mock_market.service import get_mock_company_name

router = APIRouter()

# m\d{5} 格式匹配（新 mock 公司的代码格式）
_NEW_MOCK_RE = re.compile(r'^m\d{5}$', re.IGNORECASE)


def _is_new_mock(symbol: str) -> bool:
    """判断是否为新的 mNNNNN 格式 mock 代码。"""
    return bool(_NEW_MOCK_RE.match(symbol))


@router.get("/{symbol}")
def get_market_data(symbol: str, period: str = "daily"):
    if is_mock_symbol(symbol):
        if _is_new_mock(symbol):
            return new_get_mock_kline(symbol, period)
        return generate_mock_kline(symbol, period)
    data = get_stock_kline(symbol, period)
    return data


@router.get("/{symbol}/name")
def get_stock_name_endpoint(symbol: str):
    """获取股票中文名称（7 天缓存）。"""
    if is_mock_symbol(symbol):
        if _is_new_mock(symbol):
            return {"name": get_mock_company_name(symbol)}
        return {"name": get_mock_stock_name(symbol)}
    name = get_stock_name(symbol)
    return {"name": name}
