#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检测外部API是否包含3月24日-4月13日缺失期间的数据
"""

import requests
import json
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def check_missing_period_data():
    """检查外部API返回的数据中是否包含缺失期间的数据"""
    url = os.getenv("getGopClaimListUrl")
    print("=" * 70)
    print("检测外部API数据")
    print("=" * 70)
    print(f"API: {url}")
    
    try:
        response = requests.post(url, headers={"Content-Type": "application/json"}, timeout=60)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("content", [])
            print(f"API返回记录数: {len(content)}")
            
            if not content:
                print("API没有返回数据")
                return
            
            # 日期范围：3月24日 - 4月13日
            missing_start = datetime(2026, 3, 24)
            missing_end = datetime(2026, 4, 13)
            
            # 统计各日期的数据
            date_count = {}
            missing_period_data = []
            
            for item in content:
                # 尝试多个日期字段
                date_str = item.get("admissionDate") or item.get("transmissionDate") or item.get("claimsRecDate") or ""
                
                if date_str:
                    # 尝试解析日期
                    try:
                        if isinstance(date_str, str) and len(date_str) >= 10:
                            date_part = date_str[:10]  # 取前10位 "2026-03-25"
                            if date_part not in date_count:
                                date_count[date_part] = 0
                            date_count[date_part] += 1
                            
                            # 检查是否在缺失期间
                            dt = datetime.strptime(date_part, "%Y-%m-%d")
                            if missing_start <= dt <= missing_end:
                                missing_period_data.append(item)
                    except:
                        pass
            
            print(f"\nAPI返回数据中各日期分布（前20条）：")
            sorted_dates = sorted(date_count.keys(), reverse=True)[:20]
            for d in sorted_dates:
                print(f"  {d}: {date_count[d]} 条")
            
            if missing_period_data:
                print(f"\n✅ 找到 {len(missing_period_data)} 条属于缺失期间(3/24-4/13)的数据！")
                print("\n缺失期间数据示例（前3条）：")
                for i, item in enumerate(missing_period_data[:3]):
                    print(f"\n--- 第{i+1}条 ---")
                    print(f"  claimsId: {item.get('claimsId')}")
                    print(f"  admissionDate: {item.get('admissionDate')}")
                    print(f"  transmissionDate: {item.get('transmissionDate')}")
                    print(f"  patientName: {item.get('patientName')}")
            else:
                print(f"\n❌ API返回的数据中不包含缺失期间(3/24-4/13)的数据")
                print("\n可能原因：")
                print("  1. 外部API只返回当前需要处理的案件，不返回历史数据")
                print("  2. 需要联系外部系统确认是否有历史数据备份")
                print("  3. 缺失期间的业务确实没有新案件")
            
            # 检查其他可能包含日期的字段
            print("\n" + "-" * 50)
            print("第一条数据的完整字段：")
            print(json.dumps(content[0], ensure_ascii=False, indent=2))
            
        else:
            print(f"API调用失败: {response.status_code}")
            print(f"响应: {response.text[:500]}")
            
    except Exception as e:
        print(f"调用失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_missing_period_data()
