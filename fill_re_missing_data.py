#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补充RE理赔缺失期间的数据
直接调用现有API处理
"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def get_existing_claim_ids():
    """通过API获取数据库中已处理的claim_id"""
    # 这里直接查询数据库
    import sys
    sys.path.insert(0, '.')
    from dao.claim_case_dao import ClaimCaseDAO
    from utils.dao_context import dao_context
    
    with dao_context() as (claim_dao, *_,):
        connection = claim_dao._get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT claim_id FROM claim_case")
        existing_ids = set(str(row['claim_id']) for row in cursor.fetchall())
        cursor.close()
        connection.close()
        return existing_ids

def get_re_claims_from_api():
    """从RE API获取数据"""
    url = os.getenv("getReGopClaimListUrl")
    response = requests.post(url, headers={"Content-Type": "application/json"}, json={}, timeout=60)
    if response.status_code == 200:
        result = response.json()
        return result.get("content", [])
    return []

def fill_re_missing_data():
    """补充RE理赔数据"""
    print("=" * 70)
    print("从RE API补充缺失期间(3/24-4/13)的数据")
    print("=" * 70)
    
    # 1. 获取数据库已存在的claim_id
    existing_ids = get_existing_claim_ids()
    print(f"\n数据库已存在的claim_id: {len(existing_ids)} 个")
    
    # 2. 从API获取数据
    api_data = get_re_claims_from_api()
    print(f"RE API返回: {len(api_data)} 条")
    
    # 3. 筛选缺失期间的数据
    missing_start = "2026-03-24"
    missing_end = "2026-04-13"
    
    missing_period_data = []
    for item in api_data:
        admission_date = item.get("admissionDate", "")[:10]
        if missing_start <= admission_date <= missing_end:
            missing_period_data.append(item)
    
    print(f"\n缺失期间数据: {len(missing_period_data)} 条")
    
    # 4. 过滤并分类
    new_data = []  # 新数据
    skip_data = []  # 已存在
    
    for item in missing_period_data:
        claim_id = str(item.get("claimsId", ""))
        if claim_id in existing_ids:
            skip_data.append(item)
        else:
            new_data.append(item)
    
    print(f"  - 已存在，跳过: {len(skip_data)} 条")
    print(f"  - 需要新增: {len(new_data)} 条")
    
    if not new_data:
        print("\n所有数据已存在，无需补充！")
        return
    
    # 5. 显示需要补充的数据
    print("\n需要补充的数据:")
    for item in sorted(new_data, key=lambda x: x.get("admissionDate", "")):
        print(f"  {item.get('admissionDate','')[:10]} - {item.get('claimsId')} - {item.get('patientName','')}")
    
    # 6. 确认执行
    print("\n" + "=" * 70)
    confirm = input(f"\n确认补充 {len(new_data)} 条数据? (输入 'yes' 确认): ")
    
    if confirm.lower() != 'yes':
        print("已取消")
        return
    
    # 7. 调用API处理每条数据
    print("\n开始调用API处理...")
    
    import sys
    sys.path.insert(0, '.')
    from app import process_claim_re_init
    from utils.dao_context import dao_context
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    for item in new_data:
        claim_id = str(item.get("claimsId"))
        print(f"\n处理 claim_id: {claim_id}...", end=" ")
        
        try:
            with dao_context() as (claim_dao, basic_info_dao, document_dao, policies_dao, _):
                process_claim_re_init(item, claim_dao, basic_info_dao)
                success_count += 1
                print("成功")
        except Exception as e:
            fail_count += 1
            print(f"失败: {e}")
    
    print("\n" + "=" * 70)
    print(f"处理完成:")
    print(f"  - 成功: {success_count} 条")
    print(f"  - 失败: {fail_count} 条")
    print(f"  - 跳过: {skip_count} 条")
    print("=" * 70)

if __name__ == "__main__":
    fill_re_missing_data()
