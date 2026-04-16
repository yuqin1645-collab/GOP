from dotenv import load_dotenv
from pymysql.err import MySQLError
from utils.db_utils import connection_pool

load_dotenv()


class BlacklistMemberDAO:
    def __init__(self):
        self.connection_pool = connection_pool

    def _get_connection(self):
        try:
            connection = self.connection_pool.connection()
            return connection
        except Exception as e:
            print(f"Error getting connection from pool: {e}")
            return None

    def insert_blacklist_member(self, id, name, id_type, new_ic, tel_mobile=None, remark=None, 
                               remove_remark=None, source=None, status=1, create_by=None, 
                               update_by=None, black_types=None):
        """
        插入黑名单成员信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = """
            INSERT INTO BLACKLIST_MEMBER (id, name, id_type, new_ic, tel_mobile, remark, 
                                        remove_remark, source, status, create_by, update_by, black_types)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (id, name, id_type, new_ic, tel_mobile, remark, remove_remark, 
                     source, status, create_by, update_by, black_types)
            cursor.execute(query, values)
            connection.commit()
            return cursor.lastrowid
        except MySQLError as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_blacklist_member_by_id(self, id):
        """
        根据ID获取黑名单成员信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "SELECT * FROM BLACKLIST_MEMBER WHERE id = %s"
            cursor.execute(query, (id,))
            result = cursor.fetchone()
            return result
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_blacklist_member_by_new_ic(self, new_ic):
        """
        根据新身份证号获取黑名单成员信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "SELECT * FROM BLACKLIST_MEMBER WHERE new_ic = %s"
            cursor.execute(query, (new_ic,))
            result = cursor.fetchone()
            return result
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def update_blacklist_member(self, id, **kwargs):
        """
        更新黑名单成员信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            set_clause = ', '.join([f"{key} = %s" for key in kwargs])
            query = f"UPDATE BLACKLIST_MEMBER SET {set_clause} WHERE id = %s"
            values = list(kwargs.values()) + [id]
            cursor.execute(query, values)
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def delete_blacklist_member(self, id):
        """
        根据ID删除黑名单成员信息
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "DELETE FROM BLACKLIST_MEMBER WHERE id = %s"
            cursor.execute(query, (id,))
            connection.commit()
        except MySQLError as e:
            print(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def get_active_blacklist_members(self, limit=100):
        """
        获取有效的黑名单成员列表
        """
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            query = "SELECT * FROM BLACKLIST_MEMBER WHERE status = 1 LIMIT %s"
            cursor.execute(query, (limit,))
            result = cursor.fetchall()
            return result
        except MySQLError as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            cursor.close()
            connection.close()