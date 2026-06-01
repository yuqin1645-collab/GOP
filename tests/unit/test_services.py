"""
TDD 单元测试 - Services 服务层

遵循 TDD (Test-Driven Development) 方法测试 ClaimService、PolicyService、SyncService 的核心业务逻辑。
"""
import pytest
import unittest
from unittest.mock import MagicMock, patch, PropertyMock, call


# ===== ClaimService 测试 =====

class TestClaimServiceInit(unittest.TestCase):
    """ClaimService 初始化测试"""

    def setUp(self):
        from app.services.claim_service import ClaimService
        self.service = ClaimService()

    def test_claim_service_instantiation(self):
        """测试 ClaimService 可以实例化"""
        self.assertIsNotNone(self.service)
        self.assertIsNotNone(self.service._lock)

    @patch("app.services.claim_service.dao_context")
    def test_process_claim_init_new_claim(self, mock_dao_context):
        """测试初始化新的理赔案件"""
        mock_claim_dao = MagicMock()
        mock_claim_dao.get_claim_case_by_id.return_value = None
        mock_claim_dao.insert_claim_case.return_value = 1

        mock_dao_context.return_value.__enter__.return_value = (
            mock_claim_dao, None, None, None, None
        )

        claim_info = {"claimsId": "TEST-001", "claimType": "hospital"}
        self.service.process_claim_init(claim_info, mock_claim_dao)

        mock_claim_dao.insert_claim_case.assert_called_once_with(
            claim_id="TEST-001", claim_info=claim_info
        )

    @patch("app.services.claim_service.dao_context")
    def test_process_claim_init_skip_existing(self, mock_dao_context):
        """测试跳过已存在的理赔案件"""
        mock_claim_dao = MagicMock()
        mock_claim_dao.get_claim_case_by_id.return_value = {"claim_id": "TEST-001"}

        mock_dao_context.return_value.__enter__.return_value = (
            mock_claim_dao, None, None, None, None
        )

        claim_info = {"claimsId": "TEST-001"}
        self.service.process_claim_init(claim_info, mock_claim_dao)

        mock_claim_dao.insert_claim_case.assert_not_called()


class TestClaimServiceProcessBasicInfo(unittest.TestCase):
    """ClaimService 基本信息处理测试"""

    def setUp(self):
        from app.services.claim_service import ClaimService
        self.service = ClaimService()

    @patch("app.services.claim_service.dao_context")
    @patch("app.services.claim_service.get_claim_info_api")
    def test_process_basic_info_no_claims(self, mock_get_claim, mock_dao_context):
        """测试没有待处理案件时的行为"""
        mock_claim_dao = MagicMock()
        mock_claim_dao.get_claims_to_process_basic_info.return_value = []

        mock_dao_context.return_value.__enter__.return_value = (
            mock_claim_dao, MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )

        result = self.service.process_basic_info()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["processed"], 0)

    @patch("app.services.claim_service.dao_context")
    @patch("app.services.claim_service.get_claim_info_api")
    def test_process_basic_info_success(self, mock_get_claim, mock_dao_context):
        """测试成功处理基本信息"""
        mock_get_claim.return_value = {"name": "张三", "diagnosis": "急性胃炎"}

        mock_claim_dao = MagicMock()
        mock_claim_dao.get_claims_to_process_basic_info.return_value = [
            {"claim_id": "TEST-001"}
        ]

        mock_basic_info_dao = MagicMock()
        mock_basic_info_dao.get_basic_info_analysis_by_id.return_value = None

        mock_dao_context.return_value.__enter__.return_value = (
            mock_claim_dao, mock_basic_info_dao, MagicMock(), MagicMock(), MagicMock()
        )

        result = self.service.process_basic_info()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["processed"], 1)
        mock_basic_info_dao.insert_basic_info_analysis.assert_called_once()

    @patch("app.services.claim_service.dao_context")
    @patch("app.services.claim_service.get_claim_info_api")
    def test_process_basic_info_api_failure(self, mock_get_claim, mock_dao_context):
        """测试API获取失败时的处理"""
        mock_get_claim.return_value = None

        mock_claim_dao = MagicMock()
        mock_claim_dao.get_claims_to_process_basic_info.return_value = [
            {"claim_id": "TEST-001"}
        ]

        mock_dao_context.return_value.__enter__.return_value = (
            mock_claim_dao, MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )

        result = self.service.process_basic_info()
        self.assertEqual(result["data"]["processed"], 0)


