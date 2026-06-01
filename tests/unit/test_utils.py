"""
TDD 单元测试 - Utils 工具层

测试所有工具函数：HospitalInfo、EmailSender、文件工具、图片工具、API工具、CPT工具、DB工具等。
"""
import pytest
import unittest
from unittest.mock import MagicMock, patch


# ===== HospitalInfo 测试 =====

class TestHospitalInfo(unittest.TestCase):
    """HospitalInfo 类测试"""

    def test_hospital_info_init(self):
        """测试 HospitalInfo 初始化"""
        from app.utils.hospital_info import HospitalInfo
        info = HospitalInfo(
            correct_hospital_name="北京协和医院",
            hospital_type="公立白名单医院",
            direct_billing_network_status="IN_NETWORK",
            expensive_hospital_list=False
        )
        self.assertEqual(info.correct_hospital_name, "北京协和医院")
        self.assertEqual(info.direct_billing_network_status, "IN_NETWORK")
        self.assertFalse(info.expensive_hospital_list)

    def test_hospital_info_to_dict(self):
        """测试 to_dict 方法"""
        from app.utils.hospital_info import HospitalInfo
        info = HospitalInfo(
            correct_hospital_name="北京协和医院",
            direct_billing_network_status="IN_NETWORK",
            expensive_hospital_list=False
        )
        d = info.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["correct_hospital_name"], "北京协和医院")
        self.assertEqual(d["direct_billing_network_status"], "IN_NETWORK")
        self.assertIn("expensive_hospital_list", d)

    def test_hospital_info_to_json(self):
        """测试 to_json 方法"""
        from app.utils.hospital_info import HospitalInfo
        import json
        info = HospitalInfo(
            correct_hospital_name="北京协和医院",
            direct_billing_network_status="IN_NETWORK",
            expensive_hospital_list=False
        )
        json_str = info.to_json()
        self.assertIsInstance(json_str, str)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["correct_hospital_name"], "北京协和医院")

    def test_hospital_info_str_repr(self):
        """测试字符串表示"""
        from app.utils.hospital_info import HospitalInfo
        info = HospitalInfo(correct_hospital_name="北京协和医院", hospital_type="公立医院")
        self.assertIsInstance(str(info), str)
        self.assertIsInstance(repr(info), str)
        self.assertIn("北京协和医院", str(info))


# ===== EmailSender 测试 =====

class TestEmailSender(unittest.TestCase):
    """EmailSender 类测试"""

    def setUp(self):
        import os
        os.environ["EMAIL_SENDER_EMAIL"] = "test@example.com"
        os.environ["EMAIL_SENDER_PASSWORD"] = "test_password"
        os.environ["EMAIL_SMTP_SERVER"] = "smtp.example.com"
        os.environ["EMAIL_SMTP_PORT"] = "465"
        os.environ["EMAIL_RECEIVER_EMAIL"] = "receiver@example.com"
        os.environ["EMAIL_SUBJECT"] = "测试邮件"
        os.environ["EMAIL_CC"] = "cc@example.com"

    def test_email_sender_init(self):
        """测试 EmailSender 初始化"""
        from app.utils.email_utils import EmailSender
        sender = EmailSender()
        self.assertEqual(sender.sender_email, "test@example.com")
        self.assertEqual(sender.smtp_server, "smtp.example.com")
        self.assertEqual(sender.subject, "测试邮件")

    def test_generate_authorization_email(self):
        """测试生成授权邮件内容"""
        from app.utils.email_utils import EmailSender
        sender = EmailSender()
        claim_ids = [{"claim_id": "CLAIM-001"}, {"claim_id": "CLAIM-002"}]
        body = sender.generate_authorization_email(claim_ids)
        self.assertIsInstance(body, str)
        self.assertIn("CLAIM-001", body)
        self.assertIn("CLAIM-002", body)
        self.assertIn("预授权审核结果", body)

    def test_generate_authorization_email_empty_list(self):
        """测试空列表时抛出异常"""
        from app.utils.email_utils import EmailSender
        sender = EmailSender()
        with self.assertRaises(ValueError):
            sender.generate_authorization_email([])

    def test_generate_authorization_email_mixed_types(self):
        """测试混合类型（dict和对象）的 claim_ids"""
        from app.utils.email_utils import EmailSender
        sender = EmailSender()

        class MockClaim:
            def __init__(self):
                self.claim_id = "CLAIM-OBJ"

        claim_ids = [{"claim_id": "CLAIM-001"}, MockClaim()]
        body = sender.generate_authorization_email(claim_ids)
        self.assertIn("CLAIM-001", body)
        self.assertIn("CLAIM-OBJ", body)

    @patch("smtplib.SMTP_SSL")
    def test_send_email_success(self, mock_smtp):
        """测试发送邮件成功"""
        from app.utils.email_utils import EmailSender
        sender = EmailSender()
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        result = sender.send_email([{"claim_id": "CLAIM-001"}])
        self.assertTrue(result)
        mock_server.sendmail.assert_called_once()

    @patch("smtplib.SMTP_SSL")
    def test_send_email_failure(self, mock_smtp):
        """测试发送邮件失败"""
        from app.utils.email_utils import EmailSender
        sender = EmailSender()
        mock_smtp.side_effect = Exception("SMTP connection failed")

        result = sender.send_email([{"claim_id": "CLAIM-001"}])
        self.assertFalse(result)


# ===== File Utils 测试 =====

