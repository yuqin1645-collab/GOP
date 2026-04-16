import os
from dotenv import load_dotenv
import pymysql
from pymysql.err import MySQLError
from utils.db_utils import connection_pool

load_dotenv()

class PoliciesAnalysisDAO:
    def __init__(self):
        self.connection_pool = connection_pool

    def _get_connection(self):
        try:
            connection = self.connection_pool.connection()
            return connection
        except Exception as e:
            print(f"Error getting connection from pool: {e}")
            return None

    def insert_policies_analysis(self, claim_id, policy_type,file_name=None,file_url=None,confirm_status=1, analysis_result=None):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = """
            INSERT INTO policies_analysis (claim_id, file_name, file_url,confirm_status, analysis_result,policy_type)
            VALUES (%s, %s, %s, %s,%s, %s)
            """
            values = (claim_id, file_name, file_url,confirm_status, analysis_result,policy_type)
            cursor.execute(query, values)
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def get_policies_analysis_by_id(self, claim_id,policy_type):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = "SELECT * FROM policies_analysis WHERE claim_id = %s AND policy_type = %s"
            cursor.execute(query, (claim_id, policy_type))
            results = cursor.fetchall()
            return results
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_policies_analysis_by_claim_id_and_file_name(self, claim_id, file_name):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = "SELECT * FROM policies_analysis WHERE claim_id = %s AND file_name = %s"
            cursor.execute(query, (claim_id, file_name))
            results = cursor.fetchall()
            return results
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

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
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def delete_policies_analysis(self, claim_id):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = "DELETE FROM policies_analysis WHERE claim_id = %s"
            cursor.execute(query, (claim_id,))
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

