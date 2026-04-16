import os
from dotenv import load_dotenv
import pymysql
from pymysql.err import MySQLError
from utils.db_utils import connection_pool

load_dotenv()

class DocumentAnalysisDAO:
    def __init__(self):
        self.connection_pool = connection_pool

    def _get_connection(self):
        try:
            connection = self.connection_pool.connection()
            return connection
        except Exception as e:
            print(f"Error getting connection from pool: {e}")
            return None

    def insert_document_analysis(self, claim_id, image_quality,consistency,diff,file_name=None, file_url=None,confirm_status=0, analysis_result=None):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = """
            INSERT INTO document_analysis (claim_id, confidence_level,consistency,file_name, file_url,confirm_status, analysis_result,diff)
            VALUES (%s, %s, %s, %s, %s, %s,%s,%s)
            """
            values = (claim_id, image_quality,consistency,file_name, file_url,confirm_status, analysis_result,diff)
            cursor.execute(query, values)
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
            raise
        finally:
            cursor.close()
            connection.close()

    def get_document_analysis_by_id(self, claim_id):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = "SELECT * FROM document_analysis WHERE claim_id = %s"
            cursor.execute(query, (claim_id,))
            result = cursor.fetchone()
            return result
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_document_analysis_by_claim_id(self, claim_id):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = "SELECT * FROM document_analysis WHERE claim_id = %s"
            cursor.execute(query, (claim_id,))
            results = cursor.fetchall()
            return results
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()
    def get_documents_analysis_by_claim_id_and_file_name(self, claim_id, file_name):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = "SELECT * FROM document_analysis WHERE claim_id = %s AND file_name = %s"
            cursor.execute(query, (claim_id, file_name))
            results = cursor.fetchall()
            return results
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def update_document_analysis(self, claim_id, image_quality, consistency, analysis_result):
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = """
            UPDATE document_analysis
            SET confidence_level = %s, consistency = %s, analysis_result = %s
            WHERE claim_id = %s
            """
            values = (image_quality, consistency, analysis_result, claim_id)
            cursor.execute(query, values)
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
            raise
        finally:
            cursor.close()
            connection.close()

    def delete_document_analysis(self, claim_id):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = "DELETE FROM document_analysis WHERE claim_id = %s"
            cursor.execute(query, (claim_id,))
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()



