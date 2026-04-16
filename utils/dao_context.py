from contextlib import contextmanager

from dao.blacklist_member_dao import BlacklistMemberDAO
from dao.claim_case_dao import ClaimCaseDAO
from dao.basic_info_analyzed_analysis_dao import BasicInfoAnalyzedAnalysisDAO
from dao.document_analysis_dao import DocumentAnalysisDAO
from dao.policies_analysis_dao import PoliciesAnalysisDAO
from dao.provider_dao import ProviderDAO


@contextmanager
def dao_context():
    """
    提供一个上下文管理器来管理所有DAO实例
    确保即使在出现异常时也能正确处理资源
    """
    claim_dao = ClaimCaseDAO()
    basic_info_dao = BasicInfoAnalyzedAnalysisDAO()
    document_dao = DocumentAnalysisDAO()
    policies_dao = PoliciesAnalysisDAO()
    provider_dao = ProviderDAO()
    
    try:
        yield claim_dao, basic_info_dao, document_dao, policies_dao, provider_dao
    finally:
        # 使用连接池后，不需要手动关闭连接
        pass