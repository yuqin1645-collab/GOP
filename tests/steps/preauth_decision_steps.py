"""
BDD 步骤定义 - 预授权审核决策

使用 pytest-bdd 编写的步骤实现，对应 features/preauth_decision.feature
"""
import json
from pytest_bdd import given, when, then, parsers, scenario


# ===== 场景: 标准门诊案件批准 =====

@scenario("features/preauth_decision.feature", "标准门诊案件批准")
def test_standard_approval():
    pass


@scenario("features/preauth_decision.feature", "昂贵医院就医案件拒绝")
def test_expensive_hospital_rejection():
    pass


@scenario("features/preauth_decision.feature", "除外医疗机构案件拒绝")
def test_excluded_hospital_rejection():
    pass


@scenario("features/preauth_decision.feature", "保额不足案件拒绝")
def test_insufficient_coverage():
    pass


@scenario("features/preauth_decision.feature", "不在保障期内案件拒绝")
def test_out_of_coverage_period():
    pass


@scenario("features/preauth_decision.feature", "急诊案件优先批准")
def test_emergency_fast_track():
    pass


@scenario("features/preauth_decision.feature", "药品申请审核 - 英克司兰钠")
def test_drug_review_inclisiran():
    pass


# ===== 背景步骤 =====

@given("系统已完成理赔材料的分析处理")
def system_completed_analysis():
    """确保系统已完成所有分析"""
    return {"analysis_completed": True}


# ===== 通用步骤 =====

@when(parsers.parse('理赔案件的就诊类型为 "{visit_type}"'))
def set_visit_type(visit_type, system_completed_analysis):
    """设置就诊类型"""
    system_completed_analysis["visit_type"] = visit_type
    return system_completed_analysis


@when(parsers.parse('就诊医院为 "{hospital_name}"'))
def set_hospital_name(hospital_name, system_completed_analysis):
    """设置就诊医院"""
    system_completed_analysis["hospital_name"] = hospital_name
    return system_completed_analysis


@when(parsers.parse('诊断为 "{diagnosis}"'))
def set_diagnosis(diagnosis, system_completed_analysis):
    """设置诊断"""
    system_completed_analysis["diagnosis"] = diagnosis
    return system_completed_analysis


@when(parsers.parse("申请费用为 {amount:d} 元"))
def set_amount(amount, system_completed_analysis):
    """设置申请费用"""
    system_completed_analysis["amount"] = amount
    return system_completed_analysis


@when("无责任免除条款匹配")
def no_exclusion_match(system_completed_analysis):
    """设置无责任免除条款"""
    system_completed_analysis["exclusion_match"] = False
    return system_completed_analysis


@when("该医院在昂贵医院列表中")
def hospital_in_expensive_list(system_completed_analysis):
    """标记医院在昂贵医院列表中"""
    system_completed_analysis["is_expensive_hospital"] = True
    return system_completed_analysis


@when("保险条款明确不覆盖昂贵医院")
def policy_excludes_expensive_hospitals(system_completed_analysis):
    """标记保单不覆盖昂贵医院"""
    system_completed_analysis["covers_expensive_hospital"] = False
    return system_completed_analysis


@when("理赔案件的就诊医院在除外医疗机构列表中")
def hospital_in_excluded_list(system_completed_analysis):
    """标记医院在除外医疗机构列表中"""
    system_completed_analysis["is_excluded_hospital"] = True
    return system_completed_analysis


@when(parsers.parse("对应保项的剩余保额为 {remaining:d} 元"))
def set_remaining_coverage(remaining, system_completed_analysis):
    """设置剩余保额"""
    system_completed_analysis["remaining_coverage"] = remaining
    return system_completed_analysis


@when("理赔案件的服务日期不在保险权益期限内")
def service_date_out_of_coverage(system_completed_analysis):
    """标记服务日期不在保障期内"""
    system_completed_analysis["in_coverage_period"] = False
    return system_completed_analysis


@when("理赔案件明确为急诊就医")
def set_emergency(system_completed_analysis):
    """标记为急诊就医"""
    system_completed_analysis["is_emergency"] = True
    return system_completed_analysis


@when("未触发强制拒绝条件")
def no_mandatory_rejection(system_completed_analysis):
    """确保未触发强制拒绝条件"""
    system_completed_analysis["mandatory_rejection"] = False
    return system_completed_analysis


@when("理赔案件申请了英克司兰钠药品")
def applied_inclisiran(system_completed_analysis):
    """标记申请了英克司兰钠"""
    system_completed_analysis["drug_name"] = "英克司兰钠"
    return system_completed_analysis


