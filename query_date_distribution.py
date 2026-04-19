#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询 claim_case 表的日期分布情况
用于排查 4月1日-4月10日数据缺失问题
"""

import pymysql

# 数据库连接配置
DB_CONFIG = {
    'host': 'rds3335l2v6qar8zqontg.mysql.rds.aliyuncs.com',
    'port': 3306,
    'user': 'aiuser',
    'password': 'AI@ssish',
    'database': 'ai',
    'charset': 'utf8mb4'
}

def main():
    connection = pymysql.connect(**DB_CONFIG)
    
    try:
        with connection.cursor() as cursor:
            # 1. 查询各日期的案件数量分布
            query = """
            SELECT DATE(create_time) as date, COUNT(*) as count 
            FROM claim_case 
            GROUP BY DATE(create_time) 
            ORDER BY date DESC
            """
            cursor.execute(query)
            results = cursor.fetchall()
            
            print("=" * 60)
            print("claim_case 表中各日期的案件数量分布（按日期倒序）：")
            print("=" * 60)
            for row in results:
                print(f"{row[0]} : {row[1]} 条")
            
            # 2. 查询最早和最新日期
            cursor.execute("SELECT MIN(create_time), MAX(create_time), COUNT(*) FROM claim_case")
            min_date, max_date, total = cursor.fetchone()
            print("\n" + "=" * 60)
            print(f"数据最早日期: {min_date}")
            print(f"数据最新日期: {max_date}")
            print(f"总记录数: {total}")
            print("=" * 60)
            
            # 3. 查询 3月-4月 的数据量
            print("\n" + "=" * 60)
            print("3月-4月 每日数据量统计：")
            print("=" * 60)
            query2 = """
            SELECT DATE(create_time) as date, COUNT(*) as count 
            FROM claim_case 
            WHERE create_time >= '2026-03-01' AND create_time < '2026-04-20'
            GROUP BY DATE(create_time) 
            ORDER BY date
            """
            cursor.execute(query2)
            results2 = cursor.fetchall()
            
            march_total = 0
            april_total = 0
            for row in results2:
                month = row[0].month if row[0] else 0
                if month == 3:
                    march_total += row[1]
                elif month == 4:
                    april_total += row[1]
                print(f"{row[0]} : {row[1]} 条")
            
            print("\n" + "-" * 40)
            print(f"3月份总计: {march_total} 条")
            print(f"4月份目前统计: {april_total} 条")
            
    finally:
        connection.close()

if __name__ == "__main__":
    main()