# ===== PolicyService 测试 =====

class TestPolicyService(unittest.TestCase):
    """PolicyService 测试"""

    def setUp(self):
        from app.services.policy_service import PolicyService
        self.service = PolicyService()

    @patch("app.services.policy_service.dao_context")
    def test_process_policies_no_claims(self, mock_dao_context):
        """测试没有待处理案件"""
        mock_claim_dao = MagicMock()
        mock_claim_dao.get_claims_to_process_policies_info.return_value = []

        mock_dao_context.return_value.__enter__.return_value = (
            mock_claim_dao, MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )

        result = self.service.process_policies_info()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["success_count"], 0)
        self.assertEqual(result["failed_count"], 0)


# ===== SyncService 测试 =====

class TestSyncService(unittest.TestCase):
    """SyncService 测试"""

    def setUp(self):
        from app.services.sync_service import SyncService
        self.service = SyncService()

    @patch("app.services.sync_service.dao_context")
    def test_sync_eccs_no_claims(self, mock_dao_context):
        """测试没有待同步案件"""
        mock_claim_dao = MagicMock()
        mock_claim_dao.get_claims_to_sync_eccs.return_value = []

        mock_dao_context.return_value.__enter__.return_value = (
            mock_claim_dao, MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )

        result = self.service.sync_eccs_result()
        self.assertEqual(result["status"], "success")
        self.assertIn("没有需要同步", result["message"])

    def test_sync_provider_valid_data(self):
        """测试同步供应商有效数据"""
        providers = [
            {"providerCode": "P001", "longName": "测试医院", "providerType": "公立医院"}
        ]

        with patch("app.services.sync_service.ProviderDAO") as mock_provider_dao_cls:
            mock_dao_instance = MagicMock()
            mock_dao_instance.get_provider_by_code.return_value = None
            mock_provider_dao_cls.return_value = mock_dao_instance

            result = self.service.sync_provider_info(providers)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["data"]["synced"], 1)

    def test_sync_provider_invalid_data(self):
        """测试同步供应商无效数据"""
        result = self.service.sync_provider_info("not_a_list")
        # sync_provider_info returns tuple (dict, status_code) on invalid input
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)
        self.assertIn("error", result[0])

    def test_sync_provider_empty_list(self):
        """测试同步空供应商列表"""
        with patch("app.services.sync_service.ProviderDAO") as mock_provider_dao_cls:
            mock_dao_instance = MagicMock()
            mock_provider_dao_cls.return_value = mock_dao_instance

            result = self.service.sync_provider_info([])
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["data"]["synced"], 0)

    def test_sync_blacklist_valid_data(self):
        """测试同步黑名单有效数据"""
        with patch("app.services.sync_service.BlacklistMemberDAO") as mock_dao_cls:
            mock_dao_instance = MagicMock()
            mock_dao_instance.get_blacklist_member_by_id.return_value = None
            mock_dao_cls.return_value = mock_dao_instance

            blacks = [
                {"id": "BL001", "name": "测试用户", "idType": "身份证", "newIc": "110101199001011234"}
            ]
            result = self.service.sync_blacklist_member(blacks)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["data"]["synced"], 1)

    def test_sync_blacklist_invalid_data(self):
        """测试同步黑名单无效数据"""
        result = self.service.sync_blacklist_member("not_a_list")
        # sync_blacklist_member returns tuple (dict, status_code)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)
        self.assertIn("error", result[0])


# ===== 服务层集成测试 (Mock) =====

class TestServiceIntegration:
    """服务层集成测试 - 使用 Mock 模拟依赖"""

    def test_claim_service_with_mock_llm(self, mock_openai_client, mock_connection_pool):
        """测试 ClaimService 与 mock LLM 的集成"""
        from app.services.claim_service import ClaimService
        service = ClaimService()
        assert service is not None

    def test_policy_service_with_mock(self, mock_connection_pool):
        """测试 PolicyService 与 mock DB 的集成"""
        from app.services.policy_service import PolicyService
        service = PolicyService()
        assert service is not None

    def test_sync_service_with_mock(self, mock_connection_pool):
        """测试 SyncService 与 mock DB 的集成"""
        from app.services.sync_service import SyncService
        service = SyncService()
        assert service is not None


if __name__ == "__main__":
    unittest.main()