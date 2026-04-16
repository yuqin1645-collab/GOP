import os
from dotenv import load_dotenv
import pymysql
from pymysql.err import MySQLError
from utils.db_utils import connection_pool

load_dotenv()

class BasicInfoAnalyzedAnalysisDAO:
    def __init__(self):
        self.connection_pool = connection_pool

    def _get_connection(self):
        try:
            connection = self.connection_pool.connection()
            return connection
        except Exception as e:
            print(f"Error getting connection from pool: {e}")
            return None

    def insert_basic_info_analysis(self, claim_id, confirm_status=1, analysis_result=None):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = """
            INSERT INTO basic_info_analyzed_analysis (claim_id, confirm_status, analysis_result)
            VALUES (%s, %s, %s)
            """
            values = (claim_id, confirm_status, analysis_result)
            cursor.execute(query, values)
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def get_basic_info_analysis_by_id(self, claim_id):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = "SELECT * FROM basic_info_analyzed_analysis WHERE claim_id = %s"
            cursor.execute(query, (claim_id,))
            result = cursor.fetchone()
            return result
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

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
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def delete_basic_info_analysis(self, claim_id):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = "DELETE FROM basic_info_analyzed_analysis WHERE claim_id = %s"
            cursor.execute(query, (claim_id,))
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()