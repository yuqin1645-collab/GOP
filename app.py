import json
import os
import requests
from flask import Flask, jsonify,request

from dao.blacklist_member_dao import BlacklistMemberDAO
from dao.claim_case_dao import ClaimCaseDAO
from llm.compare_ocr_results import get_similarity_prompt, compare_ocr_results, get_ocr_results_diff
from logger import logger
from utils.cpt_utils import get_cpt_data_as_json
from utils.db_utils import connection_pool
from utils.file_utils import download_file, get_file_name, get_file_name_csv, get_file_name_by_original_name
from utils.api_utils import (
    get_claim_info_api,
    get_policy_wording_url_api,
    get_claim_documents_api, get_expensive_hosp_info_api, get_direct_pay_hosp_api
)
from llm.analysis_service import analyze_claim_info, analyze_policy_info, analyze_preauth_result, \
    analyze_claim_info_qvq, call_dashscope_application, cut_document_info, \
    analyze_document_pdf_info, analyze_diag_type, get_except_info, get_apv_info, analyze_cpt, \
    pre_analyze_preauth_result1, get_inpatient_info, pre_analyze_preauth_result2, pre_analyze_policy_exceptinfo
from utils.email_utils import EmailSender
from utils.dao_context import dao_context

# 加载环境变量
from dotenv import load_dotenv

from utils.image_quality import evaluate_image_quality
from utils.image_utils import download_and_process_image
from dao.expensise_hosp_info_dao import ExpensiseHospInfoDAO
from dao.gop_config_dao import GopConfigDAO
from utils.hospital_info import HospitalInfo

load_dotenv()

# 初始化日志
logging = logger.setup_logger()

app = Flask(__name__)


# ========== 公共函数模块 ==========

def process_claim_init(claim_info,claim_dao):
    # 插入理赔申请数据
    claim_id = claim_info.get("claimsId")

    logging.info(f"开始初始化预授权信息claimId: {claim_id}")
    claim = claim_dao.get_claim_case_by_id(claim_id)
    if claim:
        logging.info(f"已存在理赔申请数据，跳过处理 {claim_id}")
        return

    #全部完成后，再插入主表
    claim_dao.insert_claim_case(claim_id=claim_id,claim_info=claim_info)

def process_claim_re_init(claim_info,claim_dao,basic_info_dao):
    # 插入理赔申请数据
    claim_id = claim_info.get("claimsId")

    logging.info(f"开始初始化RE预授权信息claimId: {claim_id}")
    claim = claim_dao.get_re_claim_case_by_id(claim_id)
    if claim:
        logging.info(f"已存在RE理赔申请数据，跳过处理 {claim_id}")
        return
    #全部完成后，再插入主表
    claim_dao.reset_claim_case_for_review(claim_id=claim_id)
    basic_info_dao.delete_basic_info_analysis(claim_id)

