"""
测试 market_data.py 的缓存功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from market_data import get_stock_kline
import time

def test_cache_functionality():
    """测试缓存功能"""
    print("=== 测试股票数据缓存功能 ===")
    
    # 测试股票代码和周期
    symbol = "000001"  # 平安银行
    period = "daily"
    
    print(f"\n1. 第一次获取数据（应该调用API）...")
    start_time = time.time()
    data1 = get_stock_kline(symbol, period)
    elapsed1 = time.time() - start_time
    print(f"   获取到 {len(data1)} 条数据，耗时: {elapsed1:.2f}秒")
    
    if data1:
        print(f"   最新数据日期: {data1[0]['time']}")
        print(f"   最旧数据日期: {data1[-1]['time']}")
    
    print(f"\n2. 第二次获取数据（应该从缓存读取）...")
    start_time = time.time()
    data2 = get_stock_kline(symbol, period)
    elapsed2 = time.time() - start_time
    print(f"   获取到 {len(data2)} 条数据，耗时: {elapsed2:.2f}秒")
    
    # 验证缓存是否有效
    if elapsed2 < elapsed1 * 0.5:  # 缓存读取应该快很多
        print("   ✅ 缓存读取速度明显快于API调用")
    else:
        print("   ⚠️ 缓存读取速度可能有问题")
    
    # 验证数据一致性
    if len(data1) == len(data2):
        print("   ✅ 缓存数据与API数据数量一致")
    else:
        print(f"   ⚠️ 数据数量不一致: API={len(data1)}, 缓存={len(data2)}")
    
    # 检查缓存目录和文件
    cache_dir = "cache"
    if os.path.exists(cache_dir):
        cache_files = os.listdir(cache_dir)
        print(f"\n3. 缓存目录检查:")
        print(f"   缓存目录: {cache_dir}")
        print(f"   缓存文件数量: {len(cache_files)}")
        
        cache_file = f"{symbol}_{period}.json"
        if cache_file in cache_files:
            print(f"   ✅ 缓存文件 {cache_file} 存在")
            
            # 检查缓存文件内容
            import json
            with open(os.path.join(cache_dir, cache_file), 'r', encoding='utf-8') as f:
                cache_content = json.load(f)
                print(f"   缓存时间: {cache_content.get('cached_at', '未知')}")
                print(f"   缓存数据条数: {len(cache_content.get('data', []))}")
        else:
            print(f"   ❌ 缓存文件 {cache_file} 不存在")
    else:
        print(f"\n❌ 缓存目录 {cache_dir} 不存在")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_cache_functionality()