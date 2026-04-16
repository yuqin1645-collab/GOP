import os
from dotenv import load_dotenv
from pymysql.err import MySQLError
from utils.db_utils import connection_pool

load_dotenv()


class ProviderDAO:
    def __init__(self):
        self.connection_pool = connection_pool

    def _get_connection(self):
        try:
            connection = self.connection_pool.connection()
            return connection
        except Exception as e:
            print(f"Error getting connection from pool: {e}")
            return None

    def insert_provider(self, provider_code, provider_name, provider_type, gop_white_list='N'):
        """
        插入新的供应商记录
        
        Args:
            provider_code (str): 供应商代码
            provider_name (str): 供应商名称
            provider_type (str): 供应商类型
            gop_white_list (str): GOP白名单标识，默认为'N'
            
        Returns:
            int: 新插入记录的ID，如果失败则返回None
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = """
            INSERT INTO provider (provider_code, provider_name, provider_type, gop_white_list)
            VALUES (%s, %s, %s, %s)
            """
            values = (provider_code, provider_name, provider_type, gop_white_list)
            cursor.execute(query, values)
            connection.commit()
            return cursor.lastrowid
        except MySQLError as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_provider_by_id(self, provider_id):
        """
        根据ID获取供应商信息
        
        Args:
            provider_id (int): 供应商ID
            
        Returns:
            dict: 供应商信息，如果未找到则返回None
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "SELECT * FROM provider WHERE id = %s"
            cursor.execute(query, (provider_id,))
            result = cursor.fetchone()
            return result
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_provider_by_code(self, provider_code):
        """
        根据供应商代码获取供应商信息
        
        Args:
            provider_code (str): 供应商代码
            
        Returns:
            dict: 供应商信息，如果未找到则返回None
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "SELECT * FROM provider WHERE provider_code = %s"
            cursor.execute(query, (provider_code,))
            result = cursor.fetchone()
            return result
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_all_providers(self):
        """
        获取所有供应商信息
        
        Returns:
            list: 供应商信息列表
        """
        connection = self._get_connection()
        if not connection:
            return []

        cursor = connection.cursor()
        try:
            query = "SELECT * FROM provider"
            cursor.execute(query)
            results = cursor.fetchall()
            return results
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return []
        finally:
            cursor.close()
            connection.close()

    def update_provider(self, provider_id, **kwargs):
        """
        更新供应商信息
        
        Args:
            provider_id (int): 供应商ID
            **kwargs: 要更新的字段和值
            
        Returns:
            bool: 更新成功返回True，否则返回False
        """
        connection = self._get_connection()
        if not connection:
            return False

        cursor = connection.cursor()
        try:
            set_clause = ', '.join([f"{key} = %s" for key in kwargs])
            query = f"UPDATE provider SET {set_clause} WHERE id = %s"
            values = list(kwargs.values()) + [provider_id]
            cursor.execute(query, values)
            connection.commit()
            return True
        except MySQLError as e:
            print(f"Error executing query: {e}")
            return False
        finally:
            cursor.close()
            connection.close()

    def delete_provider(self, provider_id):
        """
        删除供应商记录
        
        Args:
            provider_id (int): 供应商ID
            
        Returns:
            bool: 删除成功返回True，否则返回False
        """
        connection = self._get_connection()
        if not connection:
            return False

        cursor = connection.cursor()
        try:
            query = "DELETE FROM provider WHERE id = %s"
            cursor.execute(query, (provider_id,))
            connection.commit()
            return True
        except MySQLError as e:
            print(f"Error executing query: {e}")
            return False
        finally:
            cursor.close()
            connection.close()

    def get_gop_whitelisted_providers(self):
        """
        获取GOP白名单中的所有供应商
        
        Returns:
            list: GOP白名单中的供应商列表
        """
        connection = self._get_connection()
        if not connection:
            return []

        cursor = connection.cursor()
        try:
            query = "SELECT * FROM provider WHERE gop_white_list = 'Y'"
            cursor.execute(query)
            results = cursor.fetchall()
            return results
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return []
        finally:
            cursor.close()
            connection.close()