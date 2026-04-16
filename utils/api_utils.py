import os
from typing import Optional

import requests
import json

from logger import logger

logging = logger.setup_logger()
# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

def get_claim_info_api(claim_id: str) -> Optional[dict]:
    url = os.getenv("getClaimInfoApiUrl")
    return _post_json(url, {"claimsId": claim_id})

def get_expensive_hosp_info_api(claim_id: str) -> str:
    url = os.getenv("eccsWebUrlBase") + "ai/getExpensiveHospInfo"
    result = _post_json(url, {"claimsId": claim_id})
    # 由于_post_json已经保证返回字典类型，直接提取text字段
    return result.get('text', '') if isinstance(result, dict) else ''

def get_direct_pay_hosp_api(provider_code: str) -> str:
    url = os.getenv("eccsCoreUrlBase") + "ai/getDirectPayHosp"
    result = _post_json(url, {"providerCode": provider_code})
    # 由于_post_json已经保证返回字典类型，直接提取text字段
    return result.get('text', '') if isinstance(result, dict) else ''

def get_policy_wording_url_api(claim_id: str) -> Optional[str]:
    url = os.getenv("getPolicyWordingUrl")
    res = _post_json(url, {"claimId": claim_id})
    return res.get("content") if res.get("content") else []

def get_claim_documents_api(claim_id: str) -> Optional[list]:
    url = os.getenv("getDocumentsUrl")
    res = _post_json(url, {"claimId": claim_id})
    return res.get("content") if res.get("content") else []

def _post_json(url: str, data: dict) -> Optional[dict]:
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        # 尝试解析JSON
        try:
            return response.json()
        except json.JSONDecodeError:
            # 如果无法解析为JSON，返回包含文本内容的字典
            return {"text": response.text}
    except Exception as e:
        logging.error(f"API 请求失败：{url}, 错误：{e}")
        return None

