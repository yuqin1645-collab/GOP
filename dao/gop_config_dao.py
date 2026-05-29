from pymysql.err import MySQLError
from dao.base import BaseDAO
from logger import logger

logging = logger.setup_logger()


class GopConfigDAO(BaseDAO):
    def insert_config(self, config_type, config_value):
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
            logging.error(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_config_by_id(self, id):
        query = "SELECT * FROM gop_config WHERE id = %s"
        return self._fetch_one(query, (id,))

    def get_config_by_typ(self, typ):
        query = "SELECT config_value FROM gop_config WHERE cfg_typ = %s"
        result = self._fetch_one(query, (typ,))
        if result:
            if isinstance(result, dict):
                return result.get('config_value', None)
            else:
                return result[0]
        return None

    def update_config(self, id, **kwargs):
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
            logging.error(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def delete_config(self, id):
        query = "DELETE FROM gop_config WHERE id = %s"
        return self._execute(query, (id,))
