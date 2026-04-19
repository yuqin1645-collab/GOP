import os
import sys
import json
import re
from typing import Optional

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from dotenv import load_dotenv
from openai import OpenAI
from http import HTTPStatus
from dashscope import Application
from dao.document_analysis_dao import DocumentAnalysisDAO
from dao.gop_config_dao import GopConfigDAO
from logger import logger
from dao.prompt_dao import PromptDAO

from utils.api_utils import get_expensive_hosp_info_api

load_dotenv()
logging = logger.setup_logger()

client = OpenAI(
    api_key=os.getenv("api_key"),
    base_url=os.getenv("base_url")
)

# 从环境变量获取模型配置
MODEL_DOCUMENT_ANALYSIS = os.getenv("MODEL_DOCUMENT_ANALYSIS", "qwen-vl-plus")
MODEL_DOCUMENT_QVQ = os.getenv("MODEL_DOCUMENT_QVQ", "qvq-plus-latest")
MODEL_TEXT_ANALYSIS = os.getenv("MODEL_TEXT_ANALYSIS", "qwen3.5-plus")
MODEL_LONG_DOCUMENT = os.getenv("MODEL_LONG_DOCUMENT", "qwen-long-latest")

# 是否启用思考模式（部分模型不支持）
ENABLE_THINKING = os.getenv("ENABLE_THINKING", "true").lower() == "true"

prompt_dao = PromptDAO()
gop_config_dao = GopConfigDAO()


def create_chat_completion(model: str, messages: list, stream: bool = False, extra_body: dict = None, max_retries: int = 3):
    """
    统一的消息调用函数，处理模型兼容性问题
    
    :param model: 模型名称
    :param messages: 消息列表
    :param stream: 是否流式输出
    :param extra_body: 额外的请求参数
    :param max_retries: 最大重试次数（仅对429限流生效）
    :return: completion 对象
    """
    import time
    import random

    supports_thinking = model in ("qwen3.5-plus", MODEL_TEXT_ANALYSIS) or MODEL_TEXT_ANALYSIS in ("qwen3.5-plus", model)
    
    kwargs = {"model": model, "messages": messages, "stream": stream}
    
    if extra_body:
        if "enable_thinking" in extra_body:
            if ENABLE_THINKING and supports_thinking:
                kwargs["extra_body"] = extra_body
            else:
                filtered_body = {k: v for k, v in extra_body.items() if k != "enable_thinking"}
                if filtered_body:
                    kwargs["extra_body"] = filtered_body
        else:
            kwargs["extra_body"] = extra_body
    
    # 添加429限流重试机制
    last_error = None
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            error_msg = str(e)
            last_error = e
            
            # 检测429限流错误
            if "429" in error_msg or "limit_requests" in error_msg or "Too Many Requests" in error_msg:
                if attempt < max_retries - 1:
                    # 指数退避 + 随机抖动
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logging.warning(f"API限流，将在 {wait_time:.2f} 秒后重试 (尝试 {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error(f"API限流重试次数用尽，不再重试")
            
            # 其他错误直接抛出
            raise
    
    # 如果所有重试都失败，抛出最后一次错误
    raise last_error


def call_dashscope_application(claim_id: str, hosp_name: str) -> Optional[str]:
    """
    调用DashScope Application并返回响应文本
    :param claim_id: 理赔案件ID
    :return: 响应文本或None
    """
    try:
        document_dao = DocumentAnalysisDAO()
        # 获取理赔材料信息分析结果
        document_entities = document_dao.get_document_analysis_by_claim_id(claim_id)

        document_result = "".join(doc_entity.get('analysis_result', '') for doc_entity in document_entities)

        prompt = f""" 
               "info": {document_result},
                请从下面的info数据中提取以下信息:手术名称，疾病 不需要有其他信息
                医院名称使用 {hosp_name}
                 # 输出格式要求
                 * **必须严格遵守此JSON结构，不包含任何解释性文字、换行符或特殊字符。**
                example:
                '医院名称': 'xxxxxx', '手术名称': 'xxxxxx', '疾病': 'xxxxxx''
            """
        messages = [{"role": "user", "content": prompt}]
        completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages)
        content = completion.choices[0].message.content

        print(content)

        # 检查LLM返回的内容
        if not content:
            logging.error("LLM未返回有效内容")
            return None

        response = Application.call(
            api_key=os.getenv("api_key"),
            app_id='a966061760b343ea844a9acd8e1c91a9',
            prompt=content
        )

        if response.status_code != HTTPStatus.OK:
            logging.error(f'调用DashScope Application失败: request_id={response.request_id}, '
                          f'code={response.status_code}, message={response.message}')
            return None
        else:
            result_text = response.output.text
            logging.info(f"成功获取claim_id={claim_id}的分析结果")
            return result_text
    except Exception as e:
        logging.exception(f"调用DashScope Application时发生错误: {str(e)}")
        return None


