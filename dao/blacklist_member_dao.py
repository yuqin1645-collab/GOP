from pymysql.err import MySQLError
from dao.base import BaseDAO
from logger import logger

logging = logger.setup_logger()


class BlacklistMemberDAO(BaseDAO):
    def insert_blacklist_member(self, id, name, id_type, new_ic, tel_mobile=None, remark=None,
                               remove_remark=None, source=None, status=1, create_by=None,
                               update_by=None, black_types=None):
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
            logging.error(f"Error executing query: {e}")
            return None
        finally:
            cursor.close()
            connection.close()

    def get_blacklist_member_by_id(self, id):
        query = "SELECT * FROM BLACKLIST_MEMBER WHERE id = %s"
        return self._fetch_one(query, (id,))

    def get_blacklist_member_by_new_ic(self, new_ic):
        query = "SELECT * FROM BLACKLIST_MEMBER WHERE new_ic = %s"
        return self._fetch_one(query, (new_ic,))

    def update_blacklist_member(self, id, **kwargs):
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
            logging.error(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def delete_blacklist_member(self, id):
        query = "DELETE FROM BLACKLIST_MEMBER WHERE id = %s"
        return self._execute(query, (id,))

    def get_active_blacklist_members(self, limit=100):
        query = "SELECT * FROM BLACKLIST_MEMBER WHERE status = 1 LIMIT %s"
        return self._fetch_all(query, (limit,))