def process_claim_analysis(claim, claim_dao, basic_info_dao, document_dao, policies_dao,provider_dao):
    claim_id = claim['claim_id']
    gop_type = claim['gop_type']
    provider_name = claim['provider_name']
    admission_type = claim['admission_type']

    # 获取基础信息分析结果
    basic_info_entity = basic_info_dao.get_basic_info_analysis_by_id(claim_id)
    basic_info_result = basic_info_entity['analysis_result'] if basic_info_entity else ""

    # 获取理赔材料信息分析结果
    document_entities = document_dao.get_document_analysis_by_claim_id(claim_id)
    document_result = "".join(doc_entity['analysis_result'] for doc_entity in document_entities)
    document_result = cut_document_info(document_result)

    #住院指针信息
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

    # cpt
    # if claim['cpt']:
    #     cpt_list = get_cpt_data_as_json()
    #     cpt = analyze_cpt(document_result, claim['diangosis'], cpt_list)
    #     cpt = cpt.get("cpt", "")
    # else:
    #     cpt = claim['cpt']

    # 获取保单条款分析结果
    policy_entitys_tob = policies_dao.get_policies_analysis_by_id(claim_id,"tob")
    policy_result_tob = "".join(policy_entity['analysis_result'] for policy_entity in policy_entitys_tob)

    policy_entitys_prod = policies_dao.get_policies_analysis_by_id(claim_id, "product")
    policy_result_prod = "".join(policy_entity['analysis_result'] for policy_entity in policy_entitys_prod)

    policy_except_info = pre_analyze_policy_exceptinfo(policy_result_prod,policy_result_tob)

    # 使用HospitalInfo类获取医院信息
    provider_code = claim['provider_code']
    am = claim.get('am', None)  # 获取am字段，如果不存在则为None
    hospital_info = HospitalInfo.from_provider_info(provider_name, provider_code, am, claim_id,claim['provider_cate'],claim['provider_open_for_out'])

    #price knowledge base
    price_knowledge_base = call_dashscope_application(claim_id, provider_name)

    #产品名称
    corporate_code = claim.get('corporate_code', '')  # 防止 key 不存在
    if corporate_code and 'xinyanbao' in corporate_code.lower():
        prod_type = "新燕宝"
    else:
        prod_type = "其他"

    #分析 疾病类型
    pri_diag_desc = claim.get('pri_diag_desc', '')
    if '肺炎' in pri_diag_desc:
        diag_type = '肺炎'
    elif '呼吸道感染' in pri_diag_desc:
        diag_type = '呼吸道感染'
    else:
        # diag_type = analyze_diag_type(document_result)
        diag_type = '其他'

    # 生成pre预授权结果
    if gop_type == "" or gop_type is None or gop_type == "hospital":
        # 首先尝试使用预分析方法1（基于apv_info）
        pre_result1 = pre_analyze_preauth_result1(apv_info)
        print(pre_result1)
        print("第一步预分析结果")
        # 检查pre_result1是否为None
        if pre_result1 is None:
            logging.error(f"理赔 {claim.get('claim_id', 'unknown')} 的预分析结果为空，跳过预分析")
            ai_result_str_pre = ""
            ai_result_code_pre = ""
        else:
            # 提取 ai_result_str 中的前缀编号，如 "04"
            ai_result_str_pre = pre_result1.get("result", "")
            if ai_result_str_pre and " - " in ai_result_str_pre:
                ai_result_code_pre = ai_result_str_pre.split(" - ")[0]
            else:
                ai_result_code_pre = ai_result_str_pre

        # 如果预分析方法1返回的是12，则直接使用该结果
        if ai_result_code_pre == "12":
            preauth_result = pre_result1
        else:
            pre_result2 = pre_analyze_preauth_result2(hospital_info.to_json(),claim['amount'],document_result,str(policy_except_info))
            # print("*"*50)
            print(pre_result2)
            print("第二步预分析结果")
            # 检查pre_result2是否为None
            if pre_result2 is None:
                # 如果预分析方法2失败，则直接生成完整的预授权结果
                preauth_result = analyze_preauth_result(
                    basic_info_result, document_result, policy_result_tob, policy_result_prod, str(gop_type),
                    price_knowledge_base, admission_type, prod_type, hospital_info.to_json(), except_result,
                    apv_info, inpatient_info, claim['query_details'], claim['reco_benfit']
                )
                print("第三步预分析结果")
            else:
                # 提取 ai_result_str 中的前缀编号
                ai_result_str_pre2 = pre_result2.get("result", "")
                if ai_result_str_pre2 and " - " in ai_result_str_pre2:
                    ai_result_code_pre2 = ai_result_str_pre2.split(" - ")[0]
                else:
                    ai_result_code_pre2 = ai_result_str_pre2

                # 如果预分析方法2返回的是13，则直接使用该结果
                if ai_result_code_pre2 == "13":
                    preauth_result = pre_result2
                else:
                    # 生成完整的预授权结果
                    print("第四步预分析结果")
                    preauth_result = analyze_preauth_result(
                        basic_info_result, document_result, policy_result_tob, policy_result_prod, str(gop_type),
                        price_knowledge_base, admission_type, prod_type, hospital_info.to_json(), except_result,
                        apv_info, inpatient_info, claim['query_details'], claim['reco_benfit']
                    )
    else:
        # 生成预授权结果
        print("第五步预分析结果")
        preauth_result = analyze_preauth_result(
            basic_info_result, document_result, policy_result_tob,
            policy_result_prod, str(gop_type),
            price_knowledge_base, admission_type, prod_type,
            hospital_info.to_json(), except_result,
            apv_info, inpatient_info, claim['query_details'], claim['reco_benfit']
        )

    str_preauth_result = str(preauth_result)
    print("preauth_result:",preauth_result)
    print(str_preauth_result)

    #格式化result
    if preauth_result is not None:
        ai_result_str = preauth_result.get("result", "")
    else:
        ai_result_str = ""

    # 提取 ai_result_str 中的前缀编号，如 "04"
    if ai_result_str and " - " in ai_result_str:
        ai_result_code = ai_result_str.split(" - ")[0]
    else:
        ai_result_code = ai_result_str

    old_preauth_result = claim['old_preauth_result'] if claim['old_preauth_result'] else str_preauth_result

    # 更新理赔申请状态和结果
    if preauth_result is not None:
        ai_reason = preauth_result.get("reason", "")
    else:
        ai_reason = ""
    claim_dao.update_claim_case(claim_id, diag_type=diag_type, preauth_status=1, preauth_result=str_preauth_result,
                                ai_result=ai_result_code, ai_result_desc=ai_result_str,old_preauth_result=old_preauth_result,
                                ai_reason=ai_reason, update_time=None)
    logging.info(f"Processed claim {claim_id} successfully")

    return preauth_result

