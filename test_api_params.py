#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试外部API是否支持日期范围参数
检查3月24日之前的历史数据是否可以获取
"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_api_with_params():
    """测试带参数的API调用"""
    
    base_url = os.getenv("getGopClaimListUrl")
    print("=" * 70)
    print("测试API是否支持日期范围参数")
    print("=" * 70)
    print(f"基础URL: {base_url}")
    
    # 尝试不同的参数组合
    test_cases = [
        {"description": "不带参数（默认）", "data": {}},
        {"description": "传入空日期范围", "data": {"startDate": "", "endDate": ""}},
        {"description": "指定3月份的日期范围", "data": {"startDate": "2026-03-01", "endDate": "2026-03-31"}},
        {"description": "指定4月份的日期范围", "data": {"startDate": "2026-04-01", "endDate": "2026-04-13"}},
        {"description": "尝试claimId范围", "data": {"minClaimId": "32000000", "maxClaimId": "32300000"}},
        {"description": "尝试claimsIdList参数", "data": {"claimsIdList": []}},
    ]
    
    for test in test_cases:
        print(f"\n{'='*60}")
        print(f"测试: {test['description']}")
        print(f"参数: {test['data']}")
        print("-" * 60)
        
        try:
            headers = {"Content-Type": "application/json"}
            response = requests.post(base_url, headers=headers, json=test['data'], timeout=30)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("content", [])
                print(f"返回记录数: {len(content)}")
                
                if content:
                    # 统计日期分布
                    date_count = {}
                    for item in content:
                        date_str = item.get("admissionDate", "")[:10] if item.get("admissionDate") else ""
                        if date_str:
                            date_count[date_str] = date_count.get(date_str, 0) + 1
                    
                    if date_count:
                        sorted_dates = sorted(date_count.keys(), reverse=True)
                        print("日期分布:")
                        for d in sorted_dates[:10]:
                            print(f"  {d}: {date_count[d]} 条")
            else:
                print(f"响应: {response.text[:200]}")
                
        except Exception as e:
            print(f"调用失败: {e}")
    
    print("\n" + "=" * 70)
    print("测试RE理赔API")
    print("=" * 70)
    
    re_url = os.getenv("getReGopClaimListUrl")
    print(f"RE API: {re_url}")
    
    try:
        response = requests.post(re_url, headers={"Content-Type": "application/json"}, json={}, timeout=30)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("content", [])
            print(f"返回记录数: {len(content)}")
            
            if content:
                # 统计日期分布
                date_count = {}
                for item in content:
                    date_str = item.get("admissionDate", "")[:10] if item.get("admissionDate") else ""
                    if date_str:
                        date_count[date_str] = date_count.get(date_str, 0) + 1
                
                if date_count:
                    sorted_dates = sorted(date_count.keys(), reverse=True)
                    print("RE API日期分布:")
                    for d in sorted_dates[:10]:
                        print(f"  {d}: {date_count[d]} 条")
        else:
            print(f"响应: {response.text[:200]}")
    except Exception as e:
        print(f"调用失败: {e}")

if __name__ == "__main__":
    test_api_with_params()