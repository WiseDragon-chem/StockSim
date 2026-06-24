from fastapi import APIRouter
import akshare as ak
from market_data import get_stock_kline

router = APIRouter()

# 增加 period 参数，默认值 "daily"
@router.get("/{symbol}")
def get_market_data(symbol: str, period: str = "daily"):
    # 将 period 传给数据获取函数
    data = get_stock_kline(symbol, period)
    return data

@router.get("/{symbol}/name")
def get_stock_name(symbol: str):
    """获取股票中文名称"""
    try:
        # 使用 AkShare 获取股票基本信息
        stock_info = ak.stock_individual_info_em(symbol=symbol)
        if stock_info.empty:
            return {"name": "未知股票"}
        
        # 查找股票名称
        name_row = stock_info[stock_info["item"] == "股票简称"]
        if not name_row.empty:
            stock_name = name_row["value"].iloc[0]
            return {"name": stock_name}
        else:
            return {"name": "未知股票"}
    except Exception as e:
        print(f"获取股票名称错误 {symbol}: {e}")
        return {"name": "未知股票"}