# ========== 接口定义 ==========

#获取需要Gop的数据
@app.route('/api/initPreAuth', methods=['POST'])
def init_pre_auth():
    try:
        # 获取 claim_id 列表
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

        # 批量处理每个 claim_id
        for claim_info in claims_info_list:
            try:
                with dao_context() as (claim_dao, basic_info_dao, document_dao, policies_dao, _):
                    process_claim_init(claim_info,claim_dao)
            except Exception as e:
                logging.exception(f"处理理赔申请 {claim_info.get("claimsId")} 时发生错误,错误信息：{str(e)}")
                continue

    except Exception as e:
        logging.exception("发生未知错误")
        return jsonify({"error": "发生未知错误"}), 500

    return jsonify({"status": "success", "message": "所有理赔申请处理完成"}), 200


@app.route('/api/initRePreAuth', methods=['POST'])
def init_re_pre_auth():
    try:
        # 获取 claim_id 列表
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

        # 批量处理每个 claim_id
        for claim_info in claims_info_list:
            try:
                with dao_context() as (claim_dao, basic_info_dao, document_dao, policies_dao, _):
                    process_claim_re_init(claim_info,claim_dao,basic_info_dao)
            except Exception as e:
                logging.exception(f"处理理赔申请 {claim_info.get("claimsId")} 时发生错误,错误信息：{str(e)}")
                continue

    except Exception as e:
        logging.exception("发生未知错误")
        return jsonify({"error": "发生未知错误"}), 500

    return jsonify({"status": "success", "message": "所有理赔申请处理完成"}), 200

#得出Gop审核结果
@app.route('/api/genPreAuthResult', methods=['POST'])
def gen_pre_auth_result():
    try:
        with dao_context() as (claim_dao, basic_info_dao, document_dao, policies_dao,provider_dao):
            completed_claims = claim_dao.get_completed_claims()
            if len(completed_claims) == 0:
                return jsonify({"status": "success", "message": "所有理赔申请处理完成,数量为0"}), 200

            logging.info(f"Found {len(completed_claims)} completed claims to process")
            # path = os.getenv("EXCEL_PATH") + get_file_name_csv()
            # with open(path, "w", encoding="utf-8", newline="") as f:
            #     writer = csv.writer(f)
            #     writer.writerow(["ClaimId", "Result", "Reason"])


            new_completed_claims = []
            for claim in completed_claims:
                try:
                    logging.info(f"Deal {claim['claim_id']} ")
                    result = process_claim_analysis(claim, claim_dao, basic_info_dao, document_dao, policies_dao,provider_dao)

                    #预授权结果更新到eccs上
                    url = os.getenv("updatePreAuthResultUrl")
                    headers = {"Content-Type": "application/json"}
                    # 准备请求数据
                    data = {
                        "claimsId": claim['claim_id'],
                        "preAuthReason": result.get("reason", ""),
                        "preAuthResult": result.get("result", "")
                    }
                    response = requests.post(url, headers=headers, data=json.dumps(data))

                    if response.status_code != 200 and response.json().get("returnCode") != "0000":
                        logging.error(f"update preauth result failed，状态码：{response.status_code},返回码：{response.json().get("returnCode")}")
                        continue

                    # with open(path, "a", encoding="utf-8", newline="") as f:
                    #     writer = csv.writer(f)
                    #     writer.writerow([claim['claim_id'], result.get("result"), result.get("reason")])
                    #new_completed_claims.append(claim)
                except Exception as e:
                    claim_dao.update_claim_case(claim['claim_id'], preauth_status=0, preauth_result="")
                    logging.exception("Error processing claims: "+claim['claim_id'])
                    continue

            #email_sender = EmailSender()
            #email_sender.send_email(claim_ids=new_completed_claims, attachment_path=path)

    except Exception as e:
        logging.exception("Error processing claims")
        return jsonify({"error": "Failed to process claims"}), 500

    return jsonify({"status": "success", "message": "所有理赔申请处理完成"}), 200

