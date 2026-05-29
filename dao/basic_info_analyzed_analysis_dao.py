from pymysql.err import MySQLError
from dao.base import BaseDAO
from logger import logger

logging = logger.setup_logger()


class BasicInfoAnalyzedAnalysisDAO(BaseDAO):
    def insert_basic_info_analysis(self, claim_id, confirm_status=1, analysis_result=None):
        query = """
        INSERT INTO basic_info_analyzed_analysis (claim_id, confirm_status, analysis_result)
        VALUES (%s, %s, %s)
        """
        return self._execute(query, (claim_id, confirm_status, analysis_result))

    def get_basic_info_analysis_by_id(self, claim_id):
        query = "SELECT * FROM basic_info_analyzed_analysis WHERE claim_id = %s"
        return self._fetch_one(query, (claim_id,))

    def update_basic_info_analysis(self, claim_id, **kwargs):
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            set_clause = ', '.join([f"{key} = %s" for key in kwargs])
            query = f"UPDATE basic_info_analyzed_analysis SET {set_clause} WHERE claim_id = %s"
            values = list(kwargs.values()) + [claim_id]
            cursor.execute(query, values)
            connection.commit()
        except MySQLError as e:
            logging.error(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def delete_basic_info_analysis(self, claim_id):
        query = "DELETE FROM basic_info_analyzed_analysis WHERE claim_id = %s"
        return self._execute(query, (claim_id,))
