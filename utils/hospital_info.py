from dao.gop_config_dao import GopConfigDAO
from llm.analysis_service import get_expensive_hospital_info, get_except_hospital_info
from utils.api_utils import get_direct_pay_hosp_api
import json


class HospitalInfo:
    """
    医院信息类，包含医院的基本信息和分类属性
    """

    def __init__(self, correct_hospital_name=None, hospital_type=None, direct_billing_network_status=None,
                 expensive_hospital_list=False, excluded_network_list=False):
        """
        初始化医院信息对象
        
        :param correct_hospital_name: 医院名称
        :param hospital_type: 医院类型
        :param direct_billing_network_status: 是否在直付网络
        :param expensive_hospital_list: 是否昂贵医院
        :param excluded_network_list: 是否除外医院
        """
        self.correct_hospital_name = correct_hospital_name
        # self.hospital_type = hospital_type
        self.direct_billing_network_status = direct_billing_network_status
        self.expensive_hospital_list = expensive_hospital_list
        # self.excluded_network_list = excluded_network_list

    @staticmethod
    def from_provider_info(provider_name, provider_code, am, claim_id,provider_cate,provider_open_for_out):
        """
        根据供应商名称和代码创建HospitalInfo对象
        
        :param provider_name: 供应商名称
        :param provider_code: 供应商代码
        :param am: AM参数
        :param claim_id: 理赔ID
        :return: HospitalInfo 对象
        """
        # 导入必要的模块
        from dao.provider_dao import ProviderDAO
        # 假设get_direct_pay_hosp_api在某个工具模块中，这里需要根据实际情况导入
        # from utils.api_utils import get_direct_pay_hosp_api
        
        # 这里可以根据实际业务逻辑从数据库或其他数据源获取医院的完整信息
        # 当前实现仅演示基本用法
        hosp_type = '普通医院'
        provider_dao = ProviderDAO()
        provider_info = provider_dao.get_provider_by_code(provider_code)
        if provider_info and provider_info.get('gop_white_list') == 'Y':
            hosp_type = '公立白名单医院'
        
        # 直付网络逻辑
        if "赫康" in provider_name and provider_open_for_out == 'N' and provider_cate == 'CF':
            if_direct_pay_hosp = "IN_NETWORK"
        elif provider_cate == 'NP':
            if_direct_pay_hosp = "IN_NETWORK"
        else:
            if_direct_pay_hosp = get_direct_pay_hosp_api(provider_code)
            if if_direct_pay_hosp:
                if_direct_pay_hosp = "IN_NETWORK"
            else:
                if_direct_pay_hosp = "OUT_OF_NETWORK"

        # AM参数判断逻辑
        if am:
            group_flag = "Y"
        else:
            group_flag = "N"

        #昂贵医院
        expensive_hospital_info = get_expensive_hospital_info(provider_name,group_flag,claim_id)

        #除外医疗机构
        # except_hospital_info = get_except_hospital_info(provider_name)
        except_hospital_info = ""

        hospital_info = HospitalInfo(
            correct_hospital_name=provider_name,
            hospital_type=hosp_type,
            direct_billing_network_status=if_direct_pay_hosp,
            expensive_hospital_list=expensive_hospital_info
        )
        # 可以在这里添加更多逻辑来填充其他字段
        # 比如根据provider_code查询数据库获取医院类型等信息
        return hospital_info

    def to_dict(self):
        """
        将医院信息对象转换为字典格式
        
        :return: 包含医院信息的字典
        """
        return {
            'correct_hospital_name': self.correct_hospital_name
            # ,'hospital_type': self.hospital_type
            ,'direct_billing_network_status': self.direct_billing_network_status
            ,'expensive_hospital_list': self.expensive_hospital_list
            # 'excluded_network_list': self.excluded_network_list
        }

    def to_json(self):
        """
        将医院信息对象转换为JSON格式字符串
        
        :return: JSON格式字符串
        """
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def __str__(self):
        """
        返回医院信息的字符串表示
        """
        return f"HospitalInfo(name={self.correct_hospital_name}, type={self.hospital_type})"

    def __repr__(self):
        """
        返回医院信息的详细表示
        """
        return (f"HospitalInfo(correct_hospital_name='{self.correct_hospital_name}', "
                f"hospital_type='{self.hospital_type}', "
                f"direct_billing_network_status={self.direct_billing_network_status}, "
                f"expensive_hospital_list={self.expensive_hospital_list}, "
                f"excluded_network_list={self.excluded_network_list})")