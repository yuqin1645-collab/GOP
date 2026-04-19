#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试外部API，查看数据格式和内容
用于确定是否可以补回3月24日-4月13日缺失的数据
"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_api():
    # 测试主API
    url = os.getenv("getGopClaimListUrl")
    print("=" * 60)
    print(f"测试API: {url}")
    print("=" * 60)
    
    try:
        response = requests.post(url, headers={"Content-Type": "application/json"}, timeout=30)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("content", [])
            print(f"返回记录数: {len(content)}")
            
            if content:
                print("\n第一条数据示例:")
                print(json.dumps(content[0], ensure_ascii=False, indent=2))
                
                # 检查是否有日期相关字段
                first_item = content[0]
                print("\n包含的字段:")
                for key in first_item.keys():
                    print(f"  - {key}")
                    
                # 尝试找出日期相关的字段
                date_fields = ['admissionDate', 'transmissionDate', 'claimsRecDate', 'createTime', 'date']
                print("\n日期字段值:")
                for field in date_fields:
                    if field in first_item:
                        print(f"  {field}: {first_item.get(field)}")
        else:
            print(f"响应内容: {response.text[:500]}")
    except Exception as e:
        print(f"调用失败: {e}")

    print("\n" + "=" * 60)
    print("测试RE理赔API")
    print("=" * 60)
    
    # 测试RE理赔API
    re_url = os.getenv("getReGopClaimListUrl")
    print(f"测试API: {re_url}")
    
    try:
        response = requests.post(re_url, headers={"Content-Type": "application/json"}, timeout=30)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("content", [])
            print(f"返回记录数: {len(content)}")
            
            if content:
                print("\n第一条数据示例:")
                print(json.dumps(content[0], ensure_ascii=False, indent=2))
        else:
            print(f"响应内容: {response.text[:500]}")
    except Exception as e:
        print(f"调用失败: {e}")

if __name__ == "__main__":
    test_api()