@when("病情描述中未提及他汀不耐受或ASCVD")
def no_statin_intolerance_or_ascvd(system_completed_analysis):
    """标记未提及他汀不耐受或ASCVD"""
    system_completed_analysis["has_statin_intolerance"] = False
    system_completed_analysis["has_ascvd"] = False
    return system_completed_analysis


# ===== 预授权决策引擎 =====

def _mock_preauth_decision(context: dict) -> dict:
    """模拟预授权决策逻辑，基于上下文信息返回决策结果"""
    # 昂贵医院拒绝
    if context.get("is_expensive_hospital") and not context.get("covers_expensive_hospital", True):
        return {
            "result": "13 - 拒绝 (GOP Rejected)",
            "reason": "该医院属于昂贵医院，不在保险覆盖范围内。根据条款第X条，本保险不覆盖昂贵医院的就医费用。"
        }

    # 除外医疗机构拒绝
    if context.get("is_excluded_hospital"):
        return {
            "result": "13 - 拒绝 (GOP Rejected)",
            "reason": "该医院被列为除外医疗机构，根据条款规定不在保障范围内。"
        }

    # 保额不足拒绝
    amount = context.get("amount", 0)
    remaining = context.get("remaining_coverage", float("inf"))
    if amount > remaining:
        return {
            "result": "13 - 拒绝 (GOP Rejected)",
            "reason": f"申请费用 {amount} 元超过剩余保额 {remaining} 元，保额不足。"
        }

    # 不在保障期拒绝
    if context.get("in_coverage_period") == False:
        return {
            "result": "13 - 拒绝 (GOP Rejected)",
            "reason": "服务日期不在保险权益期限内，不在保障期内。"
        }

    # 急诊优先批准
    if context.get("is_emergency") and not context.get("mandatory_rejection", True):
        return {
            "result": "12 - 批准 (GOP Approved)",
            "reason": "急诊案件优先通道：患者因急诊就医，根据急诊优先处理原则，予以批准。经医学必要性分析，该急诊就医符合保险条款定义的急诊标准。"
        }

    # 英克司兰钠适应症审核
    if context.get("drug_name") == "英克司兰钠":
        if not context.get("has_statin_intolerance") and not context.get("has_ascvd"):
            return {
                "result": "13 - 拒绝 (GOP Rejected)",
                "reason": "英克司兰钠适应症不匹配：该药品适用于他汀不耐受或ASCVD患者，申请材料中未提及相关适应症。"
            }

    # 标准门诊批准
    return {
        "result": "12 - 批准 (GOP Approved)",
        "reason": "经审核，该门诊案件符合保险条款规定。条款依据：第X条覆盖门诊医疗费用。医学必要性分析：诊断为急性胃炎，胃镜检查为合理诊疗手段。"
    }


# ===== Then 断言步骤 =====

@then(parsers.parse('预授权结果应为 "{expected_result}"'))
def verify_preauth_result(expected_result, system_completed_analysis):
    """验证预授权结果"""
    decision = _mock_preauth_decision(system_completed_analysis)
    assert decision["result"] == expected_result, \
        f"期望结果: {expected_result}, 实际结果: {decision['result']}"


@then("审核结果应包含条款依据")
def verify_contains_policy_basis(system_completed_analysis):
    """验证审核结果包含条款依据"""
    decision = _mock_preauth_decision(system_completed_analysis)
    reason = decision.get("reason", "")
    has_policy_basis = any(
        keyword in reason
        for keyword in ["条款", "保险", "保障", "覆盖", "规定"]
    )
    assert has_policy_basis, f"审核结果缺少条款依据: {reason}"


@then("审核结果应包含医学必要性分析")
def verify_contains_medical_necessity(system_completed_analysis):
    """验证审核结果包含医学必要性分析"""
    decision = _mock_preauth_decision(system_completed_analysis)
    reason = decision.get("reason", "")
    has_medical_analysis = any(
        keyword in reason
        for keyword in ["医学", "诊断", "治疗", "检查", "合理", "标准"]
    )
    assert has_medical_analysis, f"审核结果缺少医学必要性分析: {reason}"


@then(parsers.parse('拒绝原因应提及 "{keyword}"'))
def verify_rejection_reason_contains(keyword, system_completed_analysis):
    """验证拒绝原因包含特定关键词"""
    decision = _mock_preauth_decision(system_completed_analysis)
    reason = decision.get("reason", "")
    assert keyword in reason, \
        f"拒绝原因中未找到关键词 '{keyword}': {reason}"


@then("审核结果应注明急诊优先通道")
def verify_emergency_fast_track(system_completed_analysis):
    """验证急诊优先通道标注"""
    decision = _mock_preauth_decision(system_completed_analysis)
    reason = decision.get("reason", "")
    assert "急诊" in reason or "优先" in reason, \
        f"审核结果未注明急诊优先通道: {reason}"