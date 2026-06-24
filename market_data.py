import os
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import akshare as ak
import pandas as pd
import requests

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

def _convert_item(item: dict) -> dict:
    """将 DataFrame 转换后的字典中的 numpy 类型转为原生 Python 类型，确保 JSON 可序列化。"""
    for key, val in item.items():
        # NaN 必须最先检查 — numpy NaN 同时满足 floating 和 isna，需优先转为 None
        if pd.isna(val):
            item[key] = None
        elif isinstance(val, (pd.Timestamp, datetime)):
            item[key] = val.strftime('%Y-%m-%d')
        elif isinstance(val, (np.floating,)):
            item[key] = float(val)
        elif isinstance(val, (np.integer,)):
            item[key] = int(val)
    return item


# ── 数据源（直连东方财富 API，绕过系统代理）──────────────────────
_EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_PERIOD_TO_KLT = {"daily": 101, "weekly": 102, "monthly": 103}
NAME_CACHE_EXPIRY_DAYS = 7
# 直连 API 不使用系统代理
_REQ_PROXIES = {"http": None, "https": None}


def _get_secid(symbol: str) -> str:
    """A 股代码 → 东方财富 secid（1.xxx = 沪市, 0.xxx = 深市）。"""
    if symbol[:1] in ("5", "6", "9"):
        return f"1.{symbol}"
    return f"0.{symbol}"


def _fetch_kline_eastmoney(symbol: str, period: str, start_date: str):
    """用 requests 直连东方财富 K 线 API，绕过代理。"""
    klt = _PERIOD_TO_KLT.get(period, 101)
    end_date = datetime.now().strftime("%Y%m%d")
    secid = _get_secid(symbol)

    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": klt,
        "fqt": 1,
        "secid": secid,
        "beg": start_date,
        "end": end_date,
    }

    r = requests.get(_EASTMONEY_KLINE_URL, params=params, timeout=30, proxies=_REQ_PROXIES)
    r.raise_for_status()
    body = r.json()

    if body.get("rc") != 0 or body.get("data") is None:
        return None

    klines = body["data"].get("klines", [])
    if not klines:
        return None

    # klines 格式: "2025-06-03,1456.45,1457.15,..." (date, open, close, high, low, vol, amount)
    rows = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 5:
            continue
        rows.append({
            "time": parts[0],
            "open": float(parts[1]),
            "close": float(parts[2]),
            "high": float(parts[3]),
            "low": float(parts[4]),
        })

    return pd.DataFrame(rows)


def _fetch_kline_akshare(symbol: str, period: str, start_date: str):
    """AkShare（备用源）。"""
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period=period,
        start_date=start_date,
        adjust="qfq",
    )
    if df.empty:
        return None
    df = df.rename(columns={
        "日期": "time",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
    })
    return df[["time", "open", "high", "low", "close"]]


def _fetch_kline(symbol: str, period: str, start_date: str):
    """先东方财富直连，后 AkShare；都失败返回 None。"""
    for name, fetcher in [
        ("eastmoney", _fetch_kline_eastmoney),
        ("akshare", _fetch_kline_akshare),
    ]:
        try:
            df = fetcher(symbol, period, start_date)
            if df is not None:
                print(f"  数据源: {name}")
                return df
        except Exception as e:
            print(f"  {name} 获取失败: {e}")
    return None


def get_stock_name(symbol: str) -> str:
    """获取股票中文名称（7 天缓存，直连东方财富 API）。"""
    cache_file = CACHE_DIR / f"{symbol}_name.json"

    # 1. 缓存命中
    if cache_file.exists():
        cache_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - cache_time < timedelta(days=NAME_CACHE_EXPIRY_DAYS):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f).get("name", "未知股票")
            except Exception:
                pass

    # 2. 从东方财富 K 线接口取名称（只取 1 天数据，响应极小）
    try:
        secid = _get_secid(symbol)
        today = datetime.now().strftime("%Y%m%d")
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "klt": 101,
            "fqt": 1,
            "secid": secid,
            "beg": today,
            "end": today,
        }
        r = requests.get(_EASTMONEY_KLINE_URL, params=params, timeout=10, proxies=_REQ_PROXIES)
        r.raise_for_status()
        body = r.json()
        name = body.get("data", {}).get("name", "")
        if name:
            _save_name_cache(cache_file, symbol, name)
            return name
    except Exception as e:
        print(f"  eastmoney 名称获取失败: {e}")

    # 3. 回退 AkShare
    try:
        stock_info = ak.stock_individual_info_em(symbol=symbol)
        if not stock_info.empty:
            name_row = stock_info[stock_info["item"] == "股票简称"]
            if not name_row.empty:
                name = str(name_row["value"].iloc[0])
                _save_name_cache(cache_file, symbol, name)
                return name
    except Exception as e:
        print(f"  akshare 名称获取失败: {e}")

    return "未知股票"


def _save_name_cache(cache_file: Path, symbol: str, name: str):
    """写入名称缓存文件。"""
    ensure_cache_dir()
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(
                {"symbol": symbol, "name": name, "cached_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
                f,
                ensure_ascii=False,
            )
    except Exception as e:
        print(f"名称缓存写入失败: {e}")


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
        
        # 使用双数据源获取（efinance 优先，AkShare 备用）
        df = _fetch_kline(symbol, period, start_date)

        if df is None or df.empty:
            # 如果没有新数据，返回现有缓存或空列表
            existing_data = load_from_cache(symbol, period) or []
            return existing_data

        # 转换为字典列表
        new_data = df.to_dict(orient="records")

        # 将所有 numpy 类型转为原生 Python 类型（确保 JSON 可序列化）
        new_data = [_convert_item(item) for item in new_data]
        # 按日期倒序（最新在前），保证缓存数据顺序一致
        new_data.sort(key=lambda x: x["time"], reverse=True)
        
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