#得出Gop审核结果 - 批量
@app.route('/api/genPreAuthResultMultiThread', methods=['POST'])
def gen_pre_auth_result_multi_thread():
    try:
        with dao_context() as (claim_dao, basic_info_dao, document_dao, policies_dao, provider_dao):
            completed_claims = claim_dao.get_completed_claims()
            if len(completed_claims) == 0:
                return jsonify({"status": "success", "message": "所有理赔申请处理完成,数量为0"}), 200

            logging.info(f"Found {len(completed_claims)} completed claims to process")
            
            # 使用多线程处理理赔案件
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading
            
            # 创建线程锁
            lock = threading.Lock()
            
            # 定义处理单个理赔案件的函数
            def process_single_claim(claim):
                try:
                    logging.info(f"Deal {claim['claim_id']} ")
                    result = process_claim_analysis(claim, claim_dao, basic_info_dao, document_dao, policies_dao, provider_dao)

                    #预授权结果更新到eccs上
                    url = os.getenv("updatePreAuthResultUrl")
                    headers = {"Content-Type": "application/json"}
                    # 准备请求数据
                    data = {
                        "claimsId": claim['claim_id'],
                        "preAuthReason": result.get("reason", ""),
                        "preAuthResult": result.get("result", "")
                    }
                    response = requests.post(url, headers=headers, data=json.dumps(data))

                    if response.status_code != 200 and response.json().get("returnCode") != "0000":
                        logging.error(f"update preauth result failed，状态码：{response.status_code},返回码：{response.json().get("returnCode")}")
                        return False

                    return True
                except Exception as e:
                    claim_dao.update_claim_case(claim['claim_id'], preauth_status=0, preauth_result="")
                    logging.exception("Error processing claims: "+claim['claim_id'])
                    return False
            
            # 使用线程池处理所有理赔案件
            max_workers = 20  # 设置最大线程数为10
            success_count = 0
            failed_count = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_claim = {executor.submit(process_single_claim, claim): claim for claim in completed_claims}
                
                # 处理完成的任务
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

    return jsonify({"status": "success", "message": f"所有理赔申请处理完成，成功: {success_count}，失败: {failed_count}"}), 200

#得出Gop审核结果
@app.route('/api/processBasicInfo', methods=['POST'])
def process_basic_info():
    try:
        with dao_context() as (claim_dao, basic_info_dao, _, _, _):
            # 查询需要处理的理赔申请
            claims = claim_dao.get_claims_to_process_basic_info()
            logging.info(f"开始处理 {len(claims)} 个理赔申请的基本信息")

            # 批量处理每个 claim_id
            for claim in claims:
                try:
                    claim_id = claim['claim_id']
                    logging.info(f"处理理赔申请基本信息: {claim_id}")

                    # 获取理赔基本数据
                    claims_info = get_claim_info_api(claim_id)
                    if not claims_info:
                        logging.warning(f"无法获取理赔信息：{claim_id}")
                        continue

                    if basic_info_dao.get_basic_info_analysis_by_id(claim_id):
                        logging.info(f"已存在理赔基本数据，跳过处理 {claim_id}")
                        continue

                    # 插入基本数据
                    basic_info_dao.insert_basic_info_analysis(
                        claim_id=claim_id,
                        analysis_result=str(claims_info)
                    )

                    # 更新 claim_case 表的 basic_info_analyzed 字段
                    claim_dao.update_basic_info_analyzed(claim_id)

                except Exception as e:
                    logging.exception(f"处理理赔申请 {claim_id} 时发生错误: {str(e)}")
                    continue

    except Exception as e:
        logging.exception("发生未知错误")
        return jsonify({"error": "发生未知错误"}), 500

    return jsonify({"status": "success", "message": "理赔基本信息处理完成"}), 200

