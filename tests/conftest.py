"""
测试配置和夹具模块

提供单元测试和集成测试所需的通用配置、数据库连接 fixtures、mock 对象等。
支持 pytest、behave (BDD) 和 unittest (TDD) 框架。
"""

import os
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ===== 环境变量加载 =====
from dotenv import load_dotenv

# 优先加载测试专用环境变量
test_env_path = PROJECT_ROOT / ".env.test"
if test_env_path.exists():
    load_dotenv(test_env_path, override=True)
else:
    load_dotenv(PROJECT_ROOT / ".env", override=False)

os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("DB_NAME", "gop_test")
# 设置 LLM API 的默认值，避免模块导入时 OpenAI 客户端初始化失败
# 使用直接赋值而非 setdefault，因为 .env 文件中可能存在空值（api_key=），
# setdefault 无法覆盖已存在（但为空）的键
for key, default_val in [
    ("api_key", "test-api-key"),
    ("base_url", "https://test.api.example.com"),
    ("DASHSCOPE_API_KEY", "test-dashscope-key"),
]:
    if not os.environ.get(key):
        os.environ[key] = default_val


# ===== Flask 测试应用 =====
import pytest

# 延迟导入 Flask，避免在没有安装时导致整个测试套件无法加载
try:
    from flask import Flask
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


@pytest.fixture(scope="session")
def test_app():
    """创建测试用的 Flask 应用实例"""
    if not FLASK_AVAILABLE:
        pytest.skip("Flask 未安装")
    from app.main import create_app
    app = create_app()
    app.config.update({
        "TESTING": True,
        "DEBUG": False,
    })
    return app


@pytest.fixture(scope="function")
def test_client(test_app):
    """创建测试客户端"""
    return test_app.test_client()


# ===== Mock 数据库连接池 =====
from unittest.mock import MagicMock, patch

# 尝试导入 PooledDB，如果不可用则跳过
try:
    from dbutils.pooled_db import PooledDB
    DBUTILS_AVAILABLE = True
except ImportError:
    DBUTILS_AVAILABLE = False


@pytest.fixture(scope="function")
def mock_db_connection():
    """模拟数据库连接"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    
    # 模拟 fetchone/fetchall 返回值
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    mock_cursor.lastrowid = 1
    
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn
    
    return mock_conn


@pytest.fixture(scope="function")
def mock_connection_pool(mock_db_connection):
    """模拟数据库连接池"""
    with patch("app.utils.db_utils.connection_pool") as mock_pool:
        mock_pool.connection.return_value = mock_db_connection
        yield mock_pool


# ===== Mock LLM / API 调用 =====
@pytest.fixture(scope="function")
def mock_openai_client():
    """模拟 OpenAI 客户端"""
    with patch("app.llm.analysis_service.client") as mock_client:
        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = '{"result": "12 - 批准 (GOP Approved)", "reason": "测试通过"}'
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_completion
        yield mock_client


@pytest.fixture(scope="function")
def mock_requests():
    """模拟 requests 库"""
    with patch("app.utils.api_utils.requests") as mock_req:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"content": [], "text": ""}
        mock_response.text = "{}"
        mock_req.post.return_value = mock_response
        mock_req.get.return_value = mock_response
        yield mock_req


# ===== 测试数据工厂 =====
class TestDataFactory:
    """测试数据工厂 - 提供各种场景的测试数据"""
    
    @staticmethod
    def make_claim_request():
        """创建标准的理赔请求"""
        return {
            "claimsId": "TEST-CLAIM-001",
            "providerCode": "TEST-PROV-001",
            "am": "Y",
            "claimType": "hospital",
            "claimInfo": {
                "insuredName": "张三",
                "gender": "男",
                "dob": "1990-01-01",
                "certNo": "110101199001011234",
                "providerName": "北京协和医院",
                "serviceType": "门诊",
                "diagnosis": "急性胃炎",
                "treatment": "胃镜检查",
                "estimatedAmount": 5000,
                "plannedAdmissionDate": "2025-07-15",
                "serviceDate": "2025-07-15"
            }
        }
    
    @staticmethod
    def make_hospital_info():
        """创建标准医院信息"""
        return {
            "correct_hospital_name": "北京协和医院",
            "hospital_type": "公立白名单医院",
            "direct_billing_network_status": "IN_NETWORK",
            "expensive_hospital_list": "非昂贵医院"
        }
    
    @staticmethod
    def make_policy_analysis():
        """创建模拟保单分析结果"""
        return {
            "prod": "保障计划已于2025-01-01生效，覆盖门诊/住院医疗费用，不包含生育和牙科",
            "tob": "门诊赔付比例90%，年度限额50万元，包含胃镜检查费用"
        }
    
    @staticmethod
    def make_claim_analysis():
        """创建模拟理赔材料分析结果"""
        return "患者张三，30岁男性，因上腹部不适就诊，门诊胃镜检查，未见明显异常。费用预估5000元。"
    
    @staticmethod
    def make_document_analysis():
        """创建模拟文档分析结果"""
        return [
            {
                "claim_id": "TEST-CLAIM-001",
                "image_quality": "95%",
                "consistency": "完全一致 (100%)",
                "analysis_result": "发票显示胃镜检查费用4500元，麻醉费500元"
            }
        ]


@pytest.fixture(scope="function")
def test_data_factory():
    """测试数据工厂 fixture"""
    return TestDataFactory()


# ===== 日志配置 =====
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [TEST] %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# 抑制第三方库的调试日志
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)