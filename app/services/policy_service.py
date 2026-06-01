"""
保单策略服务层
处理保单条款分析相关业务逻辑
"""
import os
import threading
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.logger import setup_logger
from app.utils.dao_context import dao_context
from app.utils.api_utils import get_policy_wording_url_api
from app.utils.file_utils import download_file, get_file_name_by_original_name
from app.llm.analysis_service import analyze_policy_info

logging = setup_logger()


class PolicyService:
    """保单策略服务类"""
    
    def process_policies_info(self) -> dict:
        """
        处理保单条款信息
        :return: 处理结果
        """
        with dao_context() as (claim_dao, _, _, policies_dao, _):
            claims = claim_dao.get_claims_to_process_policies_info()
            logging.info(f"开始处理 {len(claims)} 个理赔申请的保单条款分析")
            
            lock = threading.Lock()
            success_count = 0
            failed_count = 0
            
            def process_single_claim(claim):
                claim_id = claim['claim_id']
                try:
                    logging.info(f"处理理赔申请保单条款分析: {claim_id}")
                    
                    policy_info_list = get_policy_wording_url_api(claim_id)
                    if not policy_info_list:
                        logging.warning(f"无法获取保单条款 URL：{claim_id}")
                        return False
                    
                    for policy_info in policy_info_list:
                        if not policy_info:
                            logging.warning(f"无法获取保单条款 URL：{claim_id}")
                            continue
                        
                        filename = policy_info.get("fileName")
                        if not filename or not (filename.lower().endswith('.pdf') or filename.lower().endswith('.docx') or filename.lower().endswith('.xlsx')):
                            continue
                        
                        with lock:
                            results = policies_dao.get_policies_analysis_by_claim_id_and_file_name(
                                claim_id, policy_info.get("fileName")
                            )
                        
                        if results and len(results) > 0:
                            logging.info(f"已存在保单条款分析数据，跳过处理 {claim_id}")
                            continue
                        
                        pdf_url = policy_info.get("url")
                        new_pdf_url = pdf_url.replace(
                            "http://mdlcnpro.oss-cn-beijing-internal.aliyuncs.com",
                            "https://mdlcnpro.oss-cn-beijing.aliyuncs.com"
                        )
                        
                        file_path = download_file(new_pdf_url, custom_filename=get_file_name_by_original_name(filename))
                        if not file_path:
                            logging.warning(f"下载保单文件失败：{claim_id}")
                            continue
                        
                        try:
                            policy_analysis = analyze_policy_info(file_path, policy_info.get("type"))
                            if not policy_analysis:
                                logging.warning(f"保单条款分析失败：{claim_id}")
                            else:
                                with lock:
                                    policies_dao.insert_policies_analysis(
                                        claim_id=claim_id,
                                        policy_type=policy_info.get("type"),
                                        file_name=policy_info.get("fileName"),
                                        file_url=new_pdf_url,
                                        analysis_result=policy_analysis
                                    )
                        finally:
                            if file_path and os.path.exists(file_path):
                                try:
                                    os.remove(file_path)
                                    logging.debug(f"已删除临时文件：{file_path}")
                                except Exception as e:
                                    logging.warning(f"删除临时文件失败：{file_path}, 错误：{e}")
                    
                    with lock:
                        claim_dao.update_policies_analyzed(claim_id)
                    
                    return True
                    
                except Exception as e:
                    logging.exception(f"处理理赔申请 {claim_id} 时发生错误: {str(e)}")
                    return False
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_claim = {executor.submit(process_single_claim, claim): claim for claim in claims}
                
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
                        logging.exception(f"案件 {claim['claim_id']} 处理过程中出现异常: {exc}")
            
            return {
                "status": "success",
                "message": f"保单条款分析处理完成，成功: {success_count}，失败: {failed_count}",
                "success_count": success_count,
                "failed_count": failed_count
            }