def get_xyb_hosp_policy_by_app(hosp_name: str) -> Optional[str]:
    """
    调用DashScope Application并返回响应文本
    :param hosp_name: 医院名称
    :return: 响应文本或None
    """
    try:
        response = Application.call(
            api_key=os.getenv("api_key"),
            app_id='e9cb530857454d83bcc3e2b852be7804',
            prompt=hosp_name
        )

        if response.status_code != HTTPStatus.OK:
            logging.error(f'调用DashScope Application失败: request_id={response.request_id}, '
                          f'code={response.status_code}, message={response.message}')
            return None
        else:
            result_text = response.output.text
            logging.info(f"成功获取claim_id={hosp_name}的分析结果")
            return result_text
    except Exception as e:
        logging.exception(f"调用DashScope Application时发生错误: {str(e)}")
        return None


def analyze_claim_info(image_url: str, model_name: str = None) -> Optional[str]:
    """
    分析图像中的医疗材料，并使用缓存机制避免重复调用 OCR。
    :param image_url: 图片 URL 地址
    :param model_name: 模型名称，默认为 MODEL_DOCUMENT_ANALYSIS
    :return: 分析结果字符串 或 None
    """
    if model_name is None:
        model_name = MODEL_DOCUMENT_ANALYSIS
    try:

        prompt = prompt_dao.get_prompt_by_type("GOP_DOCUMENT")
        # prompt = """
        # ## 角色与任务
        # 您是一名专业的**医疗OCR文档识别助手**。您的核心任务是从医院或用户提交的入院相关文件中，**准确、高效地提取关键信息**，为后续的医疗保险**GOP预授权审核**提供必要的材料。
        # ---
        # ## 文件类型识别与信息提取
        # 在处理文件时，请首先**区分文件类型**。随后，针对每种文件类型，**仅提取并输出用于GOP审核的关键信息**。
        # ### 识别并提取以下文件类型及其关键信息：
        # * **身份证/护照**
        #     * 姓名
        #     * 性别
        #     * 出生日期
        #     * 证件号码
        # * **发票**
        #     * 总金额
        #     * 日期
        #     * 项目明细（如适用，包含费用和数量）
        # * **事先授权申请表**
        #     * 申请人姓名
        #     * 被保险人姓名
        #     * 申请日期
        #     * 计划入院日期
        #     * 预计出院日期
        #     * 诊断结果（初步诊断）
        #     * 申请治疗项目/手术名称
        #     * 预计费用
        #     * 主治医生姓名
        #     * 联系方式
        # * **化验单**
        #     * 患者姓名
        #     * 化验项目名称
        #     * 化验结果
        #     * 参考范围
        #     * 化验日期
        #     * 送检医院
        # * **检查报告**（如CT、MRI、X光、超声等）
        #     * 患者姓名
        #     * 检查类型
        #     * 检查日期
        #     * 影像所见/检查描述
        #     * 诊断结论/印象
        #     * 检查医院
        # ## 输出要求
        # 您的输出应**只包含提取的关键信息**，**不得有任何多余或冗余的内容**。请确保信息的**准确性和完整性**。
        # """

        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]}
        ]
        completion = create_chat_completion(model=model_name, messages=messages)

        # 安全提取 content，避免异常
        if not completion.choices:
            logging.warning(f"LLM响应没有choices，图片URL: {image_url}")
            logging.debug(f"完整响应: {completion}")
            return None

        first_choice = completion.choices[0]
        if not hasattr(first_choice, 'message') or not first_choice.message:
            logging.warning(f"LLM响应choices[0]没有message，图片URL: {image_url}")
            logging.debug(f"完整响应: {completion}")
            return None

        result = first_choice.message.content
        if not result:
            logging.warning(f"LLM返回content为空，图片URL: {image_url}")
            logging.debug(f"choices[0].message: {first_choice.message}")
            return None

        return result
    except Exception as e:
        error_msg = str(e)
        # 检测是否是内容审核失败
        if "data_inspection_failed" in error_msg or "Input data may contain inappropriate content" in error_msg:
            # 输入内容审核拒绝
            logging.error(f"输入内容审核拒绝，图片URL: {image_url}")
        elif "Output data may contain inappropriate content" in error_msg:
            # 输出内容审核拒绝
            logging.error(f"输出内容审核拒绝，图片URL: {image_url}")
        else:
            logging.info(f"分析医疗材料出错: {e}, 图片URL: {image_url}")
            logging.exception("分析医疗材料详细异常")
        return None


