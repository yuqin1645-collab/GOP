import os
from dotenv import load_dotenv
import pymysql
from pymysql.err import MySQLError
from utils.db_utils import connection_pool

load_dotenv()

class CasePayDAO:
    def __init__(self):
        self.connection_pool = connection_pool

    def _get_connection(self):
        try:
            connection = self.connection_pool.connection()
            return connection
        except Exception as e:
            print(f"Error getting connection from pool: {e}")
            return None

    def insert_case_pay(self, hospital=None, year=None, claims_id=None, icd_tcp_code=None, 
                        icd_tcp_name=None, cpt_pay_price=None, cpt_code=None, provider_type=None):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = """
            INSERT INTO case_pay (医院, 年份, CLAIMS_ID, ICD_TCP_CODE, ICD_TCP_NAME, `cpt_pay价格`, cptCode, provider_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (hospital, year, claims_id, icd_tcp_code, icd_tcp_name, cpt_pay_price, cpt_code, provider_type)
            cursor.execute(query, values)
            connection.commit()
            return cursor.lastrowid
        except MySQLError as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_case_pay_by_id(self, id):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = "SELECT * FROM case_pay WHERE id = %s"
            cursor.execute(query, (id,))
            result = cursor.fetchone()
            return result
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_case_pay_by_claims_id(self, claims_id):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = "SELECT * FROM case_pay WHERE CLAIMS_ID = %s"
            cursor.execute(query, (claims_id,))
            result = cursor.fetchall()
            return result
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def update_case_pay(self, id, **kwargs):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            # Map Python field names to database column names
            field_mapping = {
                'hospital': '医院',
                'year': '年份',
                'claims_id': 'CLAIMS_ID',
                'icd_tcp_code': 'ICD_TCP_CODE',
                'icd_tcp_name': 'ICD_TCP_NAME',
                'cpt_pay_price': 'cpt_pay价格',
                'cpt_code': 'cptCode',
                'provider_type': 'provider_type'
            }
            
            # Convert field names to database column names
            db_kwargs = {field_mapping.get(key, key): value for key, value in kwargs.items()}
            
            set_clause = ', '.join([f"{key} = %s" for key in db_kwargs])
            query = f"UPDATE case_pay SET {set_clause} WHERE id = %s"
            values = list(db_kwargs.values()) + [id]
            cursor.execute(query, values)
            connection.commit()
            return cursor.rowcount
        except MySQLError as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def delete_case_pay(self, id):
        connection = self._get_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        try:
            query = "DELETE FROM case_pay WHERE id = %s"
            cursor.execute(query, (id,))
            connection.commit()
            return cursor.rowcount
        except MySQLError as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()