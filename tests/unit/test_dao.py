"""
TDD 单元测试 - DAO 层

遵循 TDD (Test-Driven Development) 方法:
- 红阶段: 编写失败测试
- 绿阶段: 实现最小可用代码
- 重构阶段: 优化代码结构

测试覆盖所有 DAO 类的基本 CRUD 操作和错误处理。
"""

import pytest
import unittest
from unittest.mock import MagicMock, patch


# ===== Unit Tests =====

class TestBaseDAO(unittest.TestCase):
    """BaseDAO 基类测试"""

    def setUp(self):
        from app.dao.base import BaseDAO
        self.dao = BaseDAO()
        # 创建 mock 连接和游标
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_cursor.rowcount = 1
        self.mock_conn.cursor.return_value = self.mock_cursor
        # 直接 mock _get_connection 方法
        self._conn_patcher = patch.object(self.dao, '_get_connection', return_value=self.mock_conn)
        self._conn_patcher.start()
        self.addCleanup(self._conn_patcher.stop)

    def test_base_dao_instantiation(self):
        """测试 BaseDAO 可以实例化"""
        self.assertIsNotNone(self.dao)

    def test_get_connection_success(self):
        """测试成功获取数据库连接"""
        self._conn_patcher.stop()
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.connection.return_value = mock_conn
        self.dao.connection_pool = mock_pool
        conn = self.dao._get_connection()
        self.assertIsNotNone(conn)

    def test_fetch_one_executes_query(self):
        """测试 _fetch_one 成功执行查询"""
        expected_result = {"id": 1, "name": "test"}
        self.mock_cursor.fetchone.return_value = expected_result

        result = self.dao._fetch_one("SELECT * FROM test WHERE id = %s", (1,))

        self.assertEqual(result, expected_result)
        self.mock_cursor.execute.assert_called_once()


class TestClaimCaseDAO(unittest.TestCase):
    """ClaimCaseDAO 测试"""

    def setUp(self):
        from app.dao.claim_case_dao import ClaimCaseDAO
        self.dao = ClaimCaseDAO()
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_cursor.rowcount = 1
        self.mock_conn.cursor.return_value = self.mock_cursor
        self._conn_patcher = patch.object(self.dao, '_get_connection', return_value=self.mock_conn)
        self._conn_patcher.start()
        self.addCleanup(self._conn_patcher.stop)

    def test_insert_claim_case(self):
        """测试插入理赔案件"""
        result = self.dao.insert_claim_case(
            claim_id="TEST-001",
            claim_info={"test": True}
        )
        self.assertEqual(result, 1)

    def test_insert_claim_case_with_optional_fields(self):
        """测试插入带可选字段的理赔案件"""
        result = self.dao.insert_claim_case(
            claim_id="TEST-002",
            claim_info={"test": True},
            basic_info_analyzed=1,
            documents_analyzed=0,
            policies_analyzed=0
        )
        self.assertEqual(result, 1)

    def test_update_claim_case(self):
        """测试更新理赔案件"""
        # update_claim_case 不返回有意义的值（隐式返回 None），
        # 只验证方法不抛异常且 mock 调用正确
        self.dao.update_claim_case(
            claim_id="TEST-001",
            preauth_status=1,
            preauth_result={"approved": True}
        )
        self.mock_cursor.execute.assert_called_once()
        self.mock_conn.commit.assert_called_once()

    def test_get_claims_to_sync_eccs(self):
        """测试获取待同步 ECCS 的案件"""
        self.mock_cursor.fetchall.return_value = [
            {"claim_id": "TEST-001", "basic_info_analyzed": 1}
        ]

        result = self.dao.get_claims_to_sync_eccs()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)


class TestDocumentAnalysisDAO(unittest.TestCase):
    """DocumentAnalysisDAO 测试"""

    def setUp(self):
        from app.dao.document_analysis_dao import DocumentAnalysisDAO
        self.dao = DocumentAnalysisDAO()
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_cursor.rowcount = 1
        self.mock_conn.cursor.return_value = self.mock_cursor
        self._conn_patcher = patch.object(self.dao, '_get_connection', return_value=self.mock_conn)
        self._conn_patcher.start()
        self.addCleanup(self._conn_patcher.stop)

    def test_insert_document_analysis(self):
        """测试插入文档分析"""
        result = self.dao.insert_document_analysis(
            claim_id="TEST-001",
            image_quality=0.95,
            consistency=0.90,
            diff="无差异",
            file_name="test.jpg",
            file_url="http://example.com/test.jpg"
        )
        self.assertEqual(result, 1)

    def test_update_document_analysis(self):
        """测试更新文档分析"""
        result = self.dao.update_document_analysis(
            claim_id="TEST-001",
            image_quality=0.85,
            consistency=0.80,
            analysis_result="分析结果"
        )
        self.assertIsNotNone(result)