def analyze_claim_info_qvq(image_url: str, model_name: str = None) -> Optional[str]:
    """
    使用QVQ模型分析图像中的医疗材料，提供更精确的OCR识别结果
    :param image_url: 图片 URL 地址
    :param model_name: 要使用的模型名称，默认为 MODEL_DOCUMENT_QVQ
    :return: 分析结果字符串 或 None
    """
    if model_name is None:
        model_name = MODEL_DOCUMENT_QVQ
    dao = PromptDAO()
    prompt = dao.get_prompt_by_type("GOP_DOCUMENT")

    try:
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]}
        ]

        completion = create_chat_completion(
            model=model_name,
            messages=messages,
            stream=True
        )

        # 存储最终回复内容
        answer_content = ""

        # 流式接收响应，只收集最终回复内容
        for chunk in completion:
            if not chunk.choices:
                logging.warning(f"QVQ流式响应chunk没有choices，图片URL: {image_url}")
                continue

            delta = chunk.choices[0].delta
            if not delta:
                logging.warning(f"QVQ流式响应delta为空，图片URL: {image_url}")
                continue

            content = delta.content
            if content:  # 如果有内容，追加到 answer_content
                answer_content += content

        if not answer_content:
            logging.warning(f"QVQ模型返回content为空，图片URL: {image_url}")

        return answer_content
    except Exception as e:
        error_msg = str(e)
        # 检测是否是内容审核失败
        if "data_inspection_failed" in error_msg or "Input data may contain inappropriate content" in error_msg:
            # 输入内容审核拒绝
            logging.error(f"QVQ输入内容审核拒绝，图片URL: {image_url}")
        elif "Output data may contain inappropriate content" in error_msg:
            # 输出内容审核拒绝（模型生成的回复包含敏感信息）
            logging.error(f"QVQ输出内容审核拒绝，图片URL: {image_url}")
        else:
            logging.info(f"QVQ分析医疗材料出错: {e}, 图片URL: {image_url}")
            logging.exception("QVQ分析医疗材料详细异常")
        return None


def analyze_policy_info(file_path: str, type: str) -> Optional[str]:
    """分析保单条款 PDF 文件"""
    try:
        # 验证文件存在性和大小
        if not os.path.exists(file_path):
            logging.error(f"文件不存在：{file_path}")
            return None

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logging.error(f"文件为空：{file_path}")
            return None

        logging.info(f"开始分析保单文件：{file_path}, 大小: {file_size} bytes")

        with open(file_path, "rb") as f:
            try:
                file_object = client.files.create(file=f, purpose="file-extract")
                logging.info(f"文件上传成功，ID: {file_object.id}")
            except Exception as upload_error:
                logging.error(f"文件上传失败：{upload_error}")
                return None

        if type == 'tob':
            prompt = prompt_dao.get_prompt_by_type("GOP_POLICY")
        else:
            prompt = prompt_dao.get_prompt_by_type("GOP_POLICY_PROD")

        try:
            completion = create_chat_completion(
                model=MODEL_LONG_DOCUMENT,
                messages=[
                    {'role': 'system', 'content': f'fileid://{file_object.id}'},
                    {'role': 'user', 'content': prompt}
                ]
            )
            result = completion.choices[0].message.content
        except Exception as api_error:
            error_msg = str(api_error)
            # 检测文件损坏错误
            if "encrypted or corrupted" in error_msg or "invalid_parameter_error" in error_msg:
                logging.error(f"PDF文件损坏或加密，文件路径: {file_path}，错误: {api_error}")
            # 检测内容审核错误
            elif "data_inspection_failed" in error_msg or "inappropriate content" in error_msg.lower():
                logging.error(f"PDF内容审核拒绝，文件路径: {file_path}")
            else:
                logging.error(f"API调用失败：{api_error}")
            return None
        finally:
            # 确保删除文件
            try:
                client.files.delete(file_object.id)
                logging.info(f"文件已从DashScope删除：{file_object.id}")
            except Exception as delete_error:
                logging.warning(f"删除文件失败：{delete_error}")

        return result
    except Exception as e:
        logging.exception("分析保单条款出错")
        return None


def analyze_policy_extra_info(file_path: str) -> Optional[str]:
    """分析保单条款 PDF 文件"""
    try:
        # 验证文件存在性和大小
        if not os.path.exists(file_path):
            logging.error(f"文件不存在：{file_path}")
            return None

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logging.error(f"文件为空：{file_path}")
            return None

        logging.info(f"开始分析保单额外信息文件：{file_path}, 大小: {file_size} bytes")

        with open(file_path, "rb") as f:
            try:
                file_object = client.files.create(file=f, purpose="file-extract")
                logging.info(f"文件上传成功，ID: {file_object.id}")
            except Exception as upload_error:
                logging.error(f"文件上传失败：{upload_error}")
                return None

        prompt = prompt_dao.get_prompt_by_type("GOP_POLICY_EXTRA")

        try:
            completion = create_chat_completion(
                model=MODEL_LONG_DOCUMENT,
                messages=[
                    {'role': 'system', 'content': f'fileid://{file_object.id}'},
                    {'role': 'user', 'content': prompt}
                ]
            )
            result = completion.choices[0].message.content
        except Exception as api_error:
            logging.error(f"API调用失败：{api_error}")
            return None
        finally:
            # 确保删除文件
            try:
                client.files.delete(file_object.id)
                logging.info(f"文件已从DashScope删除：{file_object.id}")
            except Exception as delete_error:
                logging.warning(f"删除文件失败：{delete_error}")

        return result
    except Exception as e:
        logging.exception("分析保单条款出错")
        return None


