#!/usr/bin/env python3
"""
查询单个 GOP 案件 32300381 的完整处理过程（简化版）
"""
import pymysql
import json

conn = pymysql.connect(
    host='rds3335l2v6qar8zqontg.mysql.rds.aliyuncs.com',
    user='aiuser',
    password='AI@ssish',
    database='ai',
    charset='utf8mb4'
)
cursor = conn.cursor(pymysql.cursors.DictCursor)

claim_id = '32300381'

print("=" * 80)
print(f"案件 {claim_id} 完整数据查询")
print("=" * 80)

# 1. 基本信息
print("\n【1. 基本信息】")
cursor.execute("SELECT * FROM claim_case WHERE claim_id = %s", (claim_id,))
row = cursor.fetchone()
if row:
    print(f"  患者: {row['patient_name']}")
    print(f"  医院: {row['provider_name']}")
    print(f"  入院: {row['admission_date']}")
    print(f"  类型: {row['gop_type']} | {row['admission_type']}")
    print(f"  诊断: {row['pri_diag_desc']} | {row['diangosis']}")
    print(f"  费用: 预估{row['amount']}元, APV:{row['apv_amount']}元")
    print(f"  状态: 基本信息{'✅' if row['basic_info_analyzed'] else '❌'} | 文档{'✅' if row['documents_analyzed'] else '❌'} | 保单{'✅' if row['policies_analyzed'] else '❌'}")
    print(f"  AI结果: {row['ai_result_desc']}")
    print(f"  创建时间: {row['create_time']}")
    print(f"  更新时间: {row['update_time']}")
else:
    print("  未找到记录")

# 2. 检查是否存在诊断表
print("\n【2. 诊断表查询】")
cursor.execute("SHOW TABLES LIKE 'claim_diagnosis'")
if cursor.fetchone():
    cursor.execute("SELECT * FROM claim_diagnosis WHERE claim_id = %s", (claim_id,))
    rows = cursor.fetchall()
    if rows:
        for r in rows:
            print(f"  - {r}")
    else:
        print("  无诊断记录")
else:
    print("  表 claim_diagnosis 不存在")

# 3. 查询文档表
print("\n【3. 文档资料】")
cursor.execute("SHOW TABLES LIKE 'claim_documents'")
if cursor.fetchone():
    cursor.execute("SELECT id, doc_type, doc_name, analyzed, create_time FROM claim_documents WHERE claim_id = %s", (claim_id,))
    rows = cursor.fetchall()
    if rows:
        print(f"  共 {len(rows)} 份文档:")
        for r in rows:
            print(f"    #{r['id']}: {r['doc_type']} - {r['doc_name']} [{'已分析' if r['analyzed'] else '未分析'}]")
    else:
        print("  无文档记录")
else:
    print("  表 claim_documents 不存在")

# 4. 查询保单分析表
print("\n【4. 保单分析】")
cursor.execute("SHOW TABLES LIKE 'claim_policy_analysis'")
if cursor.fetchone():
    cursor.execute("SELECT * FROM claim_policy_analysis WHERE claim_id = %s", (claim_id,))
    rows = cursor.fetchall()
    if rows:
        print(f"  共 {len(rows)} 条条款:")
        for r in rows:
            print(f"    - {r}")
    else:
        print("  无保单分析记录")
else:
    print("  表 claim_policy_analysis 不存在")

# 5. 查询RE结果表
print("\n【5. 预授权结果】")
cursor.execute("SHOW TABLES LIKE 'claim_re_results'")
if cursor.fetchone():
    cursor.execute("SELECT * FROM claim_re_results WHERE claim_id = %s", (claim_id,))
    rows = cursor.fetchall()
    if rows:
        for r in rows:
            print(f"  {dict(r)}")
    else:
        print("  无RE结果记录")
else:
    print("  表 claim_re_results 不存在")

# 6. 查询处理日志表
print("\n【6. 处理日志】")
cursor.execute("SHOW TABLES LIKE 'claim_process_logs'")
if cursor.fetchone():
    cursor.execute("SELECT * FROM claim_process_logs WHERE claim_id = %s ORDER BY create_time DESC LIMIT 20", (claim_id,))
    rows = cursor.fetchall()
    if rows:
        print(f"  最近 {len(rows)} 条日志:")
        for r in rows:
            print(f"  [{r['create_time']}] {r.get('stage','')}: {str(r.get('message',''))[:120]}")
    else:
        print("  无处理日志")
else:
    print("  表 claim_process_logs 不存在")

# 7. 查看 preauth_result 的完整内容
print("\n【7. AI审核结果详情】")
if row and row['preauth_result']:
    try:
        result = json.loads(row['preauth_result'])
        print(f"  结果: {result.get('result','N/A')}")
        print(f"  金额: {result.get('amount','N/A')}")
        reason = result.get('reason','')
        if len(reason) > 500:
            reason = reason[:500] + "..."
        print(f"  理由: {reason}")
    except:
        print(f"  原始: {row['preauth_result'][:300]}")
else:
    print("  无结果")

print("\n" + "=" * 80)

conn.close()
