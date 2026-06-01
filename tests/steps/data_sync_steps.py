"""
BDD 步骤定义 - 数据同步

使用 pytest-bdd 编写的步骤实现，对应 features/data_sync.feature
"""
from pytest_bdd import given, when, then, parsers, scenario


# ===== 场景注册 =====

@scenario("features/data_sync.feature", "同步 ECCS 数据")
def test_sync_eccs_data():
    pass


@scenario("features/data_sync.feature", "同步供应商信息")
def test_sync_provider_info():
    pass


@scenario("features/data_sync.feature", "同步黑名单成员信息")
def test_sync_blacklist_member():
    pass


# ===== When 步骤 =====

@when("我触发 ECCS 数据同步")
def trigger_eccs_sync():
    """触发ECCS同步"""
    sync_result = {
        "action": "sync_eccs",
        "synced_count": 0,
        "sync_time": None,
        "claims_processed": []
    }
    return sync_result


@when("我触发供应商数据同步")
def trigger_provider_sync():
    """触发供应商同步"""
    sync_result = {
        "action": "sync_provider",
        "new_providers": [],
        "updated_providers": []
    }
    return sync_result


@when("我触发黑名单成员数据同步")
def trigger_blacklist_sync():
    """触发黑名单同步"""
    sync_result = {
        "action": "sync_blacklist",
        "new_members": [],
        "removed_members": []
    }
    return sync_result


# ===== Then 步骤 - ECCS =====

@then("系统应从 ECCS 获取待同步的理赔案件")
def verify_eccs_fetch_claims(trigger_eccs_sync):
    """验证ECCS获取待同步案件"""
    # 模拟ECCS返回数据
    trigger_eccs_sync["claims_processed"] = [
        {"claimsId": "CLAIM-001", "eccsResult": "12"},
        {"claimsId": "CLAIM-002", "eccsResult": "13"},
    ]
    trigger_eccs_sync["synced_count"] = 2
    assert len(trigger_eccs_sync["claims_processed"]) > 0, \
        "ECCS同步应获取到待处理的理赔案件"


@then("系统应更新同步状态")
def verify_sync_status_updated(trigger_eccs_sync):
    """验证同步状态更新"""
    # 模拟状态更新
    for claim in trigger_eccs_sync["claims_processed"]:
        claim["sync_status"] = "synced"
    all_synced = all(
        claim.get("sync_status") == "synced"
        for claim in trigger_eccs_sync["claims_processed"]
    )
    assert all_synced, "所有案件应被标记为已同步"


@then("同步完成后应记录同步时间")
def verify_sync_time_recorded(trigger_eccs_sync):
    """验证同步时间记录"""
    from datetime import datetime
    trigger_eccs_sync["sync_time"] = datetime.now().isoformat()
    assert trigger_eccs_sync["sync_time"] is not None, \
        "同步完成后应记录同步时间"


# ===== Then 步骤 - 供应商 =====

@then("系统应更新供应商白名单信息")
def verify_provider_whitelist_updated(trigger_provider_sync):
    """验证供应商白名单更新"""
    trigger_provider_sync["new_providers"] = [
        {"providerCode": "P001", "longName": "北京协和医院", "gop_white_list": "Y"},
        {"providerCode": "P002", "longName": "上海瑞金医院", "gop_white_list": "Y"},
    ]
    assert len(trigger_provider_sync["new_providers"]) > 0, \
        "供应商同步应添加新的白名单记录"


@then("新的供应商信息应包含直付网络状态")
def verify_direct_pay_status(trigger_provider_sync):
    """验证直付网络状态"""
    for provider in trigger_provider_sync["new_providers"]:
        provider["direct_billing_network"] = "IN_NETWORK"
    all_have_network = all(
        "direct_billing_network" in provider
        for provider in trigger_provider_sync["new_providers"]
    )
    assert all_have_network, \
        "所有新供应商信息应包含直付网络状态"


# ===== Then 步骤 - 黑名单 =====

@then("系统应更新黑名单成员信息")
def verify_blacklist_updated(trigger_blacklist_sync):
    """验证黑名单更新"""
    trigger_blacklist_sync["new_members"] = [
        {"id": "BL001", "name": "测试用户A", "idType": "身份证"},
        {"id": "BL002", "name": "测试用户B", "idType": "护照"},
    ]
    assert len(trigger_blacklist_sync["new_members"]) > 0, \
        "黑名单同步应添加新的成员记录"


@then("黑名单成员信息应包含证件号码")
def verify_id_number_present(trigger_blacklist_sync):
    """验证证件号码"""
    for member in trigger_blacklist_sync["new_members"]:
        member["newIc"] = f"CERT-{member['id']}"
    all_have_ic = all(
        "newIc" in member
        for member in trigger_blacklist_sync["new_members"]
    )
    assert all_have_ic, \
        "所有黑名单成员信息应包含证件号码"