import os
from dbutils.pooled_db import PooledDB
import pymysql


def create_connection_pool():
    try:
        connection_pool = PooledDB(
            creator=pymysql,
            maxconnections=25,
            mincached=2,
            maxcached=5,
            blocking=True,
            maxusage=None,
            setsession=[],
            ping=0,
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'gop'),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection_pool
    except Exception as e:
        print(f"Failed to create connection pool: {e}")
        raise


connection_pool = create_connection_pool()
