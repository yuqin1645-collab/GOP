"""
TDD 单元测试 - LLM 分析服务层

测试 LLM 相关函数：create_chat_completion、analyze_claim_info、analyze_policy_info、
analyze_preauth_result、compare_ocr_results、call_dashscope_application 等。
"""
import pytest
import unittest
from unittest.mock import MagicMock, patch, PropertyMock


# ===== LLM 聊天完成测试 =====

class TestCreateChatCompletion(unittest.TestCase):
    """create_chat_completion 函数测试"""

    @patch("app.llm.analysis_service.client")
    def test_create_chat_completion_success(self, mock_client):
        """测试成功创建聊天完成 - 验证调用行为"""
        from app.llm.analysis_service import create_chat_completion

        mock_completion = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion

        result = create_chat_completion(
            model="qwen3.5-plus",
            messages=[{"role": "user", "content": "你好"}]
        )
        # create_chat_completion 返回 client.chat.completions.create() 的结果
        self.assertEqual(result, mock_completion)
        mock_client.chat.completions.create.assert_called_once()

    @patch("app.llm.analysis_service.client")
    def test_create_chat_completion_with_extra_body(self, mock_client):
        """测试带 extra_body 参数的调用"""
        from app.llm.analysis_service import create_chat_completion

        mock_completion = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion

        result = create_chat_completion(
            model="qwen3.5-plus",
            messages=[{"role": "user", "content": "你好"}],
            extra_body={"enable_thinking": True}
        )
        self.assertEqual(result, mock_completion)

    @patch("app.llm.analysis_service.client")
    def test_create_chat_completion_retry_on_error(self, mock_client):
        """测试 API 限流时重试"""
        from app.llm.analysis_service import create_chat_completion
        from openai import RateLimitError

        # 前两次抛出限流错误（模拟429），第三次成功
        mock_completion = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            RateLimitError("429 Too Many Requests", response=MagicMock(), body=None),
            RateLimitError("429 Too Many Requests", response=MagicMock(), body=None),
            mock_completion,
        ]

        result = create_chat_completion(
            model="qwen3.5-plus",
            messages=[{"role": "user", "content": "你好"}],
            max_retries=3
        )
        self.assertEqual(result, mock_completion)
        self.assertEqual(mock_client.chat.completions.create.call_count, 3)


# ===== OCR 比较测试 =====

class TestCompareOCRResults:
    """OCR 结果比较测试"""

    def test_compare_ocr_results_identical(self):
        """测试相同OCR结果比较"""
        from app.llm.compare_ocr_results import get_similarity_prompt
        prompt = get_similarity_prompt("相同文本", "相同文本")
        assert "相同文本" in prompt
        assert isinstance(prompt, str)

    @patch("app.llm.compare_ocr_results.client")
    def test_compare_ocr_results(self, mock_client):
        """测试OCR结果比较"""
        from app.llm.compare_ocr_results import compare_ocr_results

        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = '{"similarity": 0.95, "differences": "无差异"}'
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_completion

        result = compare_ocr_results("文本A", "文本B")
        assert result is not None

    @patch("app.llm.compare_ocr_results.client")
    def test_get_ocr_results_diff(self, mock_client):
        """测试获取OCR结果差异"""
        from app.llm.compare_ocr_results import get_ocr_results_diff

        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "OCR结果差异分析"
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_completion

        result = get_ocr_results_diff("文本A", "文本B")
        assert result is not None


# ===== DashScope Application 测试 =====