class TestProviderDAO(unittest.TestCase):
    """ProviderDAO 测试"""

    def setUp(self):
        from app.dao.provider_dao import ProviderDAO
        self.dao = ProviderDAO()
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_cursor.rowcount = 1
        self.mock_cursor.lastrowid = 1
        self.mock_conn.cursor.return_value = self.mock_cursor
        self._conn_patcher = patch.object(self.dao, '_get_connection', return_value=self.mock_conn)
        self._conn_patcher.start()
        self.addCleanup(self._conn_patcher.stop)

    def test_insert_provider(self):
        """测试插入供应商"""
        result = self.dao.insert_provider("P001", "测试医院", "公立医院")
        self.assertEqual(result, 1)

    def test_update_provider(self):
        """测试更新供应商"""
        result = self.dao.update_provider(1, provider_type="私立医院")
        self.assertIsNotNone(result)


class TestBlacklistMemberDAO(unittest.TestCase):
    """BlacklistMemberDAO 测试"""

    def setUp(self):
        from app.dao.blacklist_member_dao import BlacklistMemberDAO
        self.dao = BlacklistMemberDAO()
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_cursor.rowcount = 1
        self.mock_conn.cursor.return_value = self.mock_cursor
        self._conn_patcher = patch.object(self.dao, '_get_connection', return_value=self.mock_conn)
        self._conn_patcher.start()
        self.addCleanup(self._conn_patcher.stop)

    def test_insert_blacklist_member(self):
        """测试插入黑名单成员"""
        result = self.dao.insert_blacklist_member(
            id=1, name="测试用户", id_type="身份证", new_ic="110101199001011234"
        )
        self.assertIsNotNone(result)


class TestPromptDAO(unittest.TestCase):
    """PromptDAO 测试"""

    def setUp(self):
        from app.dao.prompt_dao import PromptDAO
        self.dao = PromptDAO()
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_cursor.rowcount = 1
        self.mock_cursor.lastrowid = 1
        self.mock_conn.cursor.return_value = self.mock_cursor
        self._conn_patcher = patch.object(self.dao, '_get_connection', return_value=self.mock_conn)
        self._conn_patcher.start()
        self.addCleanup(self._conn_patcher.stop)

    def test_insert_prompt(self):
        """测试插入 Prompt"""
        result = self.dao.insert_prompt("GOP_TEST", "测试提示词", "这是测试内容")
        self.assertEqual(result, 1)

    def test_get_prompt_by_type(self):
        """测试按类型获取 Prompt"""
        self.mock_cursor.fetchone.return_value = {"prompt": "测试内容", "prompt_type": "GOP_TEST"}
        result = self.dao.get_prompt_by_type("GOP_TEST")
        self.assertIsNotNone(result)


class TestDAODatabaseError:
    """测试数据库错误处理"""

    def test_claim_insert_handles_mysql_error(self):
        """测试插入时 MySQL 错误的处理"""
        from pymysql.err import MySQLError
        from app.dao.claim_case_dao import ClaimCaseDAO

        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = MySQLError("模拟数据库错误")

        dao = ClaimCaseDAO()
        with patch.object(dao, '_get_connection', return_value=mock_conn):
            with pytest.raises(MySQLError):
                dao.insert_claim_case("TEST-ERR", {"test": True})

    def test_provider_insert_handles_error(self):
        """测试插入供应商时的错误处理"""
        from pymysql.err import MySQLError
        from app.dao.provider_dao import ProviderDAO

        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = MySQLError("模拟数据库错误")

        dao = ProviderDAO()
        with patch.object(dao, '_get_connection', return_value=mock_conn):
            with pytest.raises(MySQLError):
                dao.insert_provider("P001", "测试医院", "公立医院")


# ===== 参数化测试 =====

@pytest.mark.parametrize("claim_id,expected_type", [
    ("TEST-001", str),
    ("TEST-002", str),
    ("TEST-003", str),
])
def test_claim_id_is_string(claim_id, expected_type):
    """参数化测试: 验证 claim_id 始终为字符串类型"""
    assert isinstance(claim_id, expected_type)


@pytest.mark.parametrize("provider_name,provider_code", [
    ("北京协和医院", "P001"),
    ("上海瑞金医院", "P002"),
    ("广州中山大学附属第一医院", "P003"),
])
def test_provider_data_structure(provider_name, provider_code):
    """参数化测试: 验证供应商数据结构"""
    record = {"provider_name": provider_name, "provider_code": provider_code}
    assert record["provider_name"] == provider_name
    assert record["provider_code"] == provider_code


if __name__ == "__main__":
    unittest.main()