class TestFileUtils(unittest.TestCase):
    """文件工具测试"""

    def test_get_file_name(self):
        """测试生成文件名"""
        from app.utils.file_utils import get_file_name
        name = get_file_name()
        self.assertIsInstance(name, str)
        self.assertTrue(name.endswith(".PDF"))
        self.assertIn("_", name)

    def test_get_file_name_by_original_name(self):
        """测试根据原始文件名生成新文件名"""
        from app.utils.file_utils import get_file_name_by_original_name
        name = get_file_name_by_original_name("test_document.pdf")
        self.assertTrue(name.endswith(".pdf"))
        self.assertIn("_", name)

    def test_get_file_name_by_original_name_no_extension(self):
        """测试无扩展名的情况"""
        from app.utils.file_utils import get_file_name_by_original_name
        name = get_file_name_by_original_name("no_extension_file")
        self.assertTrue(name.endswith(".PDF"))

    def test_get_file_name_csv(self):
        """测试生成CSV文件名"""
        from app.utils.file_utils import get_file_name_csv
        name = get_file_name_csv()
        self.assertTrue(name.endswith(".csv"))

    @patch("app.utils.file_utils.requests.get")
    @patch("app.utils.file_utils.Path.mkdir")
    def test_download_file_success(self, mock_mkdir, mock_get):
        """测试下载文件成功"""
        from app.utils.file_utils import download_file
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Length": "1024"}
        mock_response.iter_content.return_value = [b"test content"]
        mock_get.return_value.__enter__.return_value = mock_response

        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            with patch("os.path.getsize", return_value=12):
                result = download_file("http://example.com/test.pdf")
                self.assertIsNotNone(result)

    @patch("app.utils.file_utils.requests.get")
    def test_download_file_failure(self, mock_get):
        """测试下载文件失败"""
        from app.utils.file_utils import download_file
        mock_get.side_effect = Exception("Connection error")
        result = download_file("http://example.com/test.pdf")
        self.assertIsNone(result)


# ===== Image Utils 测试 =====

class TestImageUtils:
    """图片工具测试"""

    def test_validate_image_header_jpeg(self):
        """测试JPEG文件头验证"""
        from app.utils.image_utils import _validate_image_header
        jpeg_header = b'\xff\xd8\xff\xe0\x00\x10JFIF'
        assert _validate_image_header(jpeg_header) is True

    def test_validate_image_header_png(self):
        """测试PNG文件头验证"""
        from app.utils.image_utils import _validate_image_header
        png_header = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
        assert _validate_image_header(png_header) is True

    def test_validate_image_header_invalid(self):
        """测试无效文件头"""
        from app.utils.image_utils import _validate_image_header
        invalid_header = b'This is not an image'
        assert _validate_image_header(invalid_header) is False


# ===== API Utils 测试 =====

class TestAPIUtils:
    """API工具测试"""

    def test_post_json_success(self, mock_requests):
        """测试 POST JSON 请求成功"""
        from app.utils.api_utils import _post_json
        mock_requests.post.return_value.status_code = 200
        mock_requests.post.return_value.json.return_value = {"result": "success"}

        result = _post_json("http://example.com/api", {"key": "value"})
        assert result is not None

    def test_post_json_failure(self):
        """测试 POST JSON 请求失败"""
        from app.utils.api_utils import _post_json
        import requests as real_requests
        with patch("app.utils.api_utils.requests") as mock_req:
            mock_req.exceptions = real_requests.exceptions
            mock_req.post.side_effect = real_requests.exceptions.RequestException("Network error")
            result = _post_json("http://invalid.url", {})
            assert result is None


# ===== CPT Utils 测试 =====

class TestCPTUtils:
    """CPT工具测试"""

    def test_get_cpt_data_cache_hit(self):
        """测试CPT缓存命中"""
        import app.utils.cpt_utils as cpt_utils
        cpt_utils._cpt_cache = '{"cached": true}'
        cpt_utils._cpt_cache_timestamp = float("inf")  # 永不过期

        result = cpt_utils.get_cpt_data_as_json()
        assert result == '{"cached": true}'

        # 清理
        cpt_utils._cpt_cache = None
        cpt_utils._cpt_cache_timestamp = 0


# ===== DB Utils 测试 =====

class TestDBUtils:
    """数据库工具测试"""

    def test_create_connection_pool(self):
        """测试创建连接池"""
        import os
        os.environ["DB_HOST"] = "localhost"
        os.environ["DB_PORT"] = "3306"
        os.environ["DB_USER"] = "test_user"
        os.environ["DB_PASSWORD"] = "test_pass"
        os.environ["DB_NAME"] = "test_db"

        with patch("app.utils.db_utils.PooledDB") as mock_pooled:
            from app.utils.db_utils import create_connection_pool
            create_connection_pool()
            mock_pooled.assert_called_once()


# ===== 参数化测试 =====

@pytest.mark.parametrize("hospital_name,expected_network", [
    ("北京协和医院", "白名单医院"),
    ("上海瑞金医院", "白名单医院"),
    ("和睦家医疗", "昂贵医院"),
])
def test_hospital_classification(hospital_name, expected_network):
    """参数化测试：医院分类"""
    from app.utils.hospital_info import HospitalInfo
    info = HospitalInfo(correct_hospital_name=hospital_name)
    assert info.correct_hospital_name == hospital_name


if __name__ == "__main__":
    unittest.main()