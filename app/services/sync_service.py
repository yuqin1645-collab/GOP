"""
同步服务层
处理与外部系统的数据同步
"""
import json
import os
import requests
from typing import List, Dict

from app.logger import setup_logger
from app.utils.dao_context import dao_context
from app.dao.blacklist_member_dao import BlacklistMemberDAO
from app.dao.claim_case_dao import ClaimCaseDAO
from app.dao.provider_dao import ProviderDAO
from app.api.middleware.error_handler import format_success_response

logging = setup_logger()


class SyncService:
    """同步服务类"""
    
    def sync_eccs_result(self) -> dict:
        """同步ECCS审核结果"""
        with dao_context() as (claim_dao, _, _, _, _):
            claims = claim_dao.get_claims_to_sync_eccs()
            logging.info(f"开始处理 {len(claims)} 个需要从ECCS同步的理赔申请")
            
            if not claims:
                return format_success_response(message="没有需要同步的理赔申请")
            
            claim_ids = [claim['claim_id'] for claim in claims]
            ai_results = {claim['claim_id']: claim['ai_result'] for claim in claims}
            
            eccs_url = os.getenv("eccsWebUrlBase") + "ai/getEccsAuthResultByList"
            headers = {"Content-Type": "application/json"}
            data = [{"claimsId": claim_id} for claim_id in claim_ids]
            
            response = requests.post(eccs_url, headers=headers, data=json.dumps(data))
            
            if response.status_code != 200:
                logging.error(f"调用ECCS接口失败，状态码：{response.status_code}")
                return {"error": "调用ECCS接口失败"}, 500
            
            response_data = response.json()
            
            if response_data.get("returnCode") != "0000":
                logging.error(f"ECCS接口返回错误码：{response_data.get('returnCode')}")
                return {"error": "ECCS接口返回错误"}, 500
            
            results = response_data.get("content")
            if not results:
                return {"warning": "ECCS接口返回content为空"}
            
            synced_count = 0
            for result in results:
                try:
                    claim_id = result.get("claimsId")
                    content = result.get("claimsStatusStr")
                    eccs_reason = result.get("eccsReason")
                    
                    rounded_amount = round(float(result.get("amount")), 2)
                    amount = int(rounded_amount) if rounded_amount.is_integer() else f"{rounded_amount:.2f}"
                    
                    if_agree_ai_result = result.get("ifAgreeAiResult")
                    
                    if not claim_id or not content:
                        logging.warning(f"ECCS返回数据不完整，缺少claim_id或content: {result}")
                        continue
                    
                    ai_result = ai_results.get(claim_id)
                    if ai_result is None:
                        logging.warning(f"找不到claim_id对应的AI结果: {claim_id}")
                        continue
                    
                    content_str = content.split('-')[0].strip()
                    
                    if if_agree_ai_result == "Apv" or str(ai_result) == "11":
                        compare_result = 1
                    else:
                        compare_result = 1 if str(ai_result) == content_str else 0
                    
                    compare_result_desc = "相同" if compare_result == 1 else "不同"
                    
                    sync_eccs_flag = 'Y'
                    if content_str and str(content_str) == "39":
                        sync_eccs_flag = 'S'
                    
                    claim_dao.update_eccs_sync_result(
                        claim_id, content, compare_result,
                        compare_result_desc, eccs_reason,
                        sync_eccs_flag, amount
                    )
                    logging.info(f"成功同步理赔申请到ECCS，理赔ID：{claim_id}")
                    synced_count += 1
                    
                except Exception as e:
                    logging.exception(f"处理理赔申请 {claim_id} ECCS同步时发生错误: {str(e)}")
                    continue
            
            return format_success_response(
                data={"synced": synced_count},
                message=f"ECCS同步处理完成，共同步 {synced_count} 个"
            )
    
    def sync_provider_info(self, providers: list) -> dict:
        """同步医疗机构信息"""
        if not isinstance(providers, list):
            return {"error": "请求体必须为数组格式"}, 400
        
        synced_count = 0
        provider_dao = ProviderDAO()
        
        for provider in providers:
            if not isinstance(provider, dict):
                logging.warning(f"跳过非字典格式的provider数据: {type(provider)}")
                continue
            
            provider_code = provider.get("providerCode", "").strip()
            if not provider_code:
                logging.warning("跳过缺少providerCode的记录")
                continue
            if len(provider_code) > 100:
                logging.warning(f"providerCode长度超限，跳过: {provider_code[:20]}...")
                continue
            
            existing_provider = provider_dao.get_provider_by_code(provider_code)
            if not existing_provider:
                logging.info(f"新增医疗机构: {provider.get('longName', '')} ({provider_code})")
                provider_dao.insert_provider(
                    provider_code=provider_code,
                    provider_name=str(provider.get("longName", ""))[:200],
                    provider_type=str(provider.get("providerType", ""))[:50],
                    gop_white_list="Y"
                )
                synced_count += 1
        
        return format_success_response(
            data={"synced": synced_count},
            message=f"同步医院处理完成，共新增 {synced_count} 个"
        )
    
    def sync_blacklist_member(self, blacks: list) -> dict:
        """同步黑名单成员"""
        if not isinstance(blacks, list):
            return {"error": "请求体必须为数组格式"}, 400
        
        synced_count = 0
        black_list_member_dao = BlacklistMemberDAO()
        
        for black in blacks:
            if not isinstance(black, dict):
                logging.warning(f"跳过非字典格式的黑名单数据: {type(black)}")
                continue
            
            black_id = black.get("id", "")
            if not black_id:
                logging.warning("跳过缺少id的黑名单记录")
                continue
            
            existing = black_list_member_dao.get_blacklist_member_by_id(black_id)
            if existing:
                black_list_member_dao.delete_blacklist_member(black_id)
            
            black_list_member_dao.insert_blacklist_member(
                id=black_id,
                name=str(black.get("name", ""))[:200],
                id_type=str(black.get("idType", ""))[:50],
                new_ic=str(black.get("newIc", ""))[:50],
                tel_mobile=str(black.get("telMobile", ""))[:50],
                remark=str(black.get("remark", ""))[:500],
                remove_remark=str(black.get("removeRemark", ""))[:500],
                source=str(black.get("source", ""))[:50],
                status=str(black.get("status", ""))[:20],
                create_by=str(black.get("createBy", ""))[:50],
                update_by=str(black.get("updateBy", ""))[:50],
                black_types=str(black.get("blackTypes", ""))[:100]
            )
            synced_count += 1
        
        return format_success_response(
            data={"synced": synced_count},
            message=f"同步黑名单处理完成，共处理 {synced_count} 个"
        )
