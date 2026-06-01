"""
配置管理模块
集中管理应用配置，支持环境变量和默认值
"""
import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DatabaseConfig:
    """数据库配置"""
    host: str = field(default_factory=lambda: os.getenv('DB_HOST', ''))
    port: int = field(default_factory=lambda: int(os.getenv('DB_PORT', '3306')))
    user: str = field(default_factory=lambda: os.getenv('DB_USER', ''))
    password: str = field(default_factory=lambda: os.getenv('DB_PASSWORD', ''))
    database: str = field(default_factory=lambda: os.getenv('DB_NAME', ''))
    charset: str = 'utf8mb4'
    max_connections: int = 25
    blocking: bool = True
    
    def validate(self) -> list:
        """验证必需配置项"""
        errors = []
        if not self.host:
            errors.append("DB_HOST is required")
        if not self.user:
            errors.append("DB_USER is required")
        if not self.database:
            errors.append("DB_NAME is required")
        return errors
    
    @property
    def connection_string(self) -> str:
        return f"mysql://{self.user}:***@{self.host}:{self.port}/{self.database}"


@dataclass
class LLMConfig:
    """LLM 模型配置"""
    api_key: str = field(default_factory=lambda: os.getenv('api_key', ''))
    base_url: str = field(default_factory=lambda: os.getenv('base_url', 'https://dashscope.aliyuncs.com'))
    model_document_analysis: str = field(default_factory=lambda: os.getenv('MODEL_DOCUMENT_ANALYSIS', 'qwen-vl-plus'))
    model_document_qvq: str = field(default_factory=lambda: os.getenv('MODEL_DOCUMENT_QVQ', 'qvq-plus-latest'))
    model_text_analysis: str = field(default_factory=lambda: os.getenv('MODEL_TEXT_ANALYSIS', 'qwen3.5-plus'))
    model_long_document: str = field(default_factory=lambda: os.getenv('MODEL_LONG_DOCUMENT', 'qwen-long-latest'))
    enable_thinking: bool = field(default_factory=lambda: os.getenv('ENABLE_THINKING', 'true').lower() == 'true')
    enable_qvq_cross_check: bool = field(default_factory=lambda: os.getenv('ENABLE_QVQ_CROSS_CHECK', 'true').lower() == 'true')
    
    def validate(self) -> list:
        errors = []
        if not self.api_key:
            errors.append("api_key is required")
        return errors


@dataclass
class APIConfig:
    """外部 API 配置"""
    get_gop_claim_list_url: str = field(default_factory=lambda: os.getenv('getGopClaimListUrl', ''))
    get_re_gop_claim_list_url: str = field(default_factory=lambda: os.getenv('getReGopClaimListUrl', ''))
    get_claim_info_api_url: str = field(default_factory=lambda: os.getenv('getClaimInfoApiUrl', ''))
    get_policy_wording_url: str = field(default_factory=lambda: os.getenv('getPolicyWordingUrl', ''))
    get_documents_url: str = field(default_factory=lambda: os.getenv('getDocumentsUrl', ''))
    update_pre_auth_result_url: str = field(default_factory=lambda: os.getenv('updatePreAuthResultUrl', ''))
    eccs_web_url_base: str = field(default_factory=lambda: os.getenv('eccsWebUrlBase', ''))
    eccs_core_url_base: str = field(default_factory=lambda: os.getenv('eccsCoreUrlBase', ''))


@dataclass
class AppConfig:
    """应用主配置"""
    flask_debug: bool = field(default_factory=lambda: os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
    host: str = '0.0.0.0'
    port: int = 5000
    max_content_length: int = 50 * 1024 * 1024  # 50MB
    log_path: str = field(default_factory=lambda: os.getenv('LOG_PATH', 'D:/GopLogs/app.log'))
    
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    api: APIConfig = field(default_factory=APIConfig)
    
    def validate(self) -> list:
        """验证所有配置"""
        errors = []
        errors.extend(self.database.validate())
        errors.extend(self.llm.validate())
        return errors
    
    def raise_if_invalid(self):
        """如果配置无效则抛出异常"""
        errors = self.validate()
        if errors:
            raise ValueError(f"Configuration errors: {'; '.join(errors)}")


# 全局配置实例
config = AppConfig()
