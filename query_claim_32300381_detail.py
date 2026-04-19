#!/usr/bin/env python3
"""
查询案件 32300381 的AI审核详细流程
"""
import pymysql
import ast

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
print(f"案件 {claim_id} - AI审核详细流程分析")
print("=" * 80)

# 1. 查询主表
cursor.execute("SELECT * FROM claim_case WHERE claim_id = %s", (claim_id,))
claim = cursor.fetchone()

print(f"\n【案件基本信息】")
print(f"  患者: {claim['patient_name']}")
print(f"  医院: {claim['provider_name']}")
print(f"  诊断: {claim['pri_diag_desc']}")
print(f"  入院: {claim['admission_date']}")
print(f"  预估费用: {claim['amount']}元")
print(f"  创建时间: {claim['create_time']}")
print(f"  更新时间: {claim['update_time']}")

# 2. 解析 AI 审核结果（用 ast 解析 Python dict 字符串）
print(f"\n【AI审核结果】")
if claim['preauth_result']:
    try:
        result = ast.literal_eval(claim['preauth_result'])
        print(f"  ✅ 决定: {result.get('result','N/A')}")
        print(f"  ✅ 金额: {result.get('amount','N/A')}元")
        print(f"\n  📋 审核理由（详细）:")
        reason = result.get('reason', '')
        for i, line in enumerate(reason.split('\n'), 1):
            line = line.strip()
            if line:
                # 判断是否是步骤标题
                if line.startswith(('1.', '2.', '3.', '4.', '5.')) or '步骤' in line:
                    print(f"\n  {i}. {line}")
                else:
                    print(f"     {line}")
    except Exception as e:
        print(f"  ❌ 解析失败: {e}")
        print(f"  原始: {claim['preauth_result'][:300]}")

# 3. 查找所有相关日志表
print(f"\n【查找处理日志表】")
cursor.execute("SHOW TABLES")
tables = [t[0] for t in cursor.fetchall()]
print(f"  数据库中共有 {len(tables)} 个表")

# 查找可能包含日志的表
log_tables = [t for t in tables if 'log' in t.lower() or 'process' in t.lower()]
print(f"\n  可能的日志表:")
for t in log_tables:
    print(f"    - {t}")

# 4. 尝试查找案件特定的日志
print(f"\n【尝试查找案件日志】")
for log_table in ['uhc_case_process_log', 'ai_scheduler_logs', 'ai_status_history']:
    if log_table in tables:
        print(f"\n  表 {log_table}:")
        cursor.execute(f"SHOW COLUMNS FROM {log_table}")
        cols = [c[0] for c in cursor.fetchall()]
        print(f"    字段: {cols}")
        cursor.execute(f"SELECT * FROM {log_table} WHERE claim_id = %s OR claim_case_id = %s LIMIT 5", (claim_id, claim_id))
        rows = cursor.fetchall()
        if rows:
            print(f"    找到 {len(rows)} 条记录")
            for row in rows:
                print(f"    {dict(row)}")
        else:
            print(f"    该案件无记录")

# 5. 查找 workflow 或 process 相关表
print(f"\n【流程相关表】")
process_tables = [t for t in tables if any(kw in t.lower() for kw in ['process', 'workflow', 'stage', 'audit'])]
for t in process_tables[:10]:
    print(f"  - {t}")

print("\n" + "=" * 80)

conn.close()