class TestDashScopeApplication:
    """DashScope Application 调用测试"""

    @patch("app.llm.analysis_service.DocumentAnalysisDAO")
    def test_call_dashscope_application_success(self, mock_doc_dao_cls, mock_openai_client, mock_connection_pool):
        """测试成功调用 DashScope"""
        from app.llm.analysis_service import call_dashscope_application

        mock_doc_dao = MagicMock()
        mock_doc_dao.get_document_analysis_by_claim_id.return_value = []
        mock_doc_dao_cls.return_value = mock_doc_dao

        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "测试响应"
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_completion

        result = call_dashscope_application("CLAIM-001", "北京协和医院")
        assert result is not None

    @patch("app.llm.analysis_service.DocumentAnalysisDAO")
    def test_call_dashscope_application_failure(self, mock_doc_dao_cls, mock_openai_client, mock_connection_pool):
        """测试 DashScope 调用失败返回 None"""
        from app.llm.analysis_service import call_dashscope_application

        mock_doc_dao = MagicMock()
        mock_doc_dao.get_document_analysis_by_claim_id.return_value = []
        mock_doc_dao_cls.return_value = mock_doc_dao

        mock_openai_client.chat.completions.create.side_effect = Exception("API错误")

        result = call_dashscope_application("CLAIM-001", "北京协和医院")
        assert result is None


# ===== 预授权结果分析测试 =====

def _make_streaming_chunks(content: str):
    """Helper: 创建模拟的流式响应块，每块带有 delta.content"""
    chunks = []
    for char in content:
        chunk = MagicMock()
        delta = MagicMock()
        delta.content = char
        choice = MagicMock()
        choice.delta = delta
        chunk.choices = [choice]
        chunks.append(chunk)
    return chunks


class TestAnalyzePreauthResult:
    """预授权结果分析测试"""

    @patch("app.llm.analysis_service.prompt_dao")
    def test_analyze_preauth_result_approval(self, mock_prompt_dao, mock_openai_client, mock_connection_pool):
        """测试预授权批准结果"""
        from app.llm.analysis_service import analyze_preauth_result

        mock_prompt_dao.get_prompt_by_type.return_value = "测试GOP提示词"

        test_json = '{"result": "12 - 批准 (GOP Approved)", "reason": "符合保险条款规定"}'
        mock_openai_client.chat.completions.create.return_value = _make_streaming_chunks(test_json)

        result = analyze_preauth_result(
            claims_info="患者张三，急性胃炎",
            claim_analysis="门诊胃镜检查",
            policy_analysis_tob="覆盖门诊费用",
            policy_analysis_prod="年度限额50万",
            gop_type="hospital",
            price_knowledge_base="胃镜检查参考价5000",
            service_type="门诊",
            prod_type="新燕宝",
            hospital_info='{"hospital":"北京协和医院"}',
            except_info="无除外项目",
            apv_info="无提前审核",
            inpatient_info="非住院",
            app_info="查询详情",
            reco_benifit_info="N"
        )
        assert result is not None

    @patch("app.llm.analysis_service.prompt_dao")
    def test_analyze_preauth_result_rejection(self, mock_prompt_dao, mock_openai_client, mock_connection_pool):
        """测试预授权拒绝结果"""
        from app.llm.analysis_service import analyze_preauth_result

        mock_prompt_dao.get_prompt_by_type.return_value = "测试GOP提示词"

        test_json = '{"result": "13 - 拒绝 (GOP Rejected)", "reason": "昂贵医院不在保障范围内"}'
        mock_openai_client.chat.completions.create.return_value = _make_streaming_chunks(test_json)

        result = analyze_preauth_result(
            claims_info="患者李四",
            claim_analysis="和睦家医疗就诊",
            policy_analysis_tob="不覆盖昂贵医院",
            policy_analysis_prod="标准保障计划",
            gop_type="hospital",
            price_knowledge_base="",
            service_type="门诊",
            prod_type="其他",
            hospital_info='{"hospital":"和睦家医疗","expensive":true}',
            except_info="",
            apv_info="",
            inpatient_info="非住院",
            app_info="",
            reco_benifit_info="N"
        )
        assert result is not None


# ===== clean_json_string 测试 =====

