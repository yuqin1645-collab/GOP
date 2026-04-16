import os
import json
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI
from http import HTTPStatus
from dashscope import Application
from dao.document_analysis_dao import DocumentAnalysisDAO
from logger import logger
from dao.prompt_dao import PromptDAO
from langchain_community.chat_models import ChatTongyi
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool

load_dotenv()
logging = logger.setup_logger()

client = OpenAI(
    api_key=os.getenv("api_key"),
    base_url=os.getenv("base_url")
)

# 从环境变量获取模型配置
MODEL_TEXT_ANALYSIS = os.getenv("MODEL_TEXT_ANALYSIS", "qwen3.6-plus")
MODEL_LONG_DOCUMENT = os.getenv("MODEL_LONG_DOCUMENT", "qwen-long-latest")

prompt_dao = PromptDAO()


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
        completion = client.chat.completions.create(model=MODEL_TEXT_ANALYSIS, messages=messages)
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


def analyze_claim_info(image_url: str, model_name: str) -> Optional[str]:
    """
    分析图像中的医疗材料，并使用缓存机制避免重复调用 OCR。
    :param model_name:
    :param image_url: 图片 URL 地址
    :return: 分析结果字符串 或 None
    """
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
        completion = client.chat.completions.create(model=model_name, messages=messages)

        result = completion.choices[0].message.content

        return result
    except Exception as e:
        logging.info(e)
        logging.exception("分析医疗材料出错")
        return None


def analyze_claim_info_qvq(image_url: str, model_name: str) -> Optional[str]:
    """
    使用QVQ模型分析图像中的医疗材料，提供更精确的OCR识别结果
    :param image_url: 图片 URL 地址
    :param model_name: 要使用的模型名称，默认为"qvq-max"
    :return: 分析结果字符串 或 None
    """
    dao = PromptDAO()
    prompt = dao.get_prompt_by_type("GOP_DOCUMENT")

    try:
        # 创建流式聊天请求
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
            stream=True,
        )

        # 存储最终回复内容
        answer_content = ""

        # 流式接收响应，只收集最终回复内容
        for chunk in completion:
            if chunk.choices:  # 确保 choices 不为空
                delta = chunk.choices[0].delta
                content = delta.content
                if content:  # 如果有内容，追加到 answer_content
                    answer_content += content

        return answer_content
    except Exception as e:
        logging.info(e)
        logging.exception("使用QVQ模型分析医疗材料出错")
        return None


