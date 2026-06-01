"""
理赔业务服务层
从 app.py 迁移核心业务逻辑到独立服务类
"""
import json
import os
import threading
from typing import Optional, Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.logger import setup_logger
from app.utils.dao_context import dao_context
from app.utils.api_utils import get_claim_info_api
from app.utils.hospital_info import HospitalInfo
from app.llm.analysis_service import (
    analyze_preauth_result,
    analyze_policy_info,
    cut_document_info,
    get_except_info,
    get_apv_info,
    get_inpatient_info,
    pre_analyze_preauth_result1,
    pre_analyze_preauth_result2,
    pre_analyze_policy_exceptinfo,
    call_dashscope_application,
    analyze_diag_type,
    analyze_document_pdf_info,
    analyze_claim_info,
    analyze_claim_info_qvq,
    ENABLE_QVQ_CROSS_CHECK
)
from app.utils.image_quality import evaluate_image_quality
from app.utils.image_utils import download_and_process_image
from app.utils.file_utils import download_file, get_file_name_by_original_name
from app.api.middleware.error_handler import AppError, ExternalAPIError, LLMServiceError, format_success_response

logging = setup_logger()


class ClaimService:
    """理赔业务服务类"""
    
    def __init__(self):
        self._lock = threading.Lock()
    
    def process_claim_init(self, claim_info: dict, claim_dao) -> None:
        """
        初始化预授权信息
        :param claim_info: 理赔信息
        :param claim_dao: 理赔DAO实例
        """
        claim_id = claim_info.get("claimsId")
        logging.info(f"开始初始化预授权信息claimId: {claim_id}")
        
        claim = claim_dao.get_claim_case_by_id(claim_id)
        if claim:
            logging.info(f"已存在理赔申请数据，跳过处理 {claim_id}")
            return
        
        claim_dao.insert_claim_case(claim_id=claim_id, claim_info=claim_info)
    
    def process_claim_re_init(self, claim_info: dict, claim_dao, basic_info_dao) -> None:
        """
        初始化RE预授权信息
        :param claim_info: 理赔信息
        :param claim_dao: 理赔DAO实例
        :param basic_info_dao: 基本信息DAO实例
        """
        claim_id = claim_info.get("claimsId")
        logging.info(f"开始初始化RE预授权信息claimId: {claim_id}")
        
        claim = claim_dao.get_re_claim_case_by_id(claim_id)
        if claim:
            logging.info(f"已存在RE理赔申请数据，跳过处理 {claim_id}")
            return
        
        claim_dao.reset_claim_case_for_review(claim_id=claim_id)
        basic_info_dao.delete_basic_info_analysis(claim_id)
    
    def process_claim_analysis(self, claim: dict, lock: threading.Lock = None) -> dict:
        """
        综合分析理赔信息，生成预授权结果
        :param claim: 理赔案件信息
        :param lock: 线程锁（可选）
        :return: 预授权结果
        """
        claim_id = claim['claim_id']
        gop_type = claim['gop_type']
        provider_name = claim['provider_name']
        admission_type = claim['admission_type']
        
        with dao_context() as (claim_dao, basic_info_dao, document_dao, policies_dao, provider_dao):
            # 获取基础信息分析结果
            basic_info_entity = basic_info_dao.get_basic_info_analysis_by_id(claim_id)
            basic_info_result = basic_info_entity['analysis_result'] if basic_info_entity else ""
            
            # 获取理赔材料信息分析结果
            document_entities = document_dao.get_document_analysis_by_claim_id(claim_id)
            document_result = "".join(doc_entity['analysis_result'] for doc_entity in document_entities)
            document_result = cut_document_info(document_result)
            
            # 住院指针信息
            if admission_type == "住院":
                inpatient_info = get_inpatient_info(document_result)
            else:
                inpatient_info = "非住院申请，无需住院指征信息"
            
            if 'MGU' in claim['payor_attr']:
                apv_info = '无提前审核通过/理赔通过信息'
            else:
                apv_info = get_apv_info(document_result)
            
            # 是否除外治疗，药品
            except_result = get_except_info(document_result, claim['query_details'])
            
            # 获取保单条款分析结果
            policy_entitys_tob = policies_dao.get_policies_analysis_by_id(claim_id, "tob")
            policy_result_tob = "".join(policy_entity['analysis_result'] for policy_entity in policy_entitys_tob)
            
            policy_entitys_prod = policies_dao.get_policies_analysis_by_id(claim_id, "product")
            policy_result_prod = "".join(policy_entity['analysis_result'] for policy_entity in policy_entitys_prod)
            
            policy_except_info = pre_analyze_policy_exceptinfo(policy_result_prod, policy_result_tob)
            
            # 使用HospitalInfo类获取医院信息
            provider_code = claim['provider_code']
            am = claim.get('am', None)
            hospital_info = HospitalInfo.from_provider_info(
                provider_name, provider_code, am, claim_id,
                claim['provider_cate'], claim['provider_open_for_out']
            )
            
            # price knowledge base
            price_knowledge_base = call_dashscope_application(claim_id, provider_name)
            
            # 产品名称
            corporate_code = claim.get('corporate_code', '')
            if corporate_code and 'xinyanbao' in corporate_code.lower():
                prod_type = "新燕宝"
            else:
                prod_type = "其他"
            
            # 分析疾病类型
            pri_diag_desc = claim.get('pri_diag_desc', '')
            if '肺炎' in pri_diag_desc:
                diag_type = '肺炎'
            elif '呼吸道感染' in pri_diag_desc:
                diag_type = '呼吸道感染'
            else:
                diag_type = '其他'
            
            # 生成预授权结果
            preauth_result = self._generate_preauth_result(
                gop_type, apv_info, hospital_info, claim, document_result,
                policy_except_info, basic_info_result, policy_result_tob,
                policy_result_prod, price_knowledge_base, admission_type,
                prod_type, except_result, inpatient_info
            )
            
            str_preauth_result = str(preauth_result)
            logging.debug(f"preauth_result: {preauth_result}")
            logging.debug(str_preauth_result)
            
            # 格式化result
            if preauth_result is not None:
                ai_result_str = preauth_result.get("result", "")
                ai_reason = preauth_result.get("reason", "")
            else:
                ai_result_str = ""
                ai_reason = ""
            
            # 提取 ai_result_str 中的前缀编号
            if ai_result_str and " - " in ai_result_str:
                ai_result_code = ai_result_str.split(" - ")[0]
            else:
                ai_result_code = ai_result_str
            
            old_preauth_result = claim['old_preauth_result'] if claim['old_preauth_result'] else str_preauth_result
            
            # 更新理赔申请状态和结果
            update_kwargs = dict(
                claim_id=claim_id,
                diag_type=diag_type,
                preauth_status=1,
                preauth_result=str_preauth_result,
                ai_result=ai_result_code,
                ai_result_desc=ai_result_str,
                old_preauth_result=old_preauth_result,
                ai_reason=ai_reason,
                update_time=None
            )
            
            if lock:
                with lock:
                    claim_dao.update_claim_case(**update_kwargs)
            else:
                claim_dao.update_claim_case(**update_kwargs)
            
            logging.info(f"Processed claim {claim_id} successfully")
            return preauth_result
    
    def _generate_preauth_result(
        self, gop_type, apv_info, hospital_info, claim, document_result,
        policy_except_info, basic_info_result, policy_result_tob,
        policy_result_prod, price_knowledge_base, admission_type,
        prod_type, except_result, inpatient_info
    ) -> Optional[dict]:
        """生成预授权结果（内部方法）"""
        if gop_type == "" or gop_type is None or gop_type == "hospital":
            # 首先尝试使用预分析方法1（基于apv_info）
            pre_result1 = pre_analyze_preauth_result1(apv_info)
            logging.debug(f"第一步预分析结果: {pre_result1}")
            
            if pre_result1 is None:
                logging.error(f"理赔 {claim.get('claim_id', 'unknown')} 的预分析结果为空，跳过预分析")
                return None
            
            ai_result_str_pre = pre_result1.get("result", "")
            if ai_result_str_pre and " - " in ai_result_str_pre:
                ai_result_code_pre = ai_result_str_pre.split(" - ")[0]
            else:
                ai_result_code_pre = ai_result_str_pre
            
            # 如果预分析方法1返回的是12，则直接使用该结果
            if ai_result_code_pre == "12":
                return pre_result1
            
            # 尝试预分析方法2
            pre_result2 = pre_analyze_preauth_result2(
                hospital_info.to_json(), claim['amount'], document_result, str(policy_except_info)
            )
            logging.debug(f"第二步预分析结果: {pre_result2}")
            
            if pre_result2 is None:
                # 如果预分析方法2失败，则直接生成完整的预授权结果
                return analyze_preauth_result(
                    basic_info_result, document_result, policy_result_tob, policy_result_prod, str(gop_type),
                    price_knowledge_base, admission_type, prod_type, hospital_info.to_json(), except_result,
                    apv_info, inpatient_info, claim['query_details'], claim['reco_benfit']
                )
            
            ai_result_str_pre2 = pre_result2.get("result", "")
            if ai_result_str_pre2 and " - " in ai_result_str_pre2:
                ai_result_code_pre2 = ai_result_str_pre2.split(" - ")[0]
            else:
                ai_result_code_pre2 = ai_result_str_pre2
            
            if ai_result_code_pre2 == "13":
                return pre_result2
            
            # 生成完整的预授权结果
            return analyze_preauth_result(
                basic_info_result, document_result, policy_result_tob, policy_result_prod, str(gop_type),
                price_knowledge_base, admission_type, prod_type, hospital_info.to_json(), except_result,
                apv_info, inpatient_info, claim['query_details'], claim['reco_benfit']
            )
        else:
            # 非 hospital 类型，调用完整分析
            logging.info("第五步预分析结果（非 hospital 类型，调用完整分析）")
            return analyze_preauth_result(
                basic_info_result, document_result, policy_result_tob,
                policy_result_prod, str(gop_type),
                price_knowledge_base, admission_type, prod_type,
                hospital_info.to_json(), except_result,
                apv_info, inpatient_info, claim['query_details'], claim['reco_benfit']
            )
    
    def process_basic_info(self) -> dict:
        """处理理赔基本信息"""
        with dao_context() as (claim_dao, basic_info_dao, _, _, _):
            claims = claim_dao.get_claims_to_process_basic_info()
            logging.info(f"开始处理 {len(claims)} 个理赔申请的基本信息")
            
            processed_count = 0
            for claim in claims:
                try:
                    claim_id = claim['claim_id']
                    logging.info(f"处理理赔申请基本信息: {claim_id}")
                    
                    claims_info = get_claim_info_api(claim_id)
                    if not claims_info:
                        logging.warning(f"无法获取理赔信息：{claim_id}")
                        continue
                    
                    if basic_info_dao.get_basic_info_analysis_by_id(claim_id):
                        logging.info(f"已存在理赔基本数据，跳过处理 {claim_id}")
                        continue
                    
                    basic_info_dao.insert_basic_info_analysis(
                        claim_id=claim_id,
                        analysis_result=str(claims_info)
                    )
                    
                    claim_dao.update_basic_info_analyzed(claim_id)
                    processed_count += 1
                    
                except Exception as e:
                    logging.exception(f"处理理赔申请 {claim_id} 时发生错误: {str(e)}")
                    continue
            
            return format_success_response(
                data={"processed": processed_count},
                message=f"理赔基本信息处理完成，共处理 {processed_count} 个"
            )
    
    def process_documents_info(self) -> dict:
        """处理理赔文档信息"""
        with dao_context() as (claim_dao, _, document_dao, _, _):
            claims = claim_dao.get_claims_to_process_documents_info()
            logging.info(f"开始处理 {len(claims)} 个理赔申请的文档分析")
            
            total_processed = 0
            for claim in claims:
                has_error = False
                try:
                    claim_id = claim['claim_id']
                    logging.info(f"处理理赔申请文档分析: {claim_id}")
                    
                    document_info = self._get_claim_documents(claim_id)
                    if not document_info:
                        logging.warning(f"无法获取理赔资料链接：{claim_id}")
                        continue
                    
                    doc_processed = self._process_documents_parallel(
                        claim_id, document_info, document_dao
                    )
                    total_processed += doc_processed
                    
                    if not has_error:
                        claim_dao.update_documents_analyzed(claim_id)
                        
                except Exception as e:
                    logging.exception(f"处理理赔申请 {claim_id} 时发生错误: {str(e)}")
                    continue
            
            return format_success_response(
                data={"processed": total_processed},
                message=f"理赔文档分析处理完成，共处理 {total_processed} 个文档"
            )
    
    def _get_claim_documents(self, claim_id: str) -> list:
        """获取理赔文档列表"""
        from app.utils.api_utils import get_claim_documents_api
        return get_claim_documents_api(claim_id) or []
    
    def _process_documents_parallel(self, claim_id: str, document_info: list, document_dao) -> int:
        """并行处理文档"""
        lock = threading.Lock()
        processed_count = 0
        
        def process_single_document(img_info):
            nonlocal processed_count
            return self._process_single_document(
                claim_id, img_info, document_dao, lock
            )
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_img = {
                executor.submit(process_single_document, img_info): img_info 
                for img_info in document_info
            }
            
            for future in as_completed(future_to_img):
                try:
                    result = future.result()
                    if result:
                        processed_count += 1
                except Exception as exc:
                    img_info = future_to_img[future]
                    logging.exception(f"处理文档 {img_info.get('fileName')} 时发生异常: {exc}")
        
        return processed_count
    
    def _process_single_document(self, claim_id: str, img_info: dict, document_dao, lock: threading.Lock) -> bool:
        """处理单个文档"""
        file_name = img_info.get("fileName", "")
        normalized_file_name = file_name.lower().replace(')', '.').replace(']', '.')
        supported_extensions = ('heic', '.jpg', '.png', ".jpeg", '.jfif', '.pdf', '.docx', '.xlsx')
        
        if not any(normalized_file_name.endswith(ext) for ext in supported_extensions):
            logging.info(f"不支持的文件类型，跳过：{file_name}")
            return False
        
        with lock:
            document_results = document_dao.get_documents_analysis_by_claim_id_and_file_name(
                claim_id, img_info.get("fileName")
            )
        
        if document_results and len(document_results) > 0:
            logging.info(f"已存在分析数据，跳过：{file_name}")
            return False
        
        doc_url = img_info.get("url")
        new_doc_url = doc_url.replace(
            "http://mdlcnpro.oss-cn-beijing-internal.aliyuncs.com",
            "https://mdlcnpro.oss-cn-beijing.aliyuncs.com"
        )
        
        is_pdf_like = any(normalized_file_name.endswith(ext) for ext in ('.pdf', '.docx', '.xlsx'))
        
        if not is_pdf_like:
            if not new_doc_url or not new_doc_url.startswith('http'):
                logging.warning(f"无效的文档URL：{claim_id}, URL: {new_doc_url}")
                return False
            
            llm_analys_url = download_and_process_image(new_doc_url)
            if not llm_analys_url:
                logging.warning(f"图片处理失败，跳过：{claim_id}, URL: {new_doc_url}")
                return False
            
            analysis = analyze_claim_info(llm_analys_url)
            analysis_bak = analyze_claim_info_qvq(llm_analys_url) if ENABLE_QVQ_CROSS_CHECK else None
            
            analysis = analysis or ""
            analysis_bak = analysis_bak or ""
            
            image_quality = evaluate_image_quality(new_doc_url)
            consistency = self._compare_ocr_results(analysis, analysis_bak) if analysis and analysis_bak else None
            diff = self._get_ocr_results_diff(analysis, analysis_bak) if analysis and analysis_bak else None
            
            with lock:
                document_dao.insert_document_analysis(
                    claim_id=claim_id,
                    image_quality=image_quality,
                    consistency=consistency,
                    diff=diff,
                    file_name=img_info.get("fileName"),
                    file_url=new_doc_url,
                    analysis_result=analysis,
                )
            return True
        else:
            return self._process_pdf_document(claim_id, img_info, new_doc_url, document_dao, lock)
    
    def _process_pdf_document(self, claim_id: str, img_info: dict, new_doc_url: str, document_dao, lock: threading.Lock) -> bool:
        """处理PDF文档"""
        file_path = None
        try:
            file_path = download_file(new_doc_url, custom_filename=get_file_name_by_original_name(img_info.get("fileName")))
            if not file_path:
                logging.warning(f"下载保单文件失败：{claim_id}")
                return False
            
            policy_analysis = analyze_document_pdf_info(file_path)
            
            if not policy_analysis:
                logging.warning(f"保单条款分析失败（可能是PDF损坏或内容审核）：{claim_id}, 文件名: {img_info.get('fileName')}")
            else:
                with lock:
                    document_dao.insert_document_analysis(
                        claim_id=claim_id,
                        image_quality='',
                        consistency='',
                        diff='',
                        file_name=img_info.get("fileName"),
                        file_url=new_doc_url,
                        analysis_result=policy_analysis,
                    )
            return True
        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logging.debug(f"已删除临时文件：{file_path}")
                except Exception as e:
                    logging.warning(f"删除临时文件失败：{file_path}, 错误：{e}")
    
    def _compare_ocr_results(self, result_a: str, result_b: str) -> Optional[float]:
        """比较OCR结果一致性"""
        try:
            from app.llm.compare_ocr_results import compare_ocr_results
            return compare_ocr_results(result_a, result_b)
        except Exception:
            return None
    
    def _get_ocr_results_diff(self, result_a: str, result_b: str) -> Optional[str]:
        """获取OCR结果差异"""
        try:
            from app.llm.compare_ocr_results import get_ocr_results_diff
            return get_ocr_results_diff(result_a, result_b)
        except Exception:
            return None