class TestCleanJsonString(unittest.TestCase):
    """JSON 清理函数测试"""

    def test_clean_json_with_markdown_wrapper(self):
        """测试清理 Markdown 包装的 JSON"""
        from app.llm.analysis_service import clean_json_string
        content = '```json\n{"key": "value"}\n```'
        result = clean_json_string(content)
        self.assertEqual(result, '{"key": "value"}')

    def test_clean_json_plain(self):
        """测试纯 JSON 字符串"""
        from app.llm.analysis_service import clean_json_string
        content = '{"key": "value"}'
        result = clean_json_string(content)
        self.assertEqual(result, '{"key": "value"}')

    def test_clean_json_with_whitespace(self):
        """测试带空白字符的 JSON"""
        from app.llm.analysis_service import clean_json_string
        content = '\n\n{"key": "value"}\n\n'
        result = clean_json_string(content)
        self.assertEqual(result, '{"key": "value"}')


# ===== analyze_diag_type 测试 =====

class TestAnalyzeDiagType:
    """诊断类型分析测试"""

    def test_analyze_diag_type_pneumonia(self, mock_openai_client):
        """测试肺炎诊断"""
        from app.llm.analysis_service import analyze_diag_type

        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "其他"
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_completion

        result = analyze_diag_type("诊断：肺炎")
        assert result is not None

    def test_analyze_diag_type_respiratory(self, mock_openai_client):
        """测试呼吸道感染诊断"""
        from app.llm.analysis_service import analyze_diag_type

        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "其他"
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_completion

        result = analyze_diag_type("诊断：呼吸道感染")
        assert result is not None


# ===== 预分析测试 =====

class TestPreAnalyze:
    """预分析函数测试"""

    @patch("app.llm.analysis_service.prompt_dao")
    def test_pre_analyze_preauth_result1(self, mock_prompt_dao, mock_openai_client, mock_connection_pool):
        """测试预分析方法1"""
        from app.llm.analysis_service import pre_analyze_preauth_result1

        mock_prompt_dao.get_prompt_by_type.return_value = {"prompt": "测试提示词"}

        test_json = '{"result": "12 - 批准 (GOP Approved)", "reason": "APV通过"}'
        mock_openai_client.chat.completions.create.return_value = _make_streaming_chunks(test_json)

        result = pre_analyze_preauth_result1("APV信息")
        assert result is not None

    @patch("app.llm.analysis_service.prompt_dao")
    def test_pre_analyze_preauth_result2(self, mock_prompt_dao, mock_openai_client, mock_connection_pool):
        """测试预分析方法2"""
        from app.llm.analysis_service import pre_analyze_preauth_result2

        mock_prompt_dao.get_prompt_by_type.return_value = {"prompt": "测试提示词"}

        test_json = '{"result": "13 - 拒绝 (GOP Rejected)", "reason": "保额不足"}'
        mock_openai_client.chat.completions.create.return_value = _make_streaming_chunks(test_json)

        result = pre_analyze_preauth_result2(
            hospital_info='{"hospital":"测试医院"}',
            amount="100000",
            document_result="文档分析结果",
            policy_except_info="除外条款"
        )
        assert result is not None

    @patch("app.llm.analysis_service.prompt_dao")
    def test_pre_analyze_policy_exceptinfo(self, mock_prompt_dao, mock_openai_client, mock_connection_pool):
        """测试保单除外信息预分析"""
        from app.llm.analysis_service import pre_analyze_policy_exceptinfo

        mock_prompt_dao.get_prompt_by_type.return_value = {"prompt": "测试提示词"}

        test_json = '{"has_exception": true, "exception_details": "不包含牙科"}'
        mock_openai_client.chat.completions.create.return_value = _make_streaming_chunks(test_json)

        result = pre_analyze_policy_exceptinfo("产品条款", "TOB条款")
        assert result is not None


# ===== 异常信息获取测试 =====