#获取条款信息数据
@app.route('/api/processPoliciesInfo', methods=['POST'])
def process_policies_info():
    try:
        with dao_context() as (claim_dao, _, _, policies_dao, _):
            # 查询需要处理的理赔申请
            claims = claim_dao.get_claims_to_process_policies_info()
            logging.info(f"开始处理 {len(claims)} 个理赔申请的保单条款分析")

            # 使用多线程处理理赔申请
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading
            
            # 创建线程锁
            lock = threading.Lock()
            
            # 定义处理单个理赔申请的函数
            def process_single_claim(claim):
                is_error = False
                claim_id = claim['claim_id']
                try:
                    logging.info(f"处理理赔申请保单条款分析: {claim_id}")

                    # 获取保单条款信息
                    policy_info_list = get_policy_wording_url_api(claim_id)

                    for policy_info in policy_info_list:
                        if not policy_info:
                            logging.warning(f"无法获取保单条款 URL：{claim_id}")
                            is_error = True
                            continue

                        filename = policy_info.get("fileName")
                        if not filename or not (filename.lower().endswith('.pdf') or filename.lower().endswith('.docx') or filename.lower().endswith('.xlsx')):
                            continue

                        # 线程安全地检查是否已存在分析数据
                        with lock:
                            results = policies_dao.get_policies_analysis_by_claim_id_and_file_name(claim_id, policy_info.get("fileName"))

                        if results and len(results) > 0:
                            logging.info(f"已存在保单条款分析数据，跳过处理 {claim_id}")
                            continue

                        # 下载保单 PDF 文件
                        pdf_url = policy_info.get("url")
                        new_pdf_url = pdf_url.replace(
                            "http://mdlcnpro.oss-cn-beijing-internal.aliyuncs.com",
                            "https://mdlcnpro.oss-cn-beijing.aliyuncs.com"
                        )

                        file_path = download_file(new_pdf_url, custom_filename=get_file_name_by_original_name(filename))

                        if not file_path:
                            logging.warning(f"下载保单文件失败：{claim_id}")
                            is_error = True
                            continue

                        try:
                            # 分析保单条款
                            policy_analysis = analyze_policy_info(file_path, policy_info.get("type"))

                            if not policy_analysis:
                                logging.warning(f"保单条款分析失败：{claim_id}")
                                is_error = True
                            else:
                                # 线程安全地插入分析结果
                                with lock:
                                    policies_dao.insert_policies_analysis(
                                        claim_id=claim_id,
                                        policy_type=policy_info.get("type"),
                                        file_name=policy_info.get("fileName"),
                                        file_url=new_pdf_url,
                                        analysis_result=policy_analysis
                                    )
                        finally:
                            # 使用完文件后删除
                            try:
                                if file_path and os.path.exists(file_path):
                                    os.remove(file_path)
                                    logging.debug(f"已删除临时文件：{file_path}")
                            except Exception as e:
                                logging.warning(f"删除临时文件失败：{file_path}, 错误：{e}")

                    # 线程安全地更新 claim_case 表的 policies_analyzed 字段
                    if not is_error:
                        with lock:
                            claim_dao.update_policies_analyzed(claim_id)
                    
                    return not is_error
                    
                except Exception as e:
                    logging.exception(f"处理理赔申请 {claim_id} 时发生错误: {str(e)}")
                    return False
            
            # 使用线程池处理所有理赔申请
            max_workers = 5  # 设置最大线程数为10
            success_count = 0
            failed_count = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_claim = {executor.submit(process_single_claim, claim): claim for claim in claims}
                
                # 处理完成的任务
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

    except Exception as e:
        logging.exception("发生未知错误")
        return jsonify({"error": "发生未知错误"}), 500

    return jsonify({"status": "success", "message": f"保单条款分析处理完成，成功: {success_count}，失败: {failed_count}"}), 200

