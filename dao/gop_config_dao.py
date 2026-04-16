from dotenv import load_dotenv
from pymysql.err import MySQLError
from utils.db_utils import connection_pool

load_dotenv()


class GopConfigDAO:
    def __init__(self):
        self.connection_pool = connection_pool

    def _get_connection(self):
        try:
            connection = self.connection_pool.connection()
            return connection
        except Exception as e:
            print(f"Error getting connection from pool: {e}")
            return None

    def insert_config(self, config_type, config_value):
        """
        插入配置信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = """
            INSERT INTO gop_config (config_type, config_value)
            VALUES (%s, %s)
            """
            values = (config_type, config_value)
            cursor.execute(query, values)
            connection.commit()
            return cursor.lastrowid
        except MySQLError as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_config_by_id(self, id):
        """
        根据ID获取配置信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "SELECT * FROM gop_config WHERE id = %s"
            cursor.execute(query, (id,))
            result = cursor.fetchone()
            return result
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()


    def get_config_by_typ(self, typ):
        """
        根据cfg_typ获取配置的config_value
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "SELECT config_value FROM gop_config WHERE cfg_typ = %s"
            cursor.execute(query, (typ,))
            result = cursor.fetchone()
            if result:
                # 返回config_value字段的值
                if isinstance(result, dict):
                    return result.get('config_value', None)
                else:
                    return result[0]
            return None
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()


    # def get_all_config_values(self):
    #     """
    #     获取所有配置值，用换行符分隔
    #     """
    #     connection = self._get_connection()
    #     if not connection:
    #         return None
    #
    #     cursor = connection.cursor()
    #     try:
    #         query = """
    #         SELECT GROUP_CONCAT(config_value SEPARATOR '\n') AS config_values
    #         FROM gop_config
    #         """
    #         cursor.execute(query)
    #         result = cursor.fetchone()
    #
    #         # 正确处理字典类型的查询结果
    #         if result:
    #             if isinstance(result, dict):
    #                 # 如果结果是字典类型，通过键名获取值
    #                 config_values = result.get('config_values', '')
    #                 return config_values if config_values is not None else ""
    #             elif isinstance(result, (tuple, list)) and len(result) > 0:
    #                 # 如果结果是元组或列表类型，通过索引获取值
    #                 return result[0] if result[0] is not None else ""
    #
    #         # 如果没有结果或结果为空，返回空字符串
    #         return ""
    #     except MySQLError as e:
    #         print(f"Error fetching data: {e}")
    #         return None
    #     finally:
    #         cursor.close()
    #         connection.close()

    def update_config(self, id, **kwargs):
        """
        更新配置信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            set_clause = ', '.join([f"{key} = %s" for key in kwargs])
            query = f"UPDATE gop_config SET {set_clause} WHERE id = %s"
            values = list(kwargs.values()) + [id]
            cursor.execute(query, values)
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def delete_config(self, id):
        """
        根据ID删除配置信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "DELETE FROM gop_config WHERE id = %s"
            cursor.execute(query, (id,))
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()