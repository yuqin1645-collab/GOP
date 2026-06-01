"""
理赔案件数据模型
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class ClaimCase:
    """理赔案件模型"""
    claim_id: str
    basic_info_analyzed: int = 0
    documents_analyzed: int = 0
    policies_analyzed: int = 0
    preauth_status: int = 0
    preauth_result: Optional[str] = None
    admission_date: Optional[str] = None
    gop_type: Optional[str] = None
    payor_name: Optional[str] = None
    corporate_code: Optional[str] = None
    patient_name: Optional[str] = None
    am: Optional[str] = None
    provider_name: Optional[str] = None
    provider_type: Optional[str] = None
    pri_diag_desc: Optional[str] = None
    transmission_date: Optional[str] = None
    provider_code: Optional[str] = None
    admission_type: Optional[str] = None
    diangosis: Optional[str] = None
    cpt: Optional[str] = None
    amount: Optional[float] = None
    amount_currency: Optional[str] = None
    provider_cate: Optional[str] = None
    provider_open_for_out: Optional[str] = None
    payor_code: Optional[str] = None
    payor_attr: Optional[str] = None
    loss_ratio: Optional[str] = None
    query_details: Optional[str] = None
    reco_benfit: Optional[str] = None
    claims_rec_date: Optional[str] = None
    review_flag: Optional[str] = None
    sync_eccs_flag: str = 'N'
    ai_result: Optional[str] = None
    ai_result_desc: Optional[str] = None
    ai_reason: Optional[str] = None
    old_preauth_result: Optional[str] = None
    eccs_result: Optional[str] = None
    compare_result: Optional[int] = None
    compare_result_desc: Optional[str] = None
    eccs_reason: Optional[str] = None
    apv_amount: Optional[float] = None
    diag_type: Optional[str] = None
    apply_date: Optional[datetime] = None
    update_time: Optional[datetime] = None
    sync_time: Optional[datetime] = None
    create_time: Optional[datetime] = None
    
    @property
    def is_completed(self) -> bool:
        """判断是否所有分析都已完成"""
        return (
            self.basic_info_analyzed == 1
            and self.documents_analyzed == 1
            and self.policies_analyzed == 1
            and self.preauth_status == 0
        )
    
    @property
    def is_hospital_type(self) -> bool:
        """判断是否为医院类型GOP"""
        return not self.gop_type or self.gop_type == "hospital"
    
    @property
    def is_xinyanbao(self) -> bool:
        """判断是否为新燕宝产品"""
        return self.corporate_code and 'xinyanbao' in self.corporate_code.lower()
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ClaimCase':
        """从字典创建实例"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {k: v for k, v in self.__dict__.items() if k in cls.__dataclass_fields__}
