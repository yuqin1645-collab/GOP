import os
import pymysql
from dbutils.pooled_db import PooledDB
from dotenv import load_dotenv

load_dotenv()

# 创建数据库连接池
def create_connection_pool():
    try:
        pool = PooledDB(
            creator=pymysql,
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT')),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            maxconnections=10,
            blocking=True
        )
        return pool
    except Exception as e:
        print(f"Error creating connection pool: {e}")
        return None

# 全局连接池实例
connection_pool = create_connection_pool()