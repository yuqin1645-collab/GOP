from pymysql.err import MySQLError
from app.dao.base import BaseDAO
from app.logger import logger

logging = logger.setup_logger()


class ClaimCaseDAO(BaseDAO):
    def insert_claim_case(self, claim_id, claim_info, basic_info_analyzed=0, documents_analyzed=0, policies_analyzed=0, preauth_status=0, preauth_result=None):
        if claim_info.get("estBills"):
            rounded_amount = round(float(claim_info.get("estBills")), 2)
            if rounded_amount.is_integer():
                amount = int(rounded_amount)
            else:
                amount = f"{rounded_amount:.2f}"
        else:
            amount = None

        query = """
        INSERT INTO claim_case (claim_id, basic_info_analyzed, documents_analyzed, policies_analyzed, preauth_status,
                                preauth_result, admission_date, gop_type, payor_name, corporate_code,
                                patient_name, am, provider_name, provider_type, pri_diag_desc,
                                transmission_date, provider_code, admission_type, diangosis, cpt, amount, amount_currency,
                                provider_cate, provider_open_for_out, payor_code, payor_attr, loss_ratio, query_details, reco_benfit, claims_rec_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (claim_id, basic_info_analyzed, documents_analyzed, policies_analyzed, preauth_status,
                  preauth_result, str(claim_info.get("admissionDate")), claim_info.get("gopType"), claim_info.get("payorName"), claim_info.get("corporateCode"),
                  claim_info.get("patientName"), claim_info.get("am"), claim_info.get("providerName"), claim_info.get("providerType"), claim_info.get("priDiagDesc"),
                  claim_info.get("transmissionDate"), claim_info.get("providerCode"), claim_info.get("admissionType"), claim_info.get("diangosis"), claim_info.get("cpt"),
                  amount, claim_info.get("currency"), claim_info.get("providerCategory"), claim_info.get("providerOpenForOut"), claim_info.get("payor"), claim_info.get("payorAttr"),
                  claim_info.get("lossRatio"), claim_info.get("queryDetails"), claim_info.get("recoBenfit"), claim_info.get("claimsRecDate"))
        return self._execute(query, values)

    def get_claim_case_by_id(self, claim_id):
        query = "SELECT * FROM claim_case WHERE claim_id = %s"
        return self._fetch_one(query, (claim_id,))

    def get_re_claim_case_by_id(self, claim_id):
        query = "SELECT * FROM claim_case WHERE claim_id = %s and review_flag = 'Y' and preauth_status = '0'"
        return self._fetch_one(query, (claim_id,))

    def update_claim_case(self, claim_id, **kwargs):
        connection = self._get_connection()
        if not connection:
            return None

        cursor = connection.cursor()
        try:
            special_fields = []
            if 'apply_date' in kwargs and kwargs['apply_date'] is None:
                special_fields.append('apply_date = NOW()')
            if 'update_time' in kwargs and kwargs['update_time'] is None:
                special_fields.append('update_time = NOW()')
            if 'sync_time' in kwargs and kwargs['sync_time'] is None:
                special_fields.append('sync_time = IF(sync_time IS NULL, NOW(), sync_time)')

            normal_fields = [f"{key} = %s" for key in kwargs if key not in ('apply_date', 'update_time', 'sync_time') or kwargs[key] is not None]
            all_fields = normal_fields + special_fields
            set_clause = ', '.join(all_fields)

            query = f"UPDATE claim_case SET {set_clause} WHERE claim_id = %s"
            values = [value for key, value in kwargs.items()
                     if key not in ('apply_date', 'update_time', 'sync_time') or kwargs[key] is not None] + [claim_id]

            cursor.execute(query, values)
            connection.commit()
        except MySQLError as e:
            logging.error(f"Error executing query: {e}")
        finally:
            cursor.close()
            connection.close()

    def delete_claim_case(self, claim_id):
        query = "DELETE FROM claim_case WHERE claim_id = %s"
        return self._execute(query, (claim_id,))

    def get_claims_to_sync_eccs(self):
        query = """
            SELECT * FROM claim_case
            WHERE sync_eccs_flag = 'N' and preauth_status = '1'
            and ai_result is not null
            and admission_date > CURDATE()
        """
        return self._fetch_all(query)

    def update_eccs_sync_result(self, claim_id, eccs_result, compare_result, compare_result_desc, eccs_reason, eccs_flag, apv_amount):
        self.update_claim_case(
            claim_id,
            sync_eccs_flag=eccs_flag,
            eccs_result=eccs_result,
            compare_result=compare_result,
            compare_result_desc=compare_result_desc,
            eccs_reason=eccs_reason,
            apv_amount=apv_amount,
            sync_time=None
        )

    def get_completed_claims(self):
        query = """
                SELECT *
                FROM claim_case c
                WHERE c.basic_info_analyzed = 1
                  AND c.documents_analyzed = 1
                  AND c.policies_analyzed = 1
                  AND c.preauth_status = '0'
                  AND c.provider_name not like '赫康%'
                  AND c.admission_date >= CURDATE()
                """
        return self._fetch_all(query)

    def get_claims_to_process_basic_info(self):
        query = """
           SELECT * FROM claim_case
           WHERE preauth_status = '0' AND basic_info_analyzed = '0'
           """
        return self._fetch_all(query)

    def update_basic_info_analyzed(self, claim_id):
        self.update_claim_case(claim_id, basic_info_analyzed='1')

    def get_claims_to_process_policies_info(self):
        query = """
        SELECT * FROM claim_case
        WHERE preauth_status = '0' AND policies_analyzed = '0'
        order by claim_id desc
        """
        return self._fetch_all(query)

    def update_policies_analyzed(self, claim_id):
        self.update_claim_case(claim_id, policies_analyzed='1')

    def get_claims_to_process_documents_info(self):
        query = """
            SELECT * FROM claim_case
            WHERE preauth_status = '0' AND documents_analyzed = '0'
            order by create_time desc
            """
        return self._fetch_all(query)

    def update_documents_analyzed(self, claim_id):
        self.update_claim_case(claim_id, documents_analyzed='1')

    def reset_claim_case_for_review(self, claim_id):
        self.update_claim_case(
            claim_id,
            basic_info_analyzed='0',
            documents_analyzed='0',
            policies_analyzed='0',
            preauth_status='0',
            sync_eccs_flag='N',
            review_flag='Y',
            apply_date=None
        )