#获取上传的图片信息数据
@app.route('/api/processDocumentsInfo', methods=['POST'])
def process_documents_info():
    try:
        with dao_context() as (claim_dao, _, document_dao, _, _):
            # 查询需要处理的理赔申请
            claims = claim_dao.get_claims_to_process_documents_info()
            logging.info(f"开始处理 {len(claims)} 个理赔申请的文档分析")

            # 批量处理每个 claim_id
            for claim in claims:
                has_error = False
                try:
                    claim_id = claim['claim_id']
                    logging.info(f"处理理赔申请文档分析: {claim_id}")

                    # 获取理赔资料信息
                    document_info = get_claim_documents_api(claim_id)

                    if not document_info:
                        logging.warning(f"无法获取理赔资料链接：{claim_id}")
                        continue

                    # 使用多线程处理每个文档
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    import threading
                    
                    # 创建线程锁，用于保护共享资源
                    lock = threading.Lock()
                    
                    def process_single_document(img_info):
                        nonlocal has_error
                        file_name = img_info.get("fileName", "")
                        # 处理扩展名可能带有括号的情况，如 "xxx).pdf"
                        normalized_file_name = file_name.lower().replace(')', '.').replace(']', '.')
                        supported_extensions = ('heic', '.jpg', '.png', ".jpeg", '.jfif', '.pdf', '.docx', '.xlsx')
                        if not any(normalized_file_name.endswith(ext) for ext in supported_extensions):
                            logging.info(f"不支持的文件类型，跳过：{file_name}")
                            return False

                        # 检查是否已存在分析数据
                        with lock:
                            document_results = document_dao.get_documents_analysis_by_claim_id_and_file_name(
                                claim_id,
                                img_info.get("fileName")
                            )

                        if document_results and len(document_results) > 0:
                            logging.info(f"已存在分析数据，跳过：{file_name}")
                            return False

                        # 处理URL
                        doc_url = img_info.get("url")
                        new_doc_url = doc_url.replace(
                            "http://mdlcnpro.oss-cn-beijing-internal.aliyuncs.com",
                            "https://mdlcnpro.oss-cn-beijing.aliyuncs.com"
                        )

                        if not any(normalized_file_name.endswith(ext) for ext in ('.pdf','.docx','.xlsx')):
                            # 检查URL是否有效
                            if not new_doc_url or not new_doc_url.startswith('http'):
                                logging.warning(f"无效的文档URL：{claim_id}, URL: {new_doc_url}")
                                return False

                            llm_analys_url = download_and_process_image(new_doc_url)

                            # 检查图片处理结果
                            if not llm_analys_url:
                                logging.warning(f"图片处理失败，跳过：{claim_id}, URL: {new_doc_url}")
                                return False

                            # 分析理赔资料
                            analysis = analyze_claim_info(llm_analys_url)
                            analysis_bak = analyze_claim_info_qvq(llm_analys_url)

                            # 如果分析失败但不是内容审核问题，则记录错误
                            if not analysis:
                                logging.warning(f"理赔资料分析失败（非审核原因）：{claim_id}, 文件名: {img_info.get('fileName')}")
                                # 可能是内容审核失败，日志已记录，继续处理
                            if not analysis_bak:
                                logging.warning(f"理赔资料QVQ分析失败（非审核原因）：{claim_id}, 文件名: {img_info.get('fileName')}")
                                # 可能是内容审核失败，日志已记录，继续处理

                            # 处理None值，避免后续函数报错
                            analysis = analysis or ""
                            analysis_bak = analysis_bak or ""

                            #置信度
                            image_quality = evaluate_image_quality(new_doc_url)
                            #相似度
                            consistency = compare_ocr_results(analysis, analysis_bak) if analysis and analysis_bak else None
                            # 不同
                            diff = get_ocr_results_diff(analysis, analysis_bak) if analysis and analysis_bak else None

                            # 插入分析结果
                            with lock:
                                document_dao.insert_document_analysis(
                                    claim_id=claim_id,
                                    image_quality=image_quality,
                                    consistency = consistency,
                                    diff = diff,
                                    file_name=img_info.get("fileName"),
                                    file_url=new_doc_url,
                                    analysis_result=analysis,
                                )
                            return True
                        else:
                            file_path = download_file(new_doc_url,custom_filename=get_file_name_by_original_name(img_info.get("fileName")))

                            if not file_path:
                                logging.warning(f"下载保单文件失败：{claim_id}")
                                with lock:
                                    has_error = True
                                return False

                            try:
                                # 分析保单条款
                                policy_analysis = analyze_document_pdf_info(file_path)

                                if not policy_analysis:
                                    # 检查是否是文件损坏原因
                                    logging.warning(f"保单条款分析失败（可能是PDF损坏或内容审核）：{claim_id}, 文件名: {img_info.get('fileName')}")
                                else:
                                    # 插入分析结果
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
                                # 使用完文件后删除
                                try:
                                    if file_path and os.path.exists(file_path):
                                        os.remove(file_path)
                                        logging.debug(f"已删除临时文件：{file_path}")
                                except Exception as e:
                                    logging.warning(f"删除临时文件失败：{file_path}, 错误：{e}")
                    
                    # 使用线程池处理所有文档
                    with ThreadPoolExecutor(max_workers=10) as executor:
                        # 提交所有任务
                        future_to_img = {executor.submit(process_single_document, img_info): img_info for img_info in document_info}
                        
                        # 等待所有任务完成
                        for future in as_completed(future_to_img):
                            img_info = future_to_img[future]
                            try:
                                result = future.result()
                                if not result:
                                    logging.info(f"处理文档失败（已在上方记录具体原因）：{img_info.get('fileName')}")
                            except Exception as exc:
                                logging.exception(f"处理文档 {img_info.get('fileName')} 时发生异常: {exc}")
                                with lock:
                                    has_error = True
                    
                    # 如果没有错误，更新状态
                    if not has_error:
                        claim_dao.update_documents_analyzed(claim_id)

                except Exception as e:
                    logging.exception(f"处理理赔申请 {claim_id} 时发生错误: {str(e)}")
                    continue

    except Exception as e:
        logging.exception("发生未知错误")
        return jsonify({"error": "发生未知错误"}), 500

    return jsonify({"status": "success", "message": "理赔文档分析处理完成"}), 200