def get_except_info(document_info: str,app_info:str):
    prompt = prompt_dao.get_prompt_by_type("GOP_EXCEPT")

    restricted_items = gop_config_dao.get_config_by_typ("except_medicine")

    result = {
        "user_medical_content": document_info,
        "restricted_items": restricted_items,
        "application_item": app_info
    }

    # 将字典转换为字符串
    prompt_user = str(result)

    messages = [{"role": "user", "content": prompt_user},
                {"role": "system", "content": prompt}
                ]
    completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages)
    content = completion.choices[0].message.content

    return content



def analyze_document_pdf_info(file_path: str) -> Optional[str]:
    """分析保单条款 PDF 文件"""
    try:
        # 验证文件存在性和大小
        if not os.path.exists(file_path):
            logging.error(f"文件不存在：{file_path}")
            return None

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logging.error(f"文件为空：{file_path}")
            return None

        logging.info(f"开始分析PDF文档：{file_path}, 大小: {file_size} bytes")

        with open(file_path, "rb") as f:
            try:
                file_object = client.files.create(file=f, purpose="file-extract")
                logging.info(f"文件上传成功，ID: {file_object.id}")
            except Exception as upload_error:
                logging.error(f"文件上传失败：{upload_error}")
                return None

        prompt = prompt_dao.get_prompt_by_type("GOP_DOCUMENT")

        try:
            completion = create_chat_completion(
                model=MODEL_LONG_DOCUMENT,
                messages=[
                    {'role': 'system', 'content': f'fileid://{file_object.id}'},
                    {'role': 'user', 'content': prompt}
                ]
            )
            result = completion.choices[0].message.content
        except Exception as api_error:
            logging.error(f"API调用失败：{api_error}")
            return None
        finally:
            # 确保删除文件
            try:
                client.files.delete(file_object.id)
                logging.info(f"文件已从DashScope删除：{file_object.id}")
            except Exception as delete_error:
                logging.warning(f"删除文件失败：{delete_error}")

        return result
    except Exception as e:
        logging.exception("分析保单条款出错")
        return None


#住院指针
def get_inpatient_info(document_info: str):
    prompt_system = prompt_dao.get_prompt_by_type("GOP_INPATIENT")

    dao = GopConfigDAO()

    child_inpatient_info = dao.get_config_by_typ("child_stay_hosp")

    adult_inpatient_info = dao.get_config_by_typ("adult_stay_hosp")

    prompt_user = {
        "claim_analysis": document_info,
        "child_inpatient_info": str(child_inpatient_info),
        "adult_inpatient_info": str(adult_inpatient_info)
    }
    # 将字典转换为字符串
    prompt_user = str(prompt_user)

    messages = [{"role": "user", "content": prompt_user},
                {"role": "system", "content": prompt_system}
                ]
    completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages)
    content = completion.choices[0].message.content
    return content



def cut_document_info(document_info: str):
    prompt_system ="""
    你将收到从多张图片中通过OCR或视觉识别技术提取出的信息片段。这些信息可能存在重复、碎片化或表述不一致的情况。

    你的任务是：
    1. **去重**：识别并删除重复或高度相似的内容。
    2. **合并**：将分散在不同图片中的相关信息整合为完整条目。
    3. **精简**：去除冗余词语，保留关键信息，使表达简洁清晰。
    4. **结构化**：根据内容逻辑，以结构化方式（如列表、分类或表格）输出结果。
    5. **保持原意**：不得添加未出现在原文中的信息，确保输出忠实于原始数据。
    6. **删除医院名称** 删除任何关于医院名称的信息
    
    请按以下格式输出：
    ---
    ### 精简后信息：
    - [条目1]
    - [条目2]
    - ...
    """

    prompt_user = document_info

    messages = [{"role": "user", "content": prompt_user},
                {"role": "system", "content": prompt_system}
                ]
    completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages, extra_body={"enable_thinking":True})
    content = completion.choices[0].message.content
    return content


def get_apv_info(document_info: str):
    prompt_system = """
    你将收到从多张图片中通过OCR或视觉识别技术提取出的信息片段。这些信息可能存在重复、碎片化或表述不一致的情况。

    你的任务是：
    1. 提取有没有提前审核通过/理赔通过的信息/已预授权的信息/垫付通知单/垫付金额;
     1.1 有   -> * 有提前审核通过/理赔通过/垫付信息
     1.2 没有 -> * 无提前审核通过/理赔通过/垫付信息
    2. 只输出以下2种结论，不要有分析过程
          * 有提前审核通过/理赔通过/垫付信息
          * 无提前审核通过/理赔通过/垫付信息
    """

    prompt_user = document_info

    messages = [{"role": "user", "content": prompt_user},
                {"role": "system", "content": prompt_system}
                ]
    completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages, extra_body={"enable_thinking":True}, stream=True)
    
    # 收集流式响应内容
    content = ""
    for chunk in completion:
        if chunk.choices[0].delta.content:
            content += chunk.choices[0].delta.content
    return content


