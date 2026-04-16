from dotenv import load_dotenv
from pymysql.err import MySQLError
from utils.db_utils import connection_pool

load_dotenv()


class PromptDAO:
    def __init__(self):
        self.connection_pool = connection_pool

    def _get_connection(self):
        try:
            connection = self.connection_pool.connection()
            return connection
        except Exception as e:
            print(f"Error getting connection from pool: {e}")
            return None

    def insert_prompt(self, prompt_type, prompt_type_desc, prompt):
        """
        插入提示信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = """
            INSERT INTO prompt (prompt_type, prompt_type_desc, prompt)
            VALUES (%s, %s, %s)
            """
            values = (prompt_type, prompt_type_desc, prompt)
            cursor.execute(query, values)
            connection.commit()
            return cursor.lastrowid
        except MySQLError as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_prompt_by_id(self, id):
        """
        根据ID获取提示信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "SELECT * FROM prompt WHERE id = %s"
            cursor.execute(query, (id,))
            result = cursor.fetchone()
            return result
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_prompt_by_type(self, prompt_type):
        """
        根据提示类型获取提示信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "SELECT prompt FROM prompt WHERE prompt_type = %s"
            cursor.execute(query, (prompt_type,))
            result = cursor.fetchone()
            
            # 正确处理字典类型的查询结果
            if result:
                if isinstance(result, dict):
                    # 如果结果是字典类型，返回prompt字段的值
                    return result.get('prompt')
                elif isinstance(result, (tuple, list)) and len(result) > 0:
                    # 如果结果是元组或列表类型，返回第一个元素
                    return result[0]
            
            # 如果没有结果，返回None
            return None
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def update_prompt(self, id, **kwargs):
        """
        更新提示信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            set_clause = ', '.join([f"{key} = %s" for key in kwargs])
            query = f"UPDATE prompt SET {set_clause} WHERE id = %s"
            values = list(kwargs.values()) + [id]
            cursor.execute(query, values)
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def delete_prompt(self, id):
        """
        根据ID删除提示信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "DELETE FROM prompt WHERE id = %s"
            cursor.execute(query, (id,))
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()