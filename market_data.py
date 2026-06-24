import akshare as ak
import pandas as pd
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

# 缓存配置
CACHE_DIR = Path("cache")
CACHE_EXPIRY_HOURS = 1  # 缓存过期时间（小时）

def ensure_cache_dir():
    """确保缓存目录存在"""
    CACHE_DIR.mkdir(exist_ok=True)

def get_cache_file_path(symbol: str, period: str) -> Path:
    """获取缓存文件路径"""
    return CACHE_DIR / f"{symbol}_{period}.json"

def is_cache_valid(cache_file: Path) -> bool:
    """检查缓存是否有效（未过期）"""
    if not cache_file.exists():
        return False
    
    cache_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
    expiry_time = cache_time + timedelta(hours=CACHE_EXPIRY_HOURS)
    return datetime.now() < expiry_time

def load_from_cache(symbol: str, period: str) -> list:
    """从缓存加载数据"""
    cache_file = get_cache_file_path(symbol, period)
    
    if not is_cache_valid(cache_file):
        return None
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)
            return cached_data.get('data', [])
    except Exception as e:
        print(f"缓存加载错误 {symbol}_{period}: {e}")
        return None

def save_to_cache(symbol: str, period: str, data: list):
    """保存数据到缓存"""
    ensure_cache_dir()
    cache_file = get_cache_file_path(symbol, period)
    # print(data)
    
    try:
        cache_data = {
            'symbol': symbol,
            'period': period,
            'cached_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data': data
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"缓存保存错误 {symbol}_{period}: {e}")

def get_latest_date_from_cache(symbol: str, period: str) -> str:
    """从缓存中获取最新数据日期"""
    cached_data = load_from_cache(symbol, period)
    if cached_data and len(cached_data) > 0:
        return cached_data[0]['time']  # 假设数据按时间倒序排列
    return None

def merge_data(existing_data: list, new_data: list) -> list:
    """合并现有数据和新数据（去重）"""
    if not existing_data:
        return new_data
    
    if not new_data:
        return existing_data
    
    # 创建日期映射用于去重
    existing_dates = {item['time']: item for item in existing_data}
    new_dates = {item['time']: item for item in new_data}
    
    # 合并数据，新数据优先
    merged_dates = {**existing_dates, **new_dates}
    
    # 按日期排序（最新的在前）
    merged_list = sorted(merged_dates.values(), key=lambda x: x['time'], reverse=True)
    
    return merged_list

def get_stock_kline(symbol: str, period: str = "daily"):
    """
    获取A股个股历史数据
    period: 'daily', 'weekly', 'monthly'
    """
    # 首先尝试从缓存加载
    cached_data = load_from_cache(symbol, period)
    
    if cached_data is not None:
        # 缓存有效，直接返回缓存数据
        print('访问缓存有效')
        return cached_data
    
    # 缓存无效或不存在，从API获取
    try:
        # 检查是否需要增量更新
        latest_cached_date = get_latest_date_from_cache(symbol, period)
        start_date = "20200101"  # 默认起始日期
        
        if latest_cached_date:
            # 增量更新：从缓存最新日期的下一天开始
            latest_date = datetime.strptime(latest_cached_date, '%Y-%m-%d')
            next_day = latest_date + timedelta(days=1)
            start_date = next_day.strftime('%Y%m%d')
        
        # AkShare 的 stock_zh_a_hist 完美支持 period 参数
        df = ak.stock_zh_a_hist(
            symbol=symbol, 
            period=period, 
            start_date=start_date,
            adjust="qfq"
        )
        
        if df.empty:
            # 如果没有新数据，返回现有缓存或空列表
            existing_data = load_from_cache(symbol, period) or []
            return existing_data

        # 重命名列
        df = df.rename(columns={
            "日期": "time",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close"
        })
        
        # 只需要这5列
        data = df[["time", "open", "high", "low", "close"]]
        
        # 转换为字典列表，并确保日期时间可序列化
        new_data = data.to_dict(orient="records")
        
        # 将 datetime64 对象转换为字符串
        for item in new_data:
            if isinstance(item['time'], (pd.Timestamp, datetime)):
                item['time'] = item['time'].strftime('%Y-%m-%d')
                print(type(item['time']))
        # print(new_data)
        
        # 合并新数据和现有缓存数据
        existing_data = load_from_cache(symbol, period) or []
        merged_data = merge_data(existing_data, new_data)
        
        # 保存到缓存
        save_to_cache(symbol, period, merged_data)
        
        return merged_data
        
    except Exception as e:
        print(f"AkShare Error: {e}")
        print('API调用失败尝试返回缓存数据')
        fallback_data = load_from_cache(symbol, period) or []
        return fallback_data