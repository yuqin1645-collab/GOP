"""
文档处理路由
处理理赔文档分析相关 API 端点
"""
from flask import Blueprint, jsonify

from app.logger import setup_logger
from app.services.claim_service import ClaimService
from app.services.policy_service import PolicyService

logging = setup_logger()

document_bp = Blueprint('documents', __name__, url_prefix='/api')
claim_service = ClaimService()
policy_service = PolicyService()


@document_bp.route('/processDocumentsInfo', methods=['POST'])
def process_documents_info():
    """获取上传的图片信息数据"""
    try:
        result = claim_service.process_documents_info()
        return jsonify(result), 200
    except Exception as e:
        logging.exception("发生未知错误")
        return jsonify({"error": "发生未知错误"}), 500


@document_bp.route('/processPoliciesInfo', methods=['POST'])
def process_policies_info():
    """获取条款信息数据"""
    try:
        result = policy_service.process_policies_info()
        return jsonify(result), 200
    except Exception as e:
        logging.exception("发生未知错误")
        return jsonify({"error": "发生未知错误"}), 500