def get_expensive_hospital_info(hosp_name: str,group_flag:str,claim_id:str):
    if group_flag == 'Y':
        hosp_list = get_expensive_hosp_info_api(claim_id)
    else:
        hosp_list = """
        和睦家医疗（北京和睦家医院（将台路2号）、天津、青岛、广州、深圳）、北京和睦家医疗中心启望肿瘤治疗之家、海南博鳌和睦家医疗中心
        莱佛士医疗天津/南京诊所,上海东方联合医院,新世纪医疗旗下所有医疗机构
        港安医院,香港明德医院,香港养和医院,伊丽莎白医院（新加坡）,伊丽莎白诺维娜医院（新加坡）,鹰阁医院（新加坡）
        """

    prompt_system = """
    请根据以下输入，执行一个严格的字符串完全匹配判断。本任务不涉及任何推理、解释或外部知识使用。

    ## 输入参数：
    1. 医院名称：[hospital_name]
    2. 昂贵医院名称列表：[expensive_hospital_list]（以列表形式提供）
    
    ## 执行规则：
    - 仅检查“医院名称”是否在“昂贵医院名称列表”中存在**。
    - 比较时区分中英文、全角半角、空格、标点符号等所有字符。
    - 不进行模糊匹配、相似度计算或语义理解。
    - 如果存在完全匹配 → 输出：“昂贵医院”
    - 如果不存在完全匹配 → 输出：“非昂贵医院”
    - 禁止引入任何外部知识（如医院品牌、收费标准、市场定位等）。
    - 禁止基于“High-Cost Providers”等术语进行语义推断。
    - 禁止查阅保险条款或行业共识。
    
    ## 输出格式：
    仅输出一行结果，不得包含任何解释、理由或额外信息。
    
    ## 示例：
    输入：
    - 医院名称：上海和睦家医院
    - 昂贵医院名称列表：["北京协和医院", "上海瑞金医院", "广州中山大学附属第一医院"]
    
    输出：
    非昂贵医院
    
    输入：
    - 医院名称：上海瑞金医院
    - 昂贵医院名称列表：["北京协和医院", "上海瑞金医院", "广州中山大学附属第一医院"]
    
    输出：
    昂贵医院
    """

    # 调用大模型
    prompt_user = {
        "hospital_name": hosp_name,
        "expensive_hospital_list": hosp_list
    }
    # 将字典转换为字符串
    prompt_user = str(prompt_user)

    messages = [{"role": "user", "content": prompt_user},
                {"role": "system", "content": prompt_system}
                ]
    completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages, extra_body={"enable_thinking":True}, stream=True)
    
    # 收集流式响应内容
    content = ""
    for chunk in completion:
        if chunk.choices[0].delta.content:
            content += chunk.choices[0].delta.content
    return content


def get_except_hospital_info(hosp_name: str):
    # 除外医院
    dao = GopConfigDAO()
    # 获取所有配置值
    config_values = dao.get_config_by_typ("except_medicine")

    prompt_system = """
    请根据以下输入，执行一个严格的字符串完全匹配判断。本任务不涉及任何推理、解释或外部知识使用。

    ## 输入参数：
    1. 医院名称：[hospital_name]
    2. 除外医院名称列表：[except_hospital_list]（以列表形式提供）

    ## 执行规则：
    - 仅检查“医院名称”是否在“除外医院名称列表”中存在。
    - 比较时区分中英文、全角半角、空格、标点符号等所有字符。
    - 不进行模糊匹配、相似度计算或语义理解。
    - 如果存在完全匹配 → 输出：“除外医疗机构”
    - 如果不存在完全匹配 → 输出：“非除外医疗机构”
    - 禁止引入任何外部知识（如医院品牌、收费标准、市场定位等）。
    - 禁止基于“High-Cost Providers”等术语进行语义推断。
    - 禁止查阅保险条款或行业共识。

    ## 输出格式：
    仅输出一行结果，不得包含任何解释、理由或额外信息。

    ## 示例：
    输入：
    - 医院名称：上海和睦家医院
    - 除外医院名称列表：["北京协和医院", "上海瑞金医院", "广州中山大学附属第一医院"]

    输出：
    非除外医疗机构

    输入：
    - 医院名称：上海瑞金医院
    - 昂贵医院名称列表：["北京协和医院", "上海瑞金医院", "广州中山大学附属第一医院"]

    输出：
    除外医疗机构
    """

    # 调用大模型
    prompt_user = {
        "hospital_name": hosp_name,
        "except_hospital_list": config_values
    }
    # 将字典转换为字符串
    prompt_user = str(prompt_user)

    messages = [{"role": "user", "content": prompt_user},
                {"role": "system", "content": prompt_system}
                ]
    completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages)
    content = completion.choices[0].message.content
    return content


def analyze_diag_type(claim_analysis: str):
    prompt_system = """
    请根据提供的医疗文件内容，判断申请的治疗项目是否为胃肠镜检查或治疗。仅输出“肠胃镜”或“其他”两个选项之一。
    若文件中明确提及胃镜、肠镜、胃肠镜、胃镜检查、肠镜检查、胃肠镜检查、上消化道内镜、结肠镜等关键词，则输出“肠胃镜”；否则，输出“其他”。
    """
    messages = [{"role": "user", "content": claim_analysis},
                {"role": "system", "content": prompt_system}
                ]
    completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages)
    content = completion.choices[0].message.content
    return content

