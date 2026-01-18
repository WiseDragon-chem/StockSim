import akshare as ak
import pandas as pd

def get_stock_kline(symbol: str):
    """
    获取A股个股历史数据
    symbol: "600519" (无需加 sh/sz，AkShare stock_zh_a_hist 自动处理)
    """
    try:
        # adjust="qfq" 表示前复权，更适合看盘
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date="20230101", adjust="qfq")
        
        if df.empty:
            return []

        # 重命名为 Lightweight Charts 需要的字段
        # AkShare 返回列名通常为中文
        df = df.rename(columns={
            "日期": "time",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close"
        })
        
        # 只需要这5列
        data = df[["time", "open", "high", "low", "close"]]
        
        # 转换为字典列表
        return data.to_dict(orient="records")
    except Exception as e:
        print(f"AkShare Error: {e}")
        return []