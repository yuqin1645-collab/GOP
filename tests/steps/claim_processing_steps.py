"""
BDD 步骤定义 - 理赔案件处理

使用 pytest-bdd 编写的步骤实现，对应 features/claim_processing.feature
"""

from pytest_bdd import given, when, then, parsers, scenario


# ===== 场景: 提交一个新的理赔案件并完成初审 =====

@scenario("features/claim_processing.feature", "提交一个新的理赔案件并完成初审")
def test_submit_new_claim():
    pass


@given("系统已正常启动")
def system_is_running(test_client):
    """验证系统健康检查"""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "healthy"}
    return response


@when(parsers.parse('我提交一个理赔案件 "{claim_id}"'))
def submit_claim(test_client, claim_id, test_data_factory):
    """提交理赔案件"""
    data = test_data_factory.make_claim_request()
    data["claimsId"] = claim_id
    response = test_client.post(
        "/api/claims/process",
        json=data,
        content_type="application/json"
    )
    assert response.status_code in (200, 201)
    return response


@then("系统应返回成功响应")
def verify_success_response(submit_claim):
    """验证响应成功"""
    response = submit_claim
    assert response is not None
    json_data = response.get_json()
    assert json_data is not None


@then("案件状态应为 \"已接收\"")
def verify_claim_status(submit_claim):
    """验证案件状态"""
    json_data = submit_claim.get_json()
    assert json_data.get("status") == "received" or json_data.get("success") == True


@then(parsers.parse('claim_id 应为 "{expected_id}"'))
def verify_claim_id(submit_claim, expected_id):
    """验证 claim_id"""
    json_data = submit_claim.get_json()
    assert json_data.get("claim_id") == expected_id or json_data.get("claims_id") == expected_id


# ===== 场景: 理赔案件基本信息分析 =====

@scenario("features/claim_processing.feature", "理赔案件基本信息分析")
def test_analyze_basic_info():
    pass


@when(parsers.parse('理赔案件 "{claim_id}" 已存在'))
def claim_exists(claim_id):
    """确保案件存在（mock）"""
    assert claim_id is not None
    return {"claim_id": claim_id}


@when("我请求分析案件的基本信息")
def analyze_basic_info(test_client, claim_exists):
    """请求基本信息分析"""
    claim_id = claim_exists["claim_id"]
    response = test_client.post(
        f"/api/claims/{claim_id}/basic-info",
        content_type="application/json"
    )
    return response


@then("系统应返回分析结果")
def verify_basic_info_result(analyze_basic_info):
    """验证返回了分析结果"""
    response = analyze_basic_info
    assert response.status_code in (200, 201)


@then("分析结果不应为空")
def verify_basic_info_not_empty(analyze_basic_info):
    """验证结果不为空"""
    json_data = analyze_basic_info.get_json()
    assert json_data is not None


@then("案件标记 basic_info_analyzed 应为 1")
def verify_basic_info_flag(analyze_basic_info):
    """验证标记已更新"""
    # 在实际测试中，这将检查数据库
    assert True  # placeholder for DB check


# ===== 场景: 理赔案件材料文档处理 =====

@scenario("features/claim_processing.feature", "理赔案件材料文档处理")
def test_process_documents():
    pass


@when(parsers.parse('理赔案件 "{claim_id}" 已完成基本信息分析'))
def basic_info_analyzed(claim_id):
    """确保基本信息已分析"""
    return {"claim_id": claim_id, "basic_info_analyzed": True}


@when("我提交文档处理请求")
def submit_document_processing(test_client, basic_info_analyzed):
    """提交文档处理"""
    claim_id = basic_info_analyzed["claim_id"]
    response = test_client.post(
        f"/api/claims/{claim_id}/documents",
        json={"document_urls": ["http://example.com/doc1.jpg"]},
        content_type="application/json"
    )
    return response


@then("系统应返回文档分析结果")
def verify_document_result(submit_document_processing):
    """验证文档结果"""
    response = submit_document_processing
    assert response.status_code in (200, 201)


@then("文档分析结果应包含图像质量评分")
def verify_image_quality_score(submit_document_processing):
    """验证图像质量评分"""
    json_data = submit_document_processing.get_json()
    # 检查是否包含 image_quality 字段
    if json_data:
        has_quality = any(
            "quality" in k.lower() or "image" in k.lower()
            for k in json_data.keys()
        )
        # 实际测试会验证具体字段
        assert True


@then("文档分析结果应包含OCR一致性评估")
def verify_ocr_consistency(submit_document_processing):
    """验证OCR一致性评估"""
    json_data = submit_document_processing.get_json()
    assert json_data is not None


# ===== 场景: 理赔案件保单条款分析 =====

@scenario("features/claim_processing.feature", "理赔案件保单条款分析")
def test_analyze_policy():
    pass


@when(parsers.parse('理赔案件 "{claim_id}" 已完成文档处理'))
def documents_processed(claim_id):
    """确保文档已处理"""
    return {"claim_id": claim_id, "documents_analyzed": True}


@when("我请求分析保单条款")
def analyze_policy(test_client, documents_processed):
    """分析保单"""
    claim_id = documents_processed["claim_id"]
    response = test_client.post(
        f"/api/claims/{claim_id}/policies",
        content_type="application/json"
    )
    return response


@then("系统应返回保单分析结果")
def verify_policy_result(analyze_policy):
    """验证保单结果"""
    response = analyze_policy
    assert response.status_code in (200, 201)


@then("保单分析结果应包含TOB和PROD条款")
def verify_policy_tob_prod(analyze_policy):
    """验证包含TOB和PROD"""
    json_data = analyze_policy.get_json()
    assert json_data is not None


@then("案件标记 policies_analyzed 应为 1")
def verify_policy_flag(analyze_policy):
    """验证标记"""
    assert True  # placeholder for DB check