def analyze_cpt(claim_analysis: str,icd: str,cpt: str):
    prompt_system = """
    你是一名专业的医疗编码专家，精通 ICD-10-CM 诊断编码与 CPT® 程序编码。

    用户将提供以下信息：
    
    "icd"：ICD-10 诊断编码
    "info"：医疗材料描述（如病历摘要、手术记录、理赔分析等）
    "cpt_candidates"：一个预定义的 CPT 候选列表，每个条目包含五位 CPT 代码及其标准中文描述（例如："99213 - 门诊中等复杂度随访就诊"）
    你的任务：
    从 cpt_candidates 列表中，选择唯一一个与 "icd" 和 "info" 最匹配、最符合临床实际的 CPT 条目。
    
    输出规则：
    
    仅输出一个 JSON 对象，格式为：{"cpt": "XXXXX - 中文描述"}
    所选内容必须严格来自用户提供的 cpt_candidates 列表，不得修改、缩写或自行编造描述
    如果 cpt_candidates 为空，或其中无任何条目与临床情况合理匹配，则输出：{"cpt": "无法确定"}
    禁止输出任何额外字段、解释、换行、注释或 Markdown
    输出必须是合法 JSON，可被程序直接解析
    示例输出：
    
    {"cpt": "27756 - 胫骨平台骨折闭合复位+石膏固定"}
    
    现在，请基于用户提供的全部信息，返回结果。
    
        
    """

    prompt_user = f"""
                "icd": {icd},
                "info": {claim_analysis}
                "cpt_candidates": {cpt}
                """

    messages = [{"role": "user", "content": prompt_user},
                {"role": "system", "content": prompt_system}
                ]
    completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages)
    content = completion.choices[0].message.content
    return json.loads(content)


def pre_analyze_preauth_result1(apv_info:str) -> Optional[dict]:

    """综合判断预授权结果"""
    try:
        # 获取prompt
        prompt_system = prompt_dao.get_prompt_by_type("GOP_PRE_APV")

        prompt_user = f"""
            "apv_info":{apv_info}   
        """

        messages = [{"role": "user", "content": prompt_user},
                    {"role": "system", "content": prompt_system}
                    ]
        completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages, extra_body={"enable_thinking":True}, stream=True)
        
        # 收集流式响应内容
        content = ""
        for chunk in completion:
            if chunk.choices[0].delta.content:
                content += chunk.choices[0].delta.content

        # 验证内容是否为空或无效
        if not content or not content.strip():
            logging.error(f"LLM返回空内容")
            return None

        # 清理思考过程（think标签内容）
        import re
        # 移除 <think>...</think> 标签内的内容
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        content = content.strip()

        try:
            result = json.loads(content)
            return result
        except json.JSONDecodeError as je:
            logging.error(f"JSON解析失败: {je}\n内容预览: {content[:500] if len(content) > 500 else content}")
            return None
    except Exception as e:
        logging.exception("生成预授权结果出错")
        return None


def pre_analyze_policy_exceptinfo(prod: str, tob: str) -> Optional[dict]:
    try:
        # 获取prompt
        prompt_system = """
            你将收到两个保险条款文件，严格按以下标识处理：
            'prod'：保单条款文件（完整保险合同，包含基础保障/责任免除等）
            'tob'：TOB福利条款文件（具体保障权益说明，含详细赔付规则）
            
             核心分析规则
            1. 文件定位
            所有分析必须基于 prod 和 tob 两个文件内容
            冲突处理：若 prod 与 tob 对同一事项的理赔责任描述存在矛盾（如一方允许赔付而另一方明确排除），以 tob 的表述为准
            示例：若 prod 说"不包含视力矫正手术"，但 tob 说"包含视力矫正手术"，则按 tob 处理并标注 (tob)
            
            2. 排除情形定义
            仅提取以下类型内容（禁止任何主观推断）：
            明确使用"不包含/不赔付/不承担/除外/免责"等字眼的条款
            因条件未满足导致的排除（等待期/地域/医疗机构/未如实告知等）
            费用类型/治疗项目/疾病状态/行为性质被明确排除
            
            3. 内容处理原则
            保留原文逻辑，用简洁语言转述
            仅标注文件来源（(prod), (tob) 或 (tob)）
            禁止：预设条目数量、添加解释、合并相似条款、使用"共XX类"等总结性表述
            
            4.特别规定
            不需要输出和医院类型相关的信息；
             例如：
               医院涵盖范围:“公立医院普通部、特需部、国际部，以及计划一指定私立医疗机构”

          输出要求（强制执行）
            markdown
            [加粗标题]
            [简洁说明] (来源)
             正确示例：
            视力矫正手术
            激光近视手术（LASIK）等屈光矫正手术不予赔付 (tob)
             错误示例：
            32类不予理赔情形（含生育/美容/高风险运动等）
            （禁止添加总结性语句）
            
             重点规避事项
            情况 处理方式
            --------------------- ----------------------------
            两文件内容一致 仅标注 (prod, tob)
            仅 prod 提及 标注 (prod)
            prod 与 tob 冲突 仅标注 (tob)（以 tob 为准）
            模糊表述（如"未列明不赔"） 忽略（无法明确界定）
            两文件均未提及 不列入清单
            
             请严格按此指令执行
            仅输出以下格式的纯文本清单（无任何额外说明）：
            markdown
            [标题]
            [说明] (tob)
            [标题]
            [说明] (prod)
            [标题]
            [说明] (prod, tob)
            注：所有条目必须可追溯至原文，例如：
            tob 中"眼科矫正手术不包含" → 标注 (tob)
            prod 和 tob 均写"生育费用不赔" → 标注 (prod, tob)
            
            现在请处理用户提供的 prod 和 tob 文件内容，输出仅包含上述格式的排除条款清单。
        """

        prompt_user = f"""
            "prod": {prod},
            "tob": {tob}
        """

        messages = [{"role": "user", "content": prompt_user},
                    {"role": "system", "content": prompt_system}
                    ]
        completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages, extra_body={"enable_thinking":True}, stream=True)
        
        # 收集流式响应内容
        content = ""
        for chunk in completion:
            if chunk.choices[0].delta.content:
                content += chunk.choices[0].delta.content

        return content
    except Exception as e:
        logging.exception("生成住院指征预分析结果出错")
        return None



