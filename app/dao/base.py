from pymysql.err import MySQLError
from app.utils.db_utils import connection_pool
from app.logger import setup_logger

logging = setup_logger()


class BaseDAO:
    """所有 DAO 的基类，封装通用的数据库连接和操作方法"""

    def __init__(self):
        self.connection_pool = connection_pool

    def _get_connection(self):
        try:
            connection = self.connection_pool.connection()
            return connection
        except Exception as e:
            logging.error(f"Error getting connection from pool: {e}")
            return None

    def _fetch_one(self, query, params=None):
        """执行查询并返回单条结果"""
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            cursor.execute(query, params or ())
            return cursor.fetchone()
        except MySQLError as e:
            logging.error(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def _fetch_all(self, query, params=None):
        """执行查询并返回所有结果"""
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            cursor.execute(query, params or ())
            return cursor.fetchall()
        except MySQLError as e:
            logging.error(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def _execute(self, query, params=None):
        """执行 INSERT/UPDATE/DELETE，返回受影响的行数"""
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            cursor.execute(query, params or ())
            connection.commit()
            return cursor.rowcount
        except MySQLError as e:
            logging.error(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()