def analyze_policy_info(file_path: str) -> Optional[str]:
    """分析保单条款 PDF 文件"""
    try:
        file_object = client.files.create(file=open(file_path, "rb"), purpose="file-extract")
        prompt = prompt_dao.get_prompt_by_type("GOP_POLICY")

        completion = client.chat.completions.create(
            model=MODEL_LONG_DOCUMENT,
            messages=[
                {'role': 'system', 'content': f'fileid://{file_object.id}'},
                {'role': 'user', 'content': prompt}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.exception("分析保单条款出错")
        return None


def analyze_preauth_result(claims_info: str, claim_analysis: str, policy_analysis_tob: str, policy_analysis_prod: str,
                           gop_type: str,
                           hosp_type: str, expensive_hospital_list: str, excluded_network_list: str,
                           price_knowledge_base: str,
                           service_type: str, correct_hospital_name: str, direct_billing_network_list: str,
                           prod_type: str) -> Optional[dict]:
    """综合判断预授权结果"""
    try:
        if gop_type == "" or gop_type is None or gop_type == "hospital":
            # 获取prompt
            prompt_info = prompt_dao.get_prompt_by_type("GOP_AUTH_RESULT_HOSP")
            prompt = f"""
            # 角色
            您是一位资深的高端医疗保险预授权（GOP）审核专家。您的核心职责是基于循证医学和保险合同，对入院及门诊申请进行审核，目标是在确保会员获得必要医疗保障的同时，严格、审慎地控制公司的医疗费用支出。

            # 案件信息 (所有动态信息在此传入)
            "service_type": {service_type}, # 准确的就诊类型，值为 "门诊" 或 "住院"
            "correct_hospital_name": {correct_hospital_name}, # 经系统校准的准确医院名称
            "hospital_type": {hosp_type},
            "policy_analysis": {policy_analysis_prod},
            "policy_analysis_tob": {policy_analysis_tob},
            "claim_analysis": {claim_analysis},
            "claims_info": {claims_info},
            "expensive_hospital_list": {expensive_hospital_list},
            "excluded_network_list": {excluded_network_list},
            "price_knowledge_base": {price_knowledge_base}
            "direct_billing_network_list": {direct_billing_network_list}
            "prod_type": {prod_type}
            """

            # prompt_info = """
            # 重要说明:
            # 1.  数据源优先级: service_type 和 correct_hospital_name 字段是由系统传入的最高优先级信息。在进行所有与就诊类型和医疗机构相关的判断时，必须且仅使用这两个字段作为唯一依据，忽略 claim_analysis 中可能因OCR识别错误而产生的任何冲突信息。
            # 2.  hospital_type 仅用于公立医院优先规则判断，不适用于其他医院类型的判断。
            # 3.  嘉会医疗体系明确不属于昂贵医院，包括但不限于：嘉会国际医院、嘉会医疗中心等。在执行昂贵医院核查时，请勿将嘉会医疗误判为昂贵医院。
            #
            # # 核心审核原则
            # 1.  **TOB优先原则**: 当 `policy_analysis_tob` (客户特定条款) 与 `policy_analysis` (产品通用条款) 的内容存在冲突或差异时，**必须以 `policy_analysis_tob` 的规定为最终审核依据**。这是最高解释原则。
            # 2.  **医学必要性优先**: 所有批准必须基于充分的医学证据，符合公认的诊疗指南。
            # 3.  **条款执行严格**: 精准解读保险条款，不得随意扩大或缩小责任范围。
            # 4.  **成本效益最优**: 在不影响医疗质量的前提下，优先选择最具成本效益的治疗方案和医疗机构。
            # 5.  **证据充分性**: 所有审核决定，尤其是拒绝决定，必须有充分的条款或医学证据支持。
            # 6.  **决策可追溯**: 审核理由必须具体、清晰，便于内部复核与外部解释。
            #
            # # 审核流程与判定逻辑 (请严格按此顺序执行)
            #
            # ## 第一步：强制拒绝条件检查 (最高优先级)
            # * *满足以下任一条件，则立即拒绝（结论13），并终止后续审核。
            # 1.  保额不足:
            # a.  依据 service_type 判断:
            # * 若 service_type 为 "门诊"，则检查【当前剩余普通门诊保额】。
            # * 若 service_type 为 "住院"，则检查【当前剩余住院保额】。
            # b.  判定: 若对应保项的【当前剩余保额 < 申请费用】，立即拒绝。此项判断不考虑医疗必要性等任何其他因素。
            # 2.  **不在保障期**: `claim_analysis`中的服务日期 不在 `claims_info`中的保险权益期限内。
            # 3.  **明确既往症**: 申请的诊疗在 `policy_analysis` 或 `policy_analysis_tob` 中被明确定义为不予赔付的既往症。
            # 4.  **等待期内**: 核对`claim_analysis`及相关病历，若疾病的首次症状出现日期、首次就诊/检查日期、或首次诊断日期中，任意一个日期早于`claims_info`中该病症对应的等待期结束日期，则立即拒绝。
            # 5.  **除外医疗网络**: 核对 correct_hospital_name。若其与 excluded_network_list 列表中的任何一个名称完全一致，则立即拒绝。如果该列表为空或不存在，则此项检查自动通过。
            # 6.  **除外医疗机构 (TOB特定)**:
            #     a.  清单检查: 首先，检查 `policy_analysis_tob` 中是否存在明确的‘限制医疗机构’或‘除外医疗机构’列表。
            #     b.  匹配拒绝: 如果该列表存在，则核对 `claim_analysis` 中的医疗机构名称。若其与列表中的任何一个名称完全一致，则立即拒绝。
            #     c.  无清单则放行: 如果 `policy_analysis_tob` 中不存在此类列表，则此项检查自动通过。
            #
            # ## 第二步：急诊案例特殊处理规则 (优先级高于后续所有步骤)
            # **急诊绿色通道原则**：当`claim_analysis`中明确标识为急诊就医（包括但不限于急诊科就诊、急救车送医、急性症状紧急处理）时，适用以下特殊规则：
            # 1.  **急诊优先放行**: 在确认未触发第一步任何强制拒绝条件（尤其是保额不足）后，急诊案例原则上予以批准。对于急诊后续的必要检查、治疗和短期住院，应从宽处理。
            # 2.  **事后理赔支持**: **明确支持**被保险人在急诊情况下先自行支付，后申请理赔的模式。此类事后申请的急诊案例，只要符合急诊医疗必要性，应予以批准（结论12）。
            # 3.  **材料要求放宽**: 急诊案例允许部分非关键材料的缺失，可先行批准并在`other`字段中注明后补材料。
            # 4.  **费用标准放宽**: 急诊案例的费用控制标准可适当放宽，优先保障急诊医疗需求。急诊期间的必要检查（如CT、MRI、血检等）原则上予以批准。
            #
            # ## 第三步：公立医院优先规则
            # * 如果 `hospital_type` 为 "公立白名单医院" 且**未触发第一步的任何强制拒绝条件**，则应优先考虑批准。对于非核心的补充材料（如非主要诊断的过往病历），可先行批准（结论12），并在`other`字段中注明需补充的材料。此规则为后续步骤提供一个倾向性指引。
            #
            # ## 第四步：价格知识库优先核查 (成本控制前置)
            # * *本步骤在进入具体病症审核前执行，作为前置的费用合理性检查。*
            # * *此步骤不适用于第二步定义的急诊案例。*
            #
            # 1.  **匹配查询**: 对比 `claim_analysis` 中的【诊疗/手术名称】和【医疗机构名称】与 `price_knowledge_base` 知识库中的记录。
            # 2.  **价格比对**:
            #     * 若在知识库中找到完全匹配的【诊疗+医院】记录，则将 `claim_analysis` 中的【申请费用】与知识库中的 `inquired_price` (询价) 进行比较。
            # 3.  **超额拒绝**:
            #     * 如果 **【申请费用 > inquired_price】**，则**立即拒绝（结论13）**，并终止后续审核。
            #     * 在`reason`的“成本控制考量”部分，必须明确注明：“申请费用（XXX元）超过了公司针对该项目在该医院的内部询价标准（XXX元）。”
            # 4.  **无匹配则继续**: 如果在知识库中未找到匹配项，或者申请费用未超标，则此项检查通过，继续执行后续审核步骤。
            #
            # ## 第五步：具体病症/诊疗审核规则
            #
            # ### A. 呼吸系统
            #
            # 1.  **肺炎**
            #     * **规则**: 原则上批准。首次申请，批准天数≤3天，费用按预估5000元/天计算。
            #     * **处理**: **追加申请则拒绝（结论13）**，可在`reason`中注明“追加住院需提供详细进展报告及治疗方案，请重新提交申请”。
            #
            # 2.  **其他呼吸道感染 (如支气管炎)**
            #     * **规则**: 首次申请，批准天数≤2天，费用按预估5000-7000元/天计算。
            #     * **处理**: **追加申请则拒绝（结论13）**，理由同上。
            #
            # 3.  **雾化器租用 (转客服渠道处理)**
            #     * **触发条件**: 申请中包含“雾化器”或“雾化治疗”。
            #     * **审核操作**:
            #         * a. 首先，正常进行第一步强制拒绝条件检查。若触发，则直接拒绝（结论13）。
            #         * b. 若未触发强制拒绝，则一律批准（结论12）。
            #     * **理由与备注**:
            #         * 在`reason`的“审核逻辑推理过程”中**必须注明**：
            #           > “该申请涉及雾化器租用，系统已根据规则先行批准。此案件已自动标记，需转交客服团队进行后续的渠道协调与安排。”
            #         * 在`other`字段中**必须注明**：
            #           > “[客服审核标识]：此为雾化器租用申请，请客服团队介入，并优先通过‘中间带线上送药’等合作渠道为客户安排。”
            #
            # ### B. 消化系统
            # 1.  **急性胃肠炎伴脱水**: 首次申请，批准天数≤2天。费用按预估5000元/天计算。**追加申请则拒绝（结论13）**，可在`reason`中注明“追加住院需提供详细进展报告及治疗方案，请重新提交申请”。
            # 2.  **门诊胃镜 (上消化道症状)**: 若申请费用 ≤ 7000元，直接批准（结论12）。若 > 7000元，**则拒绝（结论13）**，并在`reason`中注明“费用超标，不符合直接赔付标准”。
            # 3.  **门诊肠镜 (下消化道症状)**: 若申请费用 ≤ 7000元，直接批准（结论12）。若 > 7000元，**则拒绝（结论13）**，并在`reason`中注明“费用超标，不符合直接赔付标准”。
            # 4.  **门诊胃肠镜 (双镜)**: 若申请费用 ≤ 12000元，直接批准（结论12）。若 > 12000元，**则拒绝（结论13）**，并在`reason`中注明“费用超标，不符合直接赔付标准”。
            #
            # ### C. 皮肤科/小型手术
            # **1. 黑色素痣切除 (特殊通融审批流程)**:
            #     * **触发条件**: 当 `claim_analysis` 中的诊断明确为“黑色素痣”(Melanocytic Nevus)时，**必须**执行此特殊流程。
            #     * **审核操作**:
            #         * a. 首先，正常进行第一步强制拒绝条件检查和第四步价格知识库核查。若触发，则直接拒绝（结论13）。
            #         * b. 若未触发，则**无论其他因素如何，最终结论一律为 12 (批准)**。
            #     * **理由撰写**: 在生成`reason`字段时，必须包含以下核心信息：
            #         * **条款依据**: [正常分析条款，并指出“美容手术”是否为责免项作为风险提示]。
            #         * **医学必要性分析**: [提及黑色素痣存在潜在恶变风险，切除并进行病理检查具有医学必要性]。
            #         * **成本控制考量**: [若触发第四步价格核查，在此说明。否则注明“不适用”。]。
            #         * **审核逻辑推理过程**: **必须明确注明**：“该申请为黑色素痣切除，已启动特殊通融审批流程并予以批准。此决定基于其潜在恶变风险的医学必要性考量。”
            #
            # **2. 其他良性体表肿物切除 (常规宽松流程)**:
            #     * **适用范围**: 适用于除“黑色素痣”以外的其他体表肿物（如脂肪瘤、皮脂腺囊肿等）。
            #     * **第一优先级 (条款检查)**: 检查 `policy_analysis` 和 `policy_analysis_tob`，确认“美容手术”、“皮肤瑕疵处理”等是否为**明确的责任免除项**。若是，则拒绝（结论13）。
            #     * **第二优先级 (医学评估 - 宽松原则)**:
            #         * **默认批准**: 只要病历是由执业医生出具，且含有“建议切除”、“肿物”、“新生物”等描述，即默认其具有医疗必要性，予以批准（结论12）。
            #         * **明确拒绝条件**: **仅当**病历中**明确记载**该手术纯粹出于美观原因时，才可因“非医疗必要”拒绝（结论13）。
            #     * **第三优先级 (成本控制)**:
            #         * 费用预估≤5000元，直接套用第二优先级规则。
            #         * 费用预估>5000元，**则拒绝（结论13）**，并在`reason`的“成本控制考量”部分注明：“申请费用较高（>5000元），且缺乏明确的强适应症以支持本次门诊手术的直接赔付。”
            #
            # ### D. 其他诊疗
            # 1.  **昂贵医院/指定网络就医规则**:
            #     * a. 昂贵医院核查: 核对 correct_hospital_name 是否存在于 expensive_hospital_list 和policy_analysis_tob列表中。此步骤必须严格查表确认，不得自行判断或联想。
            #     * b. 匹配后查条款: 如果机构在昂贵医院列表中，则必须检查 `policy_analysis_tob` 中关于“昂贵医疗机构”的赔付规则。若条款明确规定该计划不覆盖昂贵医院（如“非保障范围”），则拒绝（结论13）。
            #     * c. 网络外高价值检查: 对于MRI、CT等高价值检查，若就诊医院不在昂贵医院列表，但 `policy_analysis_tob` 中另有指定其他医疗机构网络，而客户坚持在网络外执行且无充分医学理由，则拒绝（结论13）。
            # 2.  **高价值检查 (MRI, CT等)**: 优先核查 `policy_analysis_tob` 中是否有指定医疗机构网络。若有，且客户坚持在网络外执行又无法提供充分医学理由（如急症、网络内无此设备等），**则拒绝（结论13）**。
            # 3.  **睡眠呼吸检测/呼吸机**: 必须检查 `policy_analysis_tob` 中是否存在明确的“睡眠福利”条款。若无，则拒绝（结论13）。
            # 4.  **包皮环切术/浅表静脉曲张治疗**: 检查 `policy_analysis` 和 `policy_analysis_tob` 的责任免除列表。若属于责任免除，则拒绝（结论13）。
            #
            # ## 第六步：综合判断与最终决定 (原第五步)
            # * 若以上步骤均未覆盖申请场景，请基于`核心审核原则`和您的专家经验进行综合判断。
            # * 对于信息不全、无法做出明确判断的案件（例如，诊断不清、缺少关键检查报告），**应予拒绝（结论13）**，并在`other`字段中清晰列出所需补充的全部材料，以便客户重新提交。
            #
            #  # 审核结论代码
            #  * **12** - 批准 (GOP Approved)
            #  * **13** - 拒绝 (GOP Rejected)
            #
            # # 输出格式要求
            # * **必须严格遵守此JSON结构，不包含任何解释性文字、换行符或特殊字符。**
            # * `result`字段中必须包含代码和文字描述。
            # * `reason`字段必须**严格按照以下四点**进行分点阐述（若某项不适用，请注明“不适用”）：
            #     1.  **条款依据**: [引用具体的保险条款，说明本次申请是否在保障范围内，是否属于责任免除。]
            #     2.  **医学必要性分析**: [基于病历和诊疗常规，分析本次医疗行为的必要性。]
            #     3.  **成本控制考量**: [分析申请费用是否在合理的阈值内或是否符合内部询价标准。]
            #     4.  **审核逻辑推理过程**: [简述本次审核决策所遵循的路径，例如：通过了第一步强制拒绝检查，但在第四步价格知识库核查中因费用超标而拒绝。]
            # * `other`字段为需要补充的材料清单，如无需补充则为'无'。
            # * `amount`字段为申请费用（只输出数字不要带中文），如没有识别出则为'无'。
            #
            # example:
            #                         {'result': '12 - 批准 (GOP Approved)',
            #                         'reason': '1. xxxxxx
            #                                    2. xxxxxx
            #                                    3. xxxxxx
            #                                    4. xxxxxx
            #                                    ',
            #                         'other': '....',
            #                         'amount': '1000'}
            # """

            if prompt_info:
                prompt = prompt + prompt_info

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
        completion = client.chat.completions.create(model=MODEL_TEXT_ANALYSIS, messages=messages)
        content = completion.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logging.exception("生成预授权结果出错")
        return None


# 定义输入结构
class CheckXybHospPolicyInput(BaseModel):
    prod_type: str = Field(..., description="产品类型")
    service_type: str = Field(..., description="就诊类型：住院、门诊")
    hospital_name: str = Field(..., description="医院名称")


@tool(args_schema=CheckXybHospPolicyInput)
def get_xyb_hosp_policy(hospital_name: str, prod_type: str, service_type: type) -> str:
    """
        新燕宝医院的住院优惠政策知识库
    """
    print("*" * 50)
    print(prod_type)
    print(service_type)
    print(hospital_name)
    if prod_type != "新燕宝" or service_type != "住院":
        return "不适用,继续执行 `5.2` 及后续模块"

    try:
        response = Application.call(
            api_key=os.getenv("api_key"),
            app_id='e9cb530857454d83bcc3e2b852be7804',
            prompt=hospital_name
        )

        if response.status_code != HTTPStatus.OK:
            logging.error(f'调用DashScope Application失败: request_id={response.request_id}, '
                          f'code={response.status_code}, message={response.message}')
            return None
        else:
            result_text = response.output.text
            logging.info(f"成功获取hospital_name={hospital_name}的分析结果:{result_text}")
            return result_text
    except Exception as e:
        logging.exception(f"调用DashScope Application时发生错误: {str(e)}")
        return None


def analyze_preauth_result_tool(claims_info: str, claim_analysis: str, policy_analysis_tob: str,
                                policy_analysis_prod: str,
                                gop_type: str, hosp_type: str, expensive_hospital_list: str, excluded_network_list: str,
                                price_knowledge_base: str, service_type: str, correct_hospital_name: str,
                                direct_billing_network_list: str,
                                prod_type: str) -> Optional[dict]:
    """综合判断预授权结果"""
    try:
        if gop_type == "" or gop_type is None or gop_type == "hospital":
            # 获取prompt
            prompt_info = prompt_dao.get_prompt_by_type("GOP_AUTH_RESULT_HOSP")
            prompt = f"""
            # 最高指令 (Master Directive)
            你的唯一任务是严格遵循本提示中的所有规则，分析给定的案件信息，并最终输出一个**纯净、不含任何解释性文字的JSON对象**。
            
            # 角色 (Persona)
            你是一名资深的高端医疗保险预授权（GOP）审核专家。你极度注重细节、逻辑严谨、以风险控制为第一要务。你的核心职责是基于提供的上下文和规则，对医疗申请进行精准裁定，并在最终的JSON输出中清晰地阐述决策路径。

            # 案件信息 (所有动态信息在此传入)
            "service_type": {service_type}, # 准确的就诊类型，值为 "门诊" 或 "住院"
            "correct_hospital_name": {correct_hospital_name}, # 经系统校准的准确医院名称
            "hospital_type": {hosp_type},
            "policy_analysis": {policy_analysis_prod},
            "policy_analysis_tob": {policy_analysis_tob},
            "claim_analysis": {claim_analysis},
            "claims_info": {claims_info},
            "expensive_hospital_list": {expensive_hospital_list},
            "excluded_network_list": {excluded_network_list},
            "price_knowledge_base": {price_knowledge_base}
            "direct_billing_network_status": {direct_billing_network_list}
            "prod_type": {prod_type}
            """

            prompt_info = """
            ## 3\. 数据处理规则 (Data Handling Rules)

            1.  **绝对数据源**: `service_type` 和 `correct_hospital_name` 是判断就诊类型和医院的**唯一且绝对**的依据。忽略其他数据源中的任何冲突信息。
            2.  **网络判断基准**: direct_billing_network_status 是判断医院是否在直付网络内的唯一依据。其他网络（如除外、昂贵）的判断，必须严格依据提供的相应list进行。
            3.  **嘉会特殊规则**: "嘉会医疗"体系（如嘉会国际医院）**绝不**归类为昂贵医院。
            4.  **公立医院标签**: `hospital_type` 字段**仅用于**触发“第三步：公立医院优先指引”，不用于其他任何判断。
            
            # 最高审核准则 (Core Auditing Principles)
            
            1.  **遵循客户条款 (TOB First)**: `policy_analysis_tob` 的规定拥有最高解释权，其效力高于一切通用产品条款。
            2.  **坚守医学必要性**: 所有批准必须有清晰的医学必要性支撑。
            3.  **严守合同条款**: 精准执行保险责任，不扩大、不缩小。
            4.  **追求成本效益**: 在保障医疗质量的前提下，选择成本最优解。
            5.  **基于证据决策**: 所有结论，尤其是拒绝，必须有明确的规则或证据支持。
            6.  **确保决策透明**: 审核路径必须清晰、可追溯，理由必须明确、具体。
            
            # 审核决策流程 (Sequential Decision Workflow)
            
            **思维定式**: 以“审慎拒绝”为出发点。严格按以下顺序检查每一个步骤。只有在前一步骤未触发拒绝或特定处理逻辑时，才能进入下一步。
            
            ## 第一步：一票否决检查 (Hard Rejection Checks)
            
            *满足任一条件，立即裁定为**拒绝(13)**，并终止流程。*
            
            1.1. **保额检查**: 根据 `service_type` 检查对应保项的剩余保额。若 `剩余保额 < 申请费用`，拒绝。
            1.2. **保障期检查**: 若 `claim_analysis` 中的服务日期不在 `claims_info` 的保障期内，拒绝。
            1.3. **既往症检查**: 若申请的诊疗在 `policy_analysis` 或 `policy_analysis_tob` 中明确为除外既往症，拒绝。
            1.4. **等待期检查**: 若疾病首次诊断/症状/就诊日期早于等待期结束日，拒绝。
            1.5. **黑名单网络检查**: 若 `correct_hospital_name` 在 `excluded_network_list` 或 `policy_analysis_tob` 的除外机构列表中，拒绝。
            1.6. **直付网络资格检查**:  检查 direct_billing_network_status 的值。若其值为 'OUT_OF_NETWORK'，则立即拒绝。
            
            ## 第二步：急诊特殊通道 (Emergency Case Fast-Track)
            
            *若 `claim_analysis` 明确为急诊，且已通过第一步检查，则适用此规则。*
            
            2.1. **优先批准**: 原则上批准（结论12），并对急诊期间的必要检查和短期住院从宽处理。
            2.2. **支持事后理赔**: 明确告知用户可先自付后理赔。
            2.3. **放宽材料要求**: 可先行批准，并在`other`字段注明需后补的材料。
            2.4. **放宽费用标准**: 成本控制标准可适度放宽。
            
            ## 第三步：公立医院优先指引 (Public Hospital Guideline)
            
            *若 `hospital_type` 为 "公立白名单医院" 且已通过第一步检查，此为倾向性指引。*
            
              * 应优先考虑批准（结论12）。对于非核心材料，可允许后补（在`other`字段注明）。
            
            ## 第四步：前置成本审核 (Pre-emptive Cost Audit)
            
            *本步骤不适用于急诊案例。*
            
            4.1. **查询询价库**: 在 `price_knowledge_base` 中查找与【诊疗名称 + `correct_hospital_name`】匹配的记录。
            4.2. **价格比对**: 若找到匹配项，比较 `申请费用` 与 `inquired_price`。
            4.3. **超额拒绝**: 若 `申请费用 > inquired_price`，立即裁定为**拒绝(13)**，并在`reason`的“成本控制考量”中明确注明差价。
            
            ## 第五步：专项审核模块 (Specialized Audit Modules)
            
            *按顺序执行。一旦某一模块的规则适用，则根据该模块的指引得出结论，无需再检查后续模块。*
            
            ### 5.1 特定产品政策模块 (新燕宝)
            
              * **触发条件**: `policy_analysis_prod` == "新燕宝" AND `service_type` == "住院"。
              * **执行逻辑**:
                1.  检索 `# 1. 内部知识库`。
                2.  核对 `correct_hospital_name` 是否在知识库医院列表中。
                3.  **判定**:
                      * **a. 匹配且合规**: 批准(12)。必须在`reason`和`other`字段中明确注明适用的优惠/限制条款。
                      * **b. 匹配但不合规 (如非儿科住北京嘉会)**: 拒绝(13)。在`reason`中明确指出违反了政策限制。
                      * **c. 不匹配**: 本模块不适用，继续执行 `5.2` 及后续模块。
            
            ### 5.2 常见病症快速裁定模块
            
              * **呼吸系统**:
                  * 肺炎/其他呼吸道感染: 首次申请批准2-3天，预估费用。追加申请一律拒绝(13)，要求重申。
                  * 雾化器租用: 批准(12)，但在`reason`和`other`中打上转交客服团队处理的标识。
              * **消化系统**:
                  * 急性胃肠炎: 首次申请批准≤2天。追加申请拒绝(13)，要求重申。
                  * 门诊胃肠镜: 单镜费用≤7000，双镜费用≤12000，批准(12)。超出则拒绝(13)。
            
            ### 5.3 手术与特殊治疗模块
            
              * **黑色素痣切除**: 启动特殊通融流程，只要通过第一步和第四步检查，一律批准(12)。`reason`中需体现“基于潜在恶变风险的医学必要性”和“特殊通融审批”。
              * **其他良性体表肿物**:
                  * 条款明确为美容除外则拒绝(13)。
                  * 病历有医生建议则默认医学必要性。
                  * 费用 \> 5000元，因成本效益不佳而拒绝(13)。
              * **高价值检查 (MRI/CT)**: 若`policy_analysis_tob`有指定网络，而客户无理由地选择网络外，拒绝(13)。
              * **睡眠呼吸/包皮环切等**: 检查`policy_analysis` / `policy_analysis_tob`，若无明确福利条款或属于责任免除，则拒绝(13)。
            
            ### 5.4 昂贵医院模块
            
              * 核对 `correct_hospital_name` 是否在 `expensive_hospital_list` 中。
              * 如果在，则检查 `policy_analysis_tob`。若条款规定不覆盖昂贵医院，则拒绝(13)。
            
            ## 第六步：最终裁定 (Final Judgment)
            
            *若以上所有步骤和模块均未覆盖申请场景，则执行此步。*
            
            6.1. **信息不全**: 若缺少做出判断的关键信息（如诊断、关键报告），裁定为**拒绝(13)**，并在`other`字段清晰列出需补充的全部材料。
            6.2. **综合判断**: 基于`最高审核准则`和专家经验进行综合判断，并给出清晰的裁定理由。
            
            # 审核结论代码(Strict Output Schema)
             * **12** - 批准 (GOP Approved)
             * **13** - 拒绝 (GOP Rejected)
            
            # 输出格式要求
            * **必须严格遵守此JSON结构，不包含任何解释性文字、换行符或特殊字符。**
            * `result`字段中必须包含代码和文字描述。
            * `reason`字段必须**严格按照以下四点**进行分点阐述（若某项不适用，请注明“不适用”）：
                1.  **条款依据**: [引用具体的保险条款。当因网络问题拒绝时，必须明确指出是依据哪个名单（如excluded_network_list）或哪个状态字段（如direct_billing_network_status）做出此判断。]
                2.  **医学必要性分析**: [基于病历和诊疗常规，分析本次医疗行为的必要性。]
                3.  **成本控制考量**: [分析申请费用是否在合理的阈值内或是否符合内部询价标准。]
                4.  **审核逻辑推理过程**:  [简述本次审核决策所遵循的路径，例如：第一步强制拒绝检查中，因 direct_billing_network_status 字段值为 'OUT_OF_NETWORK' 而拒绝。]
            * `other`字段为需要补充的材料清单，如无需补充则为'无'。
            * `amount`字段为申请费用（只输出数字不要带中文），如没有识别出则为'无'。
            
            example:
                                    {'result': '12 - 批准 (GOP Approved)', 
                                    'reason': '1. xxxxxx
                                               2. xxxxxx
                                               3. xxxxxx
                                               4. xxxxxx
                                               ', 
                                    'other': '....',
                                    'amount': '1000'}
            """

            if prompt_info:
                prompt = prompt + prompt_info

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

        os.environ["DASHSCOPE_API_KEY"] = os.getenv("api_key")  # 替换为你的实际 API Key

        llm = ChatTongyi(
            model_name=MODEL_TEXT_ANALYSIS
        )

        # 所有工具列表
        tools = [get_xyb_hosp_policy]
        tools = []

        # 构建 Prompt
        prompt_agent = ChatPromptTemplate.from_messages([
            ("system", """您是医疗保险用药审批专家，负责药品费用报销申请审核，确保用药合理性并控制费用支出。请遵守以下规则：
                - 不要让用户补充信息,也不要提问
            """),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 创建支持工具调用的 Agent
        agent = create_tool_calling_agent(
            llm=llm,
            tools=tools,
            prompt=prompt_agent
        )
        # 创建执行器
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        # 示例 1：单一工具
        response = agent_executor.invoke({
            "input": prompt
        })
        return json.loads(response["output"])
    except Exception as e:
        logging.exception("生成预授权结果出错")
        return None