def pre_analyze_preauth_result2(hospital_info: str,amount: str,document_result: str,policy_except_info: str) -> Optional[dict]:
    try:
        # 获取prompt
        prompt_system = """
                    **判断逻辑：**  
          **1.医院特殊规则**
            如果同时满足：
              1. hospital_info.correct_hospital_name 包含以下任一字符串：
                - "广东省人民医院协和高级医疗中心"
                - "中山大学附属第六医院雅和医疗"
                - "祈福医院"
              2. amount(申请金额) > 10000
            则触发规则1，拒绝
            
          **2.受伤导致住院门诊规则**
            首先，从 claim_materials 文本中判断是否涉及受伤相关的门诊或住院。
            如果文本中明显提及受伤、创伤、事故、伤害等相关情况，则进一步判断：
            
            条件A：如果文本中缺乏明确受伤原因描述（如未说明如何受伤、原因不明等），则触发拒绝
            条件B：如果文本中缺乏明确责任归属描述（如未说明责任方、责任不明等），则触发拒绝
            条件C：如果文本中明确提及受伤由他人造成（如"被他人"、"他人导致"、"对方责任"、"被推倒"等），则触发拒绝
            条件D：如果文本中明确提及与饮酒相关（如"酒后"、"饮酒"、"醉酒"、"喝酒"等），则触发拒绝
            条件E：如果文本中明确提及由摔倒导致的受伤（如"摔倒"、"摔伤"、"跌倒"、"滑倒"等），则视为责任不明确，触发拒绝
            
            注意：只有确实涉及受伤情况时才应用此规则。如果文本中未提及受伤相关情况，则不触发此规则。
            
          **3.英克司兰钠药品检查规则**
            从 claim_materials 文本中判断是否申请了英克司兰钠（包括"英克司兰钠"、"英克司兰"、"Inclisiran"等名称）。
            如果申请了英克司兰钠，则检查文本中是否有符合适应症的病情描述：
            
            英克司兰钠适应症参考：
            - 用于他汀类药物控制不佳或无法耐受的他汀类治疗患者。
            - 适用于动脉粥样硬化性心血管疾病（ASCVD）高风险人群的辅助治疗。
            
            如果文本中申请了英克司兰钠，但未提及以下任一情况，则触发拒绝：
            - 他汀类药物控制不佳
            - 无法耐受他汀类治疗
            - 动脉粥样硬化性心血管疾病（ASCVD）
            - ASCVD高风险
            - 高胆固醇血症、高血脂等心血管疾病风险
            
            注意：只有明确申请了英克司兰钠药品时才应用此规则。如果未提及英克司兰钠，则不触发此规则。
            
          **4. Mounjaro（替尔泊肽）药品检查规则**
            从 claim_materials 文本中判断是否申请了 Mounjaro（替尔泊肽）（包括“Mounjaro”、“替尔泊肽”、“tirzepatide”等名称）。
            如果申请了 Mounjaro，则检查文本中是否有明确说明用于2型糖尿病。
            如果文本中申请了 Mounjaro，但未提及用于2型糖尿病，则触发拒绝。
            
            注意：只有明确申请了 Mounjaro 药品时才应用此规则。如果未提及 Mounjaro，则不触发此规则。
            
          **5.理赔除外信息匹配规则**
            从 policy_except_info 中获取所有理赔除外、免责信息。
            检查 claim_materials 中描述的就诊事由是否与 policy_except_info 中列明的除外责任相匹配。
            
          **6.先天性疾病规则**
            从 claim_materials 中判断是否有可能为先天性疾病，如果涉及先天性疾病，则触发拒绝。
            以下疾病都可能涉及先天性疾病：
             1.骶尾部皮肤问题
             2.结肠癌与子宫内膜癌
         
         **7.结石类疾病规则**
            从 claim_materials 中判断是否为结石类疾病，结石类疾病都涉及既往症，如果是结石类疾病 则触发拒绝。
            
        → 如果满足规则1、规则2中任一条件、规则3、规则4或规则5，则裁定为 **拒绝 (13)**  
        → 否则，裁定为 **批准 (12)**
        
        **输出要求：**
        - 必须输出纯净 JSON，无任何额外文字。
        - 使用如下结构：
        
        {
          "result": "13 - 拒绝 (GOP Rejected)",
          "reason": "XXXXXX"
        }
        
        或
        
        {
          "result": "12 - 批准 (GOP Approved)",
          "reason": "XXXXXXXX"
        }
        
        result 是 13 - 拒绝 (GOP Rejected) 的话，reason要把理由写详细
        
        **注意事项：**
        1. 对 claim_materials 的分析应基于文本中的明确描述，不进行推测
        2. 如果没有提及受伤相关情况，默认不触发受伤规则
        3. 如果没有提及英克司兰钠，默认不触发药品检查规则
        4. 规则5的判断应基于 policy_except_info 中明确的除外责任描述
        5. 对于物理治疗/理疗，不区分中医和西医，统一判断
        6. 医院是否为昂贵医院以is_expensive_hospital 为准，不要自行推理
        7. 骨龄延迟为发育迟缓
        """

        prompt_user = f"""
            "hospital_info": {hospital_info},
            "amount": {amount},
            "claim_materials": {document_result},
            "policy_except_info":{policy_except_info}
        """

        messages = [{"role": "user", "content": prompt_user},
                    {"role": "system", "content": prompt_system}
                    ]
        completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages, extra_body={"enable_thinking":True}, stream=True)
        
        # 收集流式响应内容
        content = ""
        for chunk in completion:
            if chunk.choices[0].delta.content:
                content += chunk.choices[0].delta.content

        return json.loads(clean_json_string(content))
    except Exception as e:
        logging.exception("生成住院指征预分析结果出错")
        return None


