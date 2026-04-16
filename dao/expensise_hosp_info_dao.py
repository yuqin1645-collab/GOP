from dotenv import load_dotenv
from pymysql.err import MySQLError
from utils.db_utils import connection_pool

load_dotenv()


class ExpensiseHospInfoDAO:
    def __init__(self):
        self.connection_pool = connection_pool

    def _get_connection(self):
        try:
            connection = self.connection_pool.connection()
            return connection
        except Exception as e:
            print(f"Error getting connection from pool: {e}")
            return None

    def insert_hosp_info(self, hosp_name, hosp_typ):
        """
        插入医院信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = """
            INSERT INTO expensise_hosp_info (hosp_name, hosp_typ)
            VALUES (%s, %s)
            """
            values = (hosp_name, hosp_typ)
            cursor.execute(query, values)
            connection.commit()
            return cursor.lastrowid
        except MySQLError as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_hosp_info_by_id(self, id):
        """
        根据ID获取医院信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "SELECT * FROM expensise_hosp_info WHERE id = %s"
            cursor.execute(query, (id,))
            result = cursor.fetchone()
            return result
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_expensive_hosp_names(self):
        """
        获取类型为'是'的医院名称列表
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = """
            SELECT GROUP_CONCAT(hosp_name) AS hosp_names
            FROM expensise_hosp_info
            WHERE hosp_typ = '是'
            """
            cursor.execute(query)
            result = cursor.fetchone()
            
            # 正确处理字典类型的查询结果
            if result:
                if isinstance(result, dict):
                    # 如果结果是字典类型，通过键名获取值
                    hosp_names = result.get('hosp_names', '')
                    return hosp_names if hosp_names is not None else ""
                elif isinstance(result, (tuple, list)) and len(result) > 0:
                    # 如果结果是元组或列表类型，通过索引获取值
                    return result[0] if result[0] is not None else ""
            
            # 如果没有结果或结果为空，返回空字符串
            return ""
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def update_hosp_info(self, id, **kwargs):
        """
        更新医院信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            set_clause = ', '.join([f"{key} = %s" for key in kwargs])
            query = f"UPDATE expensise_hosp_info SET {set_clause} WHERE id = %s"
            values = list(kwargs.values()) + [id]
            cursor.execute(query, values)
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def delete_hosp_info(self, id):
        """
        根据ID删除医院信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "DELETE FROM expensise_hosp_info WHERE id = %s"
            cursor.execute(query, (id,))
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()