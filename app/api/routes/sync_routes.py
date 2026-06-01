"""
同步相关路由
处理ECCS同步、医院信息同步、黑名单同步等 API 端点
"""
import json
import os
import requests
from flask import Blueprint, jsonify, request

from app.logger import setup_logger
from app.services.sync_service import SyncService
from app.services.claim_service import ClaimService
from app.utils.dao_context import dao_context
from app.dao.claim_case_dao import ClaimCaseDAO
from app.utils.cpt_utils import get_cpt_data_as_json
from app.utils.db_utils import connection_pool
from app.llm.analysis_service import analyze_cpt, cut_document_info

logging = setup_logger()

sync_bp = Blueprint('sync', __name__, url_prefix='/api')
sync_service = SyncService()
claim_service = ClaimService()


@sync_bp.route('/syncEccsResult', methods=['POST'])
def sync_eccs_result():
    """同步ECCS审核结果"""
    try:
        result = sync_service.sync_eccs_result()
        if isinstance(result, tuple):
            return jsonify(result[0]), result[1]
        return jsonify(result), 200
    except Exception as e:
        logging.exception("发生未知错误")
        return jsonify({"error": "发生未知错误"}), 500


@sync_bp.route('/processProviderInfo', methods=['POST'])
def process_provider_info():
    """同步医疗机构信息"""
    try:
        providers = request.get_json(force=True)
        result = sync_service.sync_provider_info(providers)
        if isinstance(result, tuple):
            return jsonify(result[0]), result[1]
        return jsonify(result), 200
    except Exception as e:
        logging.exception("同步医院发生未知错误")
        return jsonify({"error": "同步医院发生未知错误"}), 500


@sync_bp.route('/processBlackListMemberInfo', methods=['POST'])
def process_black_list_member_info():
    """同步黑名单成员"""
    try:
        blacks = request.get_json(force=True)
        result = sync_service.sync_blacklist_member(blacks)
        if isinstance(result, tuple):
            return jsonify(result[0]), result[1]
        return jsonify(result), 200
    except Exception as e:
        logging.exception("同步黑名单发生未知错误")
        return jsonify({"error": "同步黑名单发生未知错误"}), 500


@sync_bp.route('/processCptCodes', methods=['POST'])
def process_cpt_codes():
    """
    处理CPT代码的API接口
    """
    try:
        with dao_context() as (claim_dao, _, document_dao, _, _):
            cpt_claim_dao = ClaimCaseDAO()
            
            query = """
                SELECT * FROM claim_case where cpt is null or cpt = ''
            """
            claims = cpt_claim_dao._fetch_all(query)
            
            if not claims:
                return jsonify({"status": "success", "message": "没有需要处理的理赔案件"}), 200
            
            logging.info(f"找到 {len(claims)} 个需要处理的理赔案件")
            
            connection = connection_pool.connection()
            cursor = connection.cursor()
            
            try:
                query = "SELECT cpt_code, description FROM cpt "
                cursor.execute(query)
                results = cursor.fetchall()
                
                if not results:
                    logging.warning("警告: CPT表中没有有效数据，返回空数组")
                    cpt_data = "[]"
                else:
                    cpt_data = json.dumps(results, ensure_ascii=False)
                    logging.info(f"CPT数据加载完成，共 {len(results)} 条记录")
            except Exception as e:
                logging.error(f"获取CPT数据时出错: {e}")
                cpt_data = "[]"
            finally:
                cursor.close()
                connection.close()
            
            logging.info(f"CPT JSON数据: {cpt_data[:100]}{'...' if len(cpt_data) > 100 else ''}")
            
            processed_count = 0
            error_count = 0
            
            for claim in claims:
                try:
                    claim_id = claim['claim_id']
                    logging.info(f"处理理赔案件: {claim_id}")
                    
                    document_entities = document_dao.get_document_analysis_by_claim_id(claim_id)
                    document_result = "".join(doc_entity['analysis_result'] for doc_entity in document_entities)
                    document_result = cut_document_info(document_result)
                    
                    cpt_result = analyze_cpt(document_result, claim['diangosis'], cpt_data)
                    cpt_code = cpt_result.get("cpt", "")
                    
                    cpt_claim_dao.update_claim_case(claim_id, cpt=cpt_code)
                    logging.info(f"已更新案件 {claim_id} 的 cpt 为 {cpt_code}")
                    processed_count += 1
                    
                except Exception as e:
                    error_count += 1
                    logging.exception(f"处理案件 {claim.get('claim_id', 'Unknown')} 时发生错误: {e}")
                    continue
            
            message = f"CPT代码处理完成，成功处理: {processed_count} 个，错误: {error_count} 个"
            logging.info(message)
            
            return jsonify({
                "status": "success", 
                "message": message,
                "processed": processed_count,
                "errors": error_count
            }), 200
            
    except Exception as e:
        logging.exception("处理CPT代码时发生未知错误")
        return jsonify({"error": "发生未知错误", "message": str(e)}), 500