def clean_json_string(content: str) -> str:
    """清理JSON字符串中的非法控制字符"""
    if not content:
        return content
    # 移除无效的控制字符（换行、制表符等在字符串外的控制字符）
    # 保留 \n, \r, \t 因为它们在JSON字符串中是合法的
    content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', content)
    return content


def analyze_preauth_result(claims_info: str, claim_analysis: str, policy_analysis_tob: str, policy_analysis_prod: str,
                           gop_type: str,price_knowledge_base: str,service_type: str, prod_type: str,hospital_info: str,except_info: str,
                           apv_info:str,inpatient_info:str,app_info:str,reco_benifit_info:str) -> Optional[dict]:

    """综合判断预授权结果"""
    try:
        logging.info(f"gop_type： {gop_type} ")
        if gop_type == "" or gop_type is None or gop_type == "hospital":
            # 获取prompt
            prompt_system = prompt_dao.get_prompt_by_type("GOP_AUTH_RESULT_HOSP")

            if reco_benifit_info == "Y":
                processed_reco_benifit_info = "客户有门诊康复福利"
            else:
                processed_reco_benifit_info = "客户没有门诊康复福利"

            prompt_user = f"""
            "application information": {app_info}
            "inpatient_info": {inpatient_info},
            "service_type": {service_type},
            "policy_analysis": {policy_analysis_prod},
            "policy_analysis_tob": {policy_analysis_tob},
            "claim_analysis": {claim_analysis},
            "claims_info": {claims_info},
            "price_knowledge_base": {price_knowledge_base},
            "hospital_info": {hospital_info},
            "except_info":{except_info}
            "apv_info":{apv_info}  
            "reco_benifit_info":{processed_reco_benifit_info} 
            """

            prompt_user = str(prompt_user)

            messages = [{"role": "user", "content": prompt_user},
                        {"role": "system", "content": prompt_system}
                        ]
            completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages, extra_body={"enable_thinking":True}, stream=True)
            
            # 收集流式响应内容
            content = ""
            for chunk in completion:
                if chunk.choices[0].delta.content:
                    content += chunk.choices[0].delta.content

        else:
            prompt_info = prompt_dao.get_prompt_by_type("GOP_AUTH_RESULT_MEDI")

            prompt = f"""
                # 角色定义
                您是医疗保险用药审批专家，负责药品费用报销申请审核，确保用药合理性并控制费用支出。
                # 审核依据
                基于以下信息进行审核：
                    1. **保障权益表TOB**: """ + policy_analysis_tob + """
                    2. **保障权益表PROD**: """ + policy_analysis_prod + """
                    3. **申请材料**: """ + claim_analysis + """  
                    4. **保险期限与福利余额**: """ + claims_info + """
                    5. **用药合理性**: 临床用药指南、药物说明书、适应症匹配

            """
            if prompt_info:
                prompt = prompt + prompt_info

            messages = [{"role": "user", "content": prompt}]
            completion = create_chat_completion(model=MODEL_TEXT_ANALYSIS, messages=messages)
            content = completion.choices[0].message.content
        return json.loads(clean_json_string(content))
    except Exception as e:
        logging.exception("生成预授权结果出错")
        return None