@app.route('/api/processProviderInfo', methods=['POST'])
def processProviderInfo():
    try:
        providers = request.get_json(force=True)
        print(providers)
        for provider in providers:
            # 去除providerCode前后的空格
            provider_code = provider.get("providerCode", "").strip()
            with dao_context() as (_, _, _, _, provider_dao):
                existing_provider = provider_dao.get_provider_by_code(provider_code)
                if not existing_provider:
                    print(provider.get("longName", ""))
                    # 如果供应商不存在，则插入新记录
                    provider_dao.insert_provider(
                        provider_code=provider_code,
                        provider_name=provider.get("longName", ""),
                        provider_type=provider.get("providerType", ""),
                        gop_white_list="Y"
                    )
    except Exception as e:
        logging.exception("同步医院发生未知错误")
        return jsonify({"error": "同步医院发生未知错误"}), 500

    return jsonify({"status": "success", "message": "同步医院处理完成"}), 200

@app.route('/api/processBlackListMemberInfo', methods=['POST'])
def processBlackListMemberInfo():
    try:
        blacks = request.get_json(force=True)
        for black in blacks:
            # 去除providerCode前后的空格
            black_id = black.get("id", "")
            black_list_member_dao = BlacklistMemberDAO()
            existing_provider = black_list_member_dao.get_blacklist_member_by_id(black_id)
            if existing_provider:
                black_list_member_dao.delete_blacklist_member(black_id)

            black_list_member_dao.insert_blacklist_member(
                id=black_id,
                name=black.get("name", ""),
                id_type=black.get("idType", ""),
                new_ic=black.get("newIc", ""),
                tel_mobile=black.get("telMobile", ""),
                remark=black.get("remark", ""),
                remove_remark=black.get("removeRemark", ""),
                source=black.get("source", ""),
                status=black.get("status", ""),
                create_by=black.get("createBy", ""),
                update_by=black.get("updateBy", ""),
                black_types=black.get("blackTypes", "")
            )

    except Exception as e:
        logging.exception("同步黑名单发生未知错误")
        return jsonify({"error": "同步黑名单发生未知错误"}), 500

    return jsonify({"status": "success", "message": "同步黑名单处理完成"}), 200


