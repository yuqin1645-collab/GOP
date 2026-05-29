from pymysql.err import MySQLError
from dao.base import BaseDAO
from logger import logger

logging = logger.setup_logger()


class PoliciesAnalysisDAO(BaseDAO):
    def insert_policies_analysis(self, claim_id, policy_type, file_name=None, file_url=None, confirm_status=1, analysis_result=None):
        query = """
        INSERT INTO policies_analysis (claim_id, file_name, file_url, confirm_status, analysis_result, policy_type)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        return self._execute(query, (claim_id, file_name, file_url, confirm_status, analysis_result, policy_type))

    def get_policies_analysis_by_id(self, claim_id, policy_type):
        query = "SELECT * FROM policies_analysis WHERE claim_id = %s AND policy_type = %s"
        return self._fetch_all(query, (claim_id, policy_type))

    def get_policies_analysis_by_claim_id_and_file_name(self, claim_id, file_name):
        query = "SELECT * FROM policies_analysis WHERE claim_id = %s AND file_name = %s"
        return self._fetch_all(query, (claim_id, file_name))

    def update_policies_analysis(self, claim_id, **kwargs):
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            set_clause = ', '.join([f"{key} = %s" for key in kwargs])
            query = f"UPDATE policies_analysis SET {set_clause} WHERE claim_id = %s"
            values = list(kwargs.values()) + [claim_id]
            cursor.execute(query, values)
            connection.commit()
        except MySQLError as e:
            logging.error(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def delete_policies_analysis(self, claim_id):
        query = "DELETE FROM policies_analysis WHERE claim_id = %s"
        return self._execute(query, (claim_id,))
