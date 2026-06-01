from pymysql.err import MySQLError
from app.dao.base import BaseDAO
from app.logger import logger

logging = logger.setup_logger()


class ProviderDAO(BaseDAO):
    def insert_provider(self, provider_code, provider_name, provider_type, gop_white_list='N'):
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
            logging.error(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_provider_by_id(self, provider_id):
        query = "SELECT * FROM provider WHERE id = %s"
        return self._fetch_one(query, (provider_id,))

    def get_provider_by_code(self, provider_code):
        query = "SELECT * FROM provider WHERE provider_code = %s"
        return self._fetch_one(query, (provider_code,))

    def get_all_providers(self):
        query = "SELECT * FROM provider"
        return self._fetch_all(query) or []

    def update_provider(self, provider_id, **kwargs):
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
            logging.error(f"Error executing query: {e}")
            return False
        finally:
            cursor.close()
            connection.close()

    def delete_provider(self, provider_id):
        query = "DELETE FROM provider WHERE id = %s"
        result = self._execute(query, (provider_id,))
        return result is not None

    def get_gop_whitelisted_providers(self):
        query = "SELECT * FROM provider WHERE gop_white_list = 'Y'"
        return self._fetch_all(query) or []
