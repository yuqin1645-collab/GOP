from pymysql.err import MySQLError
from dao.base import BaseDAO
from logger import logger

logging = logger.setup_logger()


class ExpensiseHospInfoDAO(BaseDAO):
    def insert_hosp_info(self, hosp_name, hosp_typ):
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
            logging.error(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_hosp_info_by_id(self, id):
        query = "SELECT * FROM expensise_hosp_info WHERE id = %s"
        return self._fetch_one(query, (id,))

    def get_expensive_hosp_names(self):
        query = """
        SELECT GROUP_CONCAT(hosp_name) AS hosp_names
        FROM expensise_hosp_info
        WHERE hosp_typ = '是'
        """
        connection = self._get_connection()
        if not connection:
            return ""

        cursor = connection.cursor()
        try:
            cursor.execute(query)
            result = cursor.fetchone()
            if result:
                if isinstance(result, dict):
                    hosp_names = result.get('hosp_names', '')
                    return hosp_names if hosp_names is not None else ""
                elif isinstance(result, (tuple, list)) and len(result) > 0:
                    return result[0] if result[0] is not None else ""
            return ""
        except MySQLError as e:
            logging.error(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def update_hosp_info(self, id, **kwargs):
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
            logging.error(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def delete_hosp_info(self, id):
        query = "DELETE FROM expensise_hosp_info WHERE id = %s"
        return self._execute(query, (id,))
