#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补数据脚本
尝试从外部API获取3月24日-4月13日缺失的数据并同步到数据库
"""

import requests
import json
import os
from dotenv import load_dotenv
import sys
sys.path.insert(0, '.')
from dao.claim_case_dao import ClaimCaseDAO
from utils.dao_context import dao_context

load_dotenv()

def check_existing_claim_ids():
    """检查数据库中已存在的claim_id"""
    with dao_context() as (claim_dao, *_,):
        # 获取所有claim_id
        query = "SELECT claim_id FROM claim_case"
        connection = claim_dao._get_connection()
        cursor = connection.cursor()
        cursor.execute(query)
        existing_ids = set(str(row[0]) for row in cursor.fetchall())
        cursor.close()
        connection.close()
        return existing_ids

def sync_claims_from_api():
    """从外部API同步数据"""
    url = os.getenv("getGopClaimListUrl")
    print(f"调用API: {url}")
    
    try:
        response = requests.post(url, headers={"Content-Type": "application/json"}, timeout=60)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("content", [])
            print(f"API返回记录数: {len(content)}")
            
            if not content:
                print("API没有返回数据")
                return 0
            
            # 检查已存在的claim_id
            existing_ids = check_existing_claim_ids()
            print(f"数据库中已存在的claim_id数量: {len(existing_ids)}")
            
            # 统计需要插入的数据
            new_count = 0
            existing_count = 0
            missing_period_count = 0
            
            for item in content:
                claim_id = str(item.get("claimsId", ""))
                
                # 检查是否已存在
                if claim_id in existing_ids:
                    existing_count += 1
                    continue
                
                # 检查日期字段（如果是3月24日-4月13日之间的数据）
                admission_date = item.get("admissionDate", "")
                transmission_date = item.get("transmissionDate", "")
                claims_rec_date = item.get("claimsRecDate", "")
                
                # 简单判断是否是缺失期间的数据（可以根据日期字段调整）
                if admission_date or transmission_date or claims_rec_date:
                    missing_period_count += 1
                
                new_count += 1
            
            print(f"\n统计结果:")
            print(f"  - 已存在，跳过: {existing_count}")
            print(f"  - 新数据（可能是缺失期间的）: {missing_period_count}")
            
            return len(content)
        else:
            print(f"API调用失败: {response.status_code}")
            print(f"响应: {response.text[:500]}")
            return 0
            
    except Exception as e:
        print(f"调用失败: {e}")
        return 0

def main():
    print("=" * 60)
    print("开始补数据流程")
    print("=" * 60)
    
    # 1. 先测试API返回什么数据
    sync_claims_from_api()
    
    print("\n" + "=" * 60)
    print("下一步建议")
    print("=" * 60)
    print("""
1. 如果API返回了3月24日-4月13日的数据，说明外部系统有历史数据
2. 需要确认API是否支持传入日期范围参数
3. 如果API没有那段时期的数据，需要联系外部系统/业务方

请运行以下命令测试API：
  cd /app/gop && source myenv/bin/activate && python test_api_and_fill_data.py
""")

if __name__ == "__main__":
    main()
