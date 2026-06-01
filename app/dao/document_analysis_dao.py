from pymysql.err import MySQLError
from app.dao.base import BaseDAO
from app.logger import logger

logging = logger.setup_logger()


class DocumentAnalysisDAO(BaseDAO):
    def insert_document_analysis(self, claim_id, image_quality, consistency, diff, file_name=None, file_url=None, confirm_status=0, analysis_result=None):
        query = """
        INSERT INTO document_analysis (claim_id, confidence_level, consistency, file_name, file_url, confirm_status, analysis_result, diff)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        return self._execute(query, (claim_id, image_quality, consistency, file_name, file_url, confirm_status, analysis_result, diff))

    def get_document_analysis_by_id(self, claim_id):
        query = "SELECT * FROM document_analysis WHERE claim_id = %s"
        return self._fetch_one(query, (claim_id,))

    def get_document_analysis_by_claim_id(self, claim_id):
        query = "SELECT * FROM document_analysis WHERE claim_id = %s"
        return self._fetch_all(query, (claim_id,))

    def get_documents_analysis_by_claim_id_and_file_name(self, claim_id, file_name):
        query = "SELECT * FROM document_analysis WHERE claim_id = %s AND file_name = %s"
        return self._fetch_all(query, (claim_id, file_name))

    def update_document_analysis(self, claim_id, image_quality, consistency, analysis_result):
        query = """
        UPDATE document_analysis
        SET confidence_level = %s, consistency = %s, analysis_result = %s
        WHERE claim_id = %s
        """
        return self._execute(query, (image_quality, consistency, analysis_result, claim_id))

    def delete_document_analysis(self, claim_id):
        query = "DELETE FROM document_analysis WHERE claim_id = %s"
        return self._execute(query, (claim_id,))
