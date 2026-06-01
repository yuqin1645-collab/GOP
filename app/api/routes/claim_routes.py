"""
理赔相关路由
处理理赔初始化、预授权生成等 API 端点
"""
import json
import os
import requests
from flask import Blueprint, jsonify, request
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from app.logger import setup_logger
from app.utils.dao_context import dao_context
from app.services.claim_service import ClaimService
from app.api.middleware.error_handler import format_success_response

logging = setup_logger()

claim_bp = Blueprint('claims', __name__, url_prefix='/api')
claim_service = ClaimService()


@claim_bp.route('/initPreAuth', methods=['POST'])
def init_pre_auth():
    """获取需要Gop的数据"""
    try:
        url = os.getenv("getGopClaimListUrl")
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers)
        
        if response.status_code != 200:
            logging.error(f"获取理赔号失败，状态码：{response.status_code}")
            return jsonify({"error": "获取理赔号失败"}), 500
        
        try:
            claims_list = response.json()
            claims_info_list = claims_list.get("content") if claims_list.get("content") else []
        except json.JSONDecodeError:
            logging.error("响应内容不是合法的 JSON 格式")
            return jsonify({"error": "响应内容不是合法的 JSON 格式"}), 500
        
        logging.info(f"开始处理 {len(claims_info_list)} 个理赔申请")
        
        for claim_info in claims_info_list:
            try:
                with dao_context() as (claim_dao, basic_info_dao, document_dao, policies_dao, _):
                    claim_service.process_claim_init(claim_info, claim_dao)
            except Exception as e:
                logging.exception(f"处理理赔申请 {claim_info.get('claimsId')} 时发生错误: {str(e)}")
                continue
        
    except Exception as e:
        logging.exception("发生未知错误")
        return jsonify({"error": "发生未知错误"}), 500
    
    return jsonify({"status": "success", "message": "所有理赔申请处理完成"}), 200


@claim_bp.route('/initRePreAuth', methods=['POST'])
def init_re_pre_auth():
    """获取需要RE Gop的数据"""
    try:
        url = os.getenv("getReGopClaimListUrl")
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers)
        
        if response.status_code != 200:
            logging.error(f"获取RE理赔号失败，状态码：{response.status_code}")
            return jsonify({"error": "获取RE理赔号失败"}), 500
        
        try:
            claims_list = response.json()
            claims_info_list = claims_list.get("content") if claims_list.get("content") else []
        except json.JSONDecodeError:
            logging.error("RE响应内容不是合法的 JSON 格式")
            return jsonify({"error": "RE响应内容不是合法的 JSON 格式"}), 500
        
        logging.info(f"RE开始处理 {len(claims_info_list)} 个理赔申请")
        
        for claim_info in claims_info_list:
            try:
                with dao_context() as (claim_dao, basic_info_dao, document_dao, policies_dao, _):
                    claim_service.process_claim_re_init(claim_info, claim_dao, basic_info_dao)
            except Exception as e:
                logging.exception(f"处理理赔申请 {claim_info.get('claimsId')} 时发生错误: {str(e)}")
                continue
        
    except Exception as e:
        logging.exception("发生未知错误")
        return jsonify({"error": "发生未知错误"}), 500
    
    return jsonify({"status": "success", "message": "所有理赔申请处理完成"}), 200


@claim_bp.route('/genPreAuthResult', methods=['POST'])
def gen_pre_auth_result():
    """得出Gop审核结果（单线程）"""
    try:
        with dao_context() as (claim_dao, basic_info_dao, document_dao, policies_dao, provider_dao):
            completed_claims = claim_dao.get_completed_claims()
            if len(completed_claims) == 0:
                return jsonify({"status": "success", "message": "所有理赔申请处理完成,数量为0"}), 200
            
            logging.info(f"Found {len(completed_claims)} completed claims to process")
            
            for claim in completed_claims:
                try:
                    logging.info(f"Deal {claim['claim_id']} ")
                    result = claim_service.process_claim_analysis(claim)
                    
                    url = os.getenv("updatePreAuthResultUrl")
                    headers = {"Content-Type": "application/json"}
                    data = {
                        "claimsId": claim['claim_id'],
                        "preAuthReason": result.get("reason", ""),
                        "preAuthResult": result.get("result", "")
                    }
                    response = requests.post(url, headers=headers, data=json.dumps(data))
                    
                    if response.status_code != 200 and response.json().get("returnCode") != "0000":
                        logging.error(f"update preauth result failed，状态码：{response.status_code}")
                        continue
                        
                except Exception as e:
                    claim_dao.update_claim_case(claim['claim_id'], preauth_status=0, preauth_result="")
                    logging.exception("Error processing claims: " + claim['claim_id'])
                    continue
    
    except Exception as e:
        logging.exception("Error processing claims")
        return jsonify({"error": "Failed to process claims"}), 500
    
    return jsonify({"status": "success", "message": "所有理赔申请处理完成"}), 200


@claim_bp.route('/genPreAuthResultMultiThread', methods=['POST'])
def gen_pre_auth_result_multi_thread():
    """得出Gop审核结果 - 批量多线程"""
    try:
        with dao_context() as (claim_dao, basic_info_dao, document_dao, policies_dao, provider_dao):
            completed_claims = claim_dao.get_completed_claims()
            if len(completed_claims) == 0:
                return jsonify({"status": "success", "message": "所有理赔申请处理完成,数量为0"}), 200
            
            logging.info(f"Found {len(completed_claims)} completed claims to process")
            
            lock = threading.Lock()
            
            def process_single_claim(claim):
                claim_id = claim['claim_id']
                try:
                    logging.info(f"Deal {claim_id} ")
                    result = claim_service.process_claim_analysis(claim, lock)
                    
                    url = os.getenv("updatePreAuthResultUrl")
                    headers = {"Content-Type": "application/json"}
                    data = {
                        "claimsId": claim_id,
                        "preAuthReason": result.get("reason", ""),
                        "preAuthResult": result.get("result", "")
                    }
                    response = requests.post(url, headers=headers, data=json.dumps(data))
                    
                    if response.status_code != 200 and response.json().get("returnCode") != "0000":
                        logging.error(f"update preauth result failed，状态码：{response.status_code}")
                        return False
                    
                    return True
                except Exception as e:
                    with lock:
                        claim_dao.update_claim_case(claim_id, preauth_status=0, preauth_result="")
                    logging.exception("Error processing claims: " + claim_id)
                    return False
            
            max_workers = 3
            success_count = 0
            failed_count = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_claim = {executor.submit(process_single_claim, claim): claim for claim in completed_claims}
                
                for future in as_completed(future_to_claim):
                    claim = future_to_claim[future]
                    try:
                        success = future.result()
                        if success:
                            success_count += 1
                        else:
                            failed_count += 1
                    except Exception as exc:
                        failed_count += 1
                        with lock:
                            logging.exception(f"案件 {claim['claim_id']} 处理过程中出现异常: {exc}")
    
    except Exception as e:
        logging.exception("Error processing claims")
        return jsonify({"error": "Failed to process claims"}), 500
    
    return jsonify({
        "status": "success", 
        "message": f"所有理赔申请处理完成，成功: {success_count}，失败: {failed_count}"
    }), 200


@claim_bp.route('/processBasicInfo', methods=['POST'])
def process_basic_info():
    """处理理赔基本信息"""
    return jsonify(claim_service.process_basic_info()), 200
