from pymysql.err import MySQLError
from dao.base import BaseDAO
from logger import logger

logging = logger.setup_logger()


class PromptDAO(BaseDAO):
    def insert_prompt(self, prompt_type, prompt_type_desc, prompt):
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
            logging.error(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_prompt_by_id(self, id):
        query = "SELECT * FROM prompt WHERE id = %s"
        return self._fetch_one(query, (id,))

    def get_prompt_by_type(self, prompt_type):
        query = "SELECT prompt FROM prompt WHERE prompt_type = %s"
        result = self._fetch_one(query, (prompt_type,))
        if result:
            if isinstance(result, dict):
                return result.get('prompt')
            elif isinstance(result, (tuple, list)) and len(result) > 0:
                return result[0]
        return None

    def update_prompt(self, id, **kwargs):
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
            logging.error(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def delete_prompt(self, id):
        query = "DELETE FROM prompt WHERE id = %s"
        return self._execute(query, (id,))