@app.route('/api/syncEccsResult', methods=['POST'])
def sync_eccs_result():
    try:
        with dao_context() as (claim_dao, _, _, _, _):
            # 1. 查询sync_eccs_flag = 'N'的理赔案件
            claims = claim_dao.get_claims_to_sync_eccs()
            logging.info(f"开始处理 {len(claims)} 个需要从ECCS同步的理赔申请")

            if not claims:
                return jsonify({"status": "success", "message": "没有需要同步的理赔申请"}), 200

            # 2. 构造批量请求参数
            claim_ids = [claim['claim_id'] for claim in claims]
            ai_results = {claim['claim_id']: claim['ai_result'] for claim in claims}
            
            eccs_url = os.getenv("eccsWebUrlBase") + "ai/getEccsAuthResultByList"
            headers = {"Content-Type": "application/json"}
            data = [{"claimsId": claim_id} for claim_id in claim_ids]

            # 3. 调用接口获取ECCS结果（批量）
            response = requests.post(eccs_url, headers=headers, data=json.dumps(data))

            if response.status_code != 200:
                logging.error(f"调用ECCS接口失败，状态码：{response.status_code}")
                return jsonify({"error": "调用ECCS接口失败"}), 500

            response_data = response.json()

            # 检查返回码
            if response_data.get("returnCode") != "0000":
                logging.error(f"ECCS接口返回错误码：{response_data.get('returnCode')}，信息：{response_data.get('returnMsg')}")
                return jsonify({"error": "ECCS接口返回错误"}), 500

            # 4. 获取content
            results = response_data.get("content")
            if not results:
                logging.warning("ECCS接口返回content为空")
                return jsonify({"warning": "ECCS接口返回content为空"}), 200

            # 5. 处理每个理赔案件的结果
            for result in results:
                try:
                    claim_id = result.get("claimsId")
                    content = result.get("claimsStatusStr")
                    eccs_reason = result.get("eccsReason")

                    rounded_amount = round(float(result.get("amount")), 2)
                    # 如果小数部分为.00，则转换为整数
                    if rounded_amount.is_integer():
                        amount = int(rounded_amount)
                    else:
                        amount = f"{rounded_amount:.2f}"

                    if_agree_ai_result = result.get("ifAgreeAiResult")
                    
                    if not claim_id or not content:
                        logging.warning(f"ECCS返回数据不完整，缺少claim_id或content: {result}")
                        continue
                    
                    ai_result = ai_results.get(claim_id)
                    if ai_result is None:
                        logging.warning(f"找不到claim_id对应的AI结果: {claim_id}")
                        continue

                    # 6. 比较ai_result和content是否相等
                    content_str = content.split('-')[0].strip()
                    # 合并两个条件：ai_result为"11"或if_agree_ai_result为"Apv"时compare_result为1
                    if if_agree_ai_result == "Apv" or str(ai_result) == "11":
                        compare_result = 1
                    else:
                        compare_result = 1 if str(ai_result) == content_str else 0

                    compare_result_desc = "相同" if compare_result == 1 else "不同"

                    # 7. 更新sync_eccs_flag, eccs_result和compare_result
                    sync_eccs_flag = 'Y'
                    if content_str and str(content_str) == "39":
                        sync_eccs_flag = 'S'

                    claim_dao.update_eccs_sync_result(
                        claim_id, 
                        content, 
                        compare_result,
                        compare_result_desc,
                        eccs_reason,
                        sync_eccs_flag,
                        amount
                    )
                    logging.info(f"成功同步理赔申请到ECCS，理赔ID：{claim_id}，ECCS结果：{content}，比较结果：{compare_result}")

                except Exception as e:
                    logging.exception(f"处理理赔申请 {claim_id} ECCS同步时发生错误: {str(e)}")
                    continue

    except Exception as e:
        logging.exception("发生未知错误")
        return jsonify({"error": "发生未知错误"}), 500

    return jsonify({"status": "success", "message": "ECCS同步处理完成"}), 200


@app.route('/api/processCptCodes', methods=['POST'])
def process_cpt_codes():
    """
    处理CPT代码的API接口，执行与cpt.py中main函数相同的逻辑
    """
    try:
        with dao_context() as (claim_dao, _, document_dao, _, _):
            # 创建与cpt.py中相同的ClaimCaseDAO实例
            cpt_claim_dao = ClaimCaseDAO()
            
            # 查询 diag_type 为 NULL 且 documents_analyzed = '1' 的理赔案件
            query = """
                SELECT * FROM claim_case where cpt is null or cpt = ''
            """
            claims = cpt_claim_dao._fetch_all(query)
            
            if not claims:
                return jsonify({"status": "success", "message": "没有需要处理的理赔案件"}), 200
            
            logging.info(f"找到 {len(claims)} 个需要处理的理赔案件")
            
            # 获取CPT数据并转换为JSON字符串
            connection = connection_pool.connection()
            cursor = connection.cursor()
            
            try:
                query = "SELECT cpt_code, description FROM cpt "
                cursor.execute(query)
                results = cursor.fetchall()
                
                # 检查是否有结果
                if not results:
                    logging.warning("警告: CPT表中没有有效数据，返回空数组")
                    cpt_data = "[]"
                else:
                    # 转换为JSON格式的字符串
                    cpt_data = json.dumps(results, ensure_ascii=False)
                    logging.info(f"CPT数据加载完成，共 {len(results)} 条记录")
            except Exception as e:
                logging.error(f"获取CPT数据时出错: {e}")
                # 返回空数组的JSON字符串作为默认值
                cpt_data = "[]"
            finally:
                cursor.close()
                connection.close()
            
            logging.info(f"CPT JSON数据: {cpt_data[:100]}{'...' if len(cpt_data) > 100 else ''}")
            
            # 处理每个理赔案件
            processed_count = 0
            error_count = 0
            
            for claim in claims:
                try:
                    claim_id = claim['claim_id']
                    logging.info(f"处理理赔案件: {claim_id}")
                    
                    # 获取文档分析结果
                    document_entities = document_dao.get_document_analysis_by_claim_id(claim_id)
                    document_result = "".join(doc_entity['analysis_result'] for doc_entity in document_entities)
                    document_result = cut_document_info(document_result)
                    
                    # 分析CPT代码
                    cpt_result = analyze_cpt(document_result, claim['diangosis'], cpt_data)
                    cpt_code = cpt_result.get("cpt", "")
                    
                    # 更新数据库
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)