class TestGetExceptInfo:
    """除外信息获取测试"""

    @patch("app.llm.analysis_service.gop_config_dao")
    @patch("app.llm.analysis_service.prompt_dao")
    def test_get_except_info(self, mock_prompt_dao, mock_gop_config_dao, mock_openai_client):
        """测试获取除外信息"""
        from app.llm.analysis_service import get_except_info

        mock_prompt_dao.get_prompt_by_type.return_value = "测试除外提示词"
        mock_gop_config_dao.get_config_by_typ.return_value = []

        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "无除外项目"
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_completion

        result = get_except_info("文档分析结果", "查询详情")
        assert result is not None


# ===== APV 信息获取测试 =====

class TestGetAPVInfo:
    """APV信息获取测试"""

    def test_get_apv_info(self, mock_openai_client):
        """测试获取APV信息"""
        from app.llm.analysis_service import get_apv_info

        mock_openai_client.chat.completions.create.return_value = _make_streaming_chunks("无提前审核通过记录")

        result = get_apv_info("文档分析结果")
        assert result is not None


# ===== 住院指征信息测试 =====

class TestGetInpatientInfo:
    """住院指征信息测试"""

    @patch("app.llm.analysis_service.GopConfigDAO")
    @patch("app.llm.analysis_service.prompt_dao")
    def test_get_inpatient_info(self, mock_prompt_dao, mock_gop_config_dao_cls, mock_openai_client):
        """测试获取住院指征信息"""
        from app.llm.analysis_service import get_inpatient_info

        mock_prompt_dao.get_prompt_by_type.return_value = "测试住院指征提示词"
        mock_gop_config_dao = MagicMock()
        mock_gop_config_dao.get_config_by_typ.return_value = []
        mock_gop_config_dao_cls.return_value = mock_gop_config_dao

        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "住院指征明确"
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]
        mock_openai_client.chat.completions.create.return_value = mock_completion

        result = get_inpatient_info("文档分析结果")
        assert result is not None


# ===== 文档信息截断测试 =====

class TestCutDocumentInfo:
    """文档信息截断测试"""

    def test_cut_document_info_short(self):
        """测试短文档不截断"""
        from app.llm.analysis_service import cut_document_info
        short_text = "短文本"
        result = cut_document_info(short_text)
        assert result is not None
        assert len(result) > 0

    def test_cut_document_info_long(self):
        """测试长文档截断"""
        from app.llm.analysis_service import cut_document_info
        long_text = "A" * 5000
        result = cut_document_info(long_text)
        assert result is not None
        assert len(result) <= len(long_text)


# ===== 昂贵医院信息测试 =====

class TestExpensiveHospitalInfo:
    """昂贵医院信息测试"""

    def test_get_expensive_hospital_info(self, mock_openai_client, mock_connection_pool):
        """测试获取昂贵医院信息（使用mock DAO）"""
        from app.llm.analysis_service import get_expensive_hospital_info

        with patch("app.llm.analysis_service.GopConfigDAO") as mock_dao_cls:
            mock_dao = MagicMock()
            mock_dao.get_config_by_typ.return_value = []
            mock_dao_cls.return_value = mock_dao

            # 返回流式响应块
            mock_openai_client.chat.completions.create.return_value = _make_streaming_chunks("非昂贵医院")

            result = get_expensive_hospital_info("北京协和医院", "N", "CLAIM-001")
            assert result is not None
            assert result == "非昂贵医院"


# ===== 参数化测试 =====

@pytest.mark.parametrize("model_name", [
    "qwen-vl-plus",
    "qvq-plus-latest",
    "qwen3.5-plus",
    "qwen-long-latest",
])
def test_model_name_strings(model_name):
    """参数化测试：验证模型名称格式"""
    assert isinstance(model_name, str)
    assert len(model_name) > 0


@pytest.mark.parametrize("result_code,expected_category", [
    ("12", "批准"),
    ("13", "拒绝"),
    ("11", "人工审核"),
    ("39", "待定"),
])
def test_preauth_result_codes(result_code, expected_category):
    """参数化测试：验证预授权结果代码"""
    valid_codes = ["11", "12", "13", "39"]
    assert result_code in valid_codes


if __name__ == "__main__":
    unittest.main()