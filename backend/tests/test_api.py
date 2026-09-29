"""API 全流程测试：建企业/产品 → 上传法规 → 发起分析 → 查询结果与动作。"""

import io

import pytest
from fastapi.testclient import TestClient

from app.main import app

#: 测试用法规文本（含健康数据相关条款，保证 mock 分析可命中）
_REGULATION_TEXT = """测试数据保护条例

第一条 目的
为规范个人数据处理活动，保护个人数据权益，制定本条例。

第九条 特殊类别个人数据
[DEMO SUMMARY] 原则上禁止处理健康数据、生物识别数据等特殊类别个人数据；取得数据主体明示同意等法定例外情形除外。

第四十四条 跨境传输
[DEMO SUMMARY] 向第三国或国际组织传输个人数据，仅在充分性认定或适当保障措施等条件满足时方可进行。
"""


@pytest.fixture(scope="module")
def client():
    """TestClient 上下文管理器：触发 lifespan（建表 + 种子数据 + 向量索引）。"""
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["db"] == "sqlite"
        assert data["llm_provider"] == "mock"
        assert data["embedding_provider"] == "local"


class TestComplianceTools:
    def test_questionnaire_and_assessment(self, client: TestClient):
        questionnaire = client.get("/api/compliance/questionnaire")
        assert questionnaire.status_code == 200
        assert len(questionnaire.json()["modules"]) == 6
        assert len(questionnaire.json()["questions"]) >= 20

        product = client.get("/api/products").json()[0]
        response = client.post(
            "/api/compliance/assessments",
            json={
                "product_id": product["id"],
                "answers": {
                    "collect_personal": True,
                    "privacy_policy": False,
                    "encrypt_storage": False,
                    "access_control": False,
                    "breach_plan": False,
                    "retention_defined": False,
                },
            },
        )
        assert response.status_code == 201, response.text
        result = response.json()
        assert result["score"] < 100
        assert result["hits"]
        assert "告知与同意" in result["dimension_scores"]
        assert result["report_markdown"].startswith("#")

        listing = client.get("/api/compliance/assessments")
        assert listing.status_code == 200
        assert any(item["id"] == result["id"] for item in listing.json())

    def test_policy_and_document_tools(self, client: TestClient):
        checked = client.post("/api/compliance/policy/check", json={"text": "我们收集手机号，您可以注销账号。"})
        assert checked.status_code == 200
        assert 0 < checked.json()["covered"] < checked.json()["total"]

        generated = client.post(
            "/api/compliance/policy/generate",
            json={
                "answers": {"collect_personal": True, "privacy_policy": True},
                "product_name": "测试产品",
                "company_name": "测试公司",
                "contact": "privacy@example.com",
            },
        )
        assert generated.status_code == 200
        assert "测试产品" in generated.json()["text"]

        analyzed = client.post(
            "/api/compliance/documents/analyze",
            json={"text": "产品收集手机号，使用 HTTPS 加密，并面向欧盟用户。"},
        )
        assert analyzed.status_code == 200
        assert analyzed.json()["suggestions"]["collect_personal"] is True
        assert analyzed.json()["suggestions"]["encrypt_storage"] is True

        uploaded = client.post(
            "/api/compliance/documents/upload",
            files={"file": ("product.md", "产品收集手机号并提供注销入口。".encode(), "text/markdown")},
        )
        assert uploaded.status_code == 200
        assert uploaded.json()["suggestions"]["right_delete"] is True


class TestCompanyProductCrud:
    def test_company_crud(self, client: TestClient):
        # 创建
        resp = client.post(
            "/api/companies",
            json={
                "name": "测试出海企业",
                "industry": "消费电子",
                "country": "中国",
                "target_markets": ["Germany"],
                "business_model": "B2C 硬件销售",
            },
        )
        assert resp.status_code == 201, resp.text
        company = resp.json()
        assert company["id"] > 0
        assert company["target_markets"] == ["Germany"]

        # 详情
        resp = client.get(f"/api/companies/{company['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "测试出海企业"

        # 更新（部分字段）
        resp = client.put(f"/api/companies/{company['id']}", json={"industry": "智能穿戴"})
        assert resp.status_code == 200
        assert resp.json()["industry"] == "智能穿戴"
        assert resp.json()["name"] == "测试出海企业"  # 未传字段保持不变

        # 列表
        resp = client.get("/api/companies")
        assert resp.status_code == 200
        assert any(c["id"] == company["id"] for c in resp.json())

        # 404 友好报错
        resp = client.get("/api/companies/99999")
        assert resp.status_code == 404
        assert "企业不存在" in resp.json()["detail"]

    def test_product_crud_and_filter(self, client: TestClient):
        company = client.post("/api/companies", json={"name": "产品测试企业"}).json()
        resp = client.post(
            "/api/products",
            json={
                "company_id": company["id"],
                "name": "测试手表",
                "category": "智能穿戴",
                "collects_health_data": True,
                "collects_personal_data": True,
            },
        )
        assert resp.status_code == 201, resp.text
        product = resp.json()
        assert product["collects_health_data"] is True
        assert product["collects_location_data"] is False  # 默认值

        # ?company_id= 过滤
        resp = client.get("/api/products", params={"company_id": company["id"]})
        assert resp.status_code == 200
        assert [p["id"] for p in resp.json()] == [product["id"]]

        # 所属企业不存在 → 404
        resp = client.post("/api/products", json={"company_id": 99999, "name": "孤儿产品"})
        assert resp.status_code == 404

        # 更新
        resp = client.put(f"/api/products/{product['id']}", json={"has_privacy_policy": True})
        assert resp.status_code == 200
        assert resp.json()["has_privacy_policy"] is True


class TestDeveloperWorkflow:
    def test_scan_fix_and_policy_mismatch(self, client: TestClient):
        company = client.post("/api/companies", json={"name": "独立开发者"}).json()
        product = client.post(
            "/api/products",
            json={
                "company_id": company["id"],
                "name": "定位工具",
                "category": "App",
                "collects_location_data": True,
                "uses_third_party_sdk": True,
                "third_party_sdks": ["Firebase Analytics"],
            },
        ).json()
        scanned = client.post(
            "/api/developer/sdk-scan",
            json={
                "product_id": product["id"],
                "filename": "AndroidManifest.xml",
                "content": "android.permission.ACCESS_FINE_LOCATION Firebase Analytics",
            },
        )
        assert scanned.status_code == 201, scanned.text
        assert len(scanned.json()["findings"]) == 2

        checked = client.post(
            "/api/compliance/policy/check",
            json={"product_id": product["id"], "text": "我们收集账号信息并提供删除方式。"},
        )
        assert checked.status_code == 200, checked.text
        assert {item["key"] for item in checked.json()["mismatches"]} == {"location", "sdk"}

        issues = client.get("/api/developer/issues", params={"product_id": product["id"]}).json()
        assert issues
        updated = client.patch(f"/api/developer/issues/{issues[0]['id']}", json={"status": "resolved"})
        assert updated.status_code == 200
        assert updated.json()["status"] == "resolved"


class TestRegulations:
    def test_seed_regulations_listed(self, client: TestClient):
        """种子法规应已入库且带条款数。"""
        resp = client.get("/api/regulations")
        assert resp.status_code == 200
        regs = resp.json()
        names = {r["name"] for r in regs}
        assert "GDPR（通用数据保护条例）" in names
        assert "个人信息保护法" in names
        assert "数据安全法" in names
        for reg in regs:
            assert reg["article_count"] > 0

    def test_regulation_detail_with_articles(self, client: TestClient):
        regs = client.get("/api/regulations").json()
        gdpr = next(r for r in regs if "GDPR" in r["name"])
        resp = client.get(f"/api/regulations/{gdpr['id']}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["articles"], "详情应含条款数组"
        numbers = {a["article_number"] for a in detail["articles"]}
        assert "第9条" in numbers and "第44条" in numbers
        # 种子内容带 DEMO 标注
        assert "[DEMO SUMMARY]" in detail["articles"][0]["content"]

    def test_upload_regulation_text(self, client: TestClient):
        """上传 txt 法规 → 解析 → 切分 → 入库。"""
        resp = client.post(
            "/api/regulations/upload",
            files={"file": ("test_reg.txt", io.BytesIO(_REGULATION_TEXT.encode("utf-8")), "text/plain")},
            data={
                "name": "测试数据保护条例",
                "jurisdiction": "EU",
                "description": "测试用法规",
                "source_url": "https://example.com/reg",
            },
        )
        assert resp.status_code == 201, resp.text
        result = resp.json()
        assert result["articles_ingested"] == 3  # 第一/九/四十四条

        detail = client.get(f"/api/regulations/{result['id']}").json()
        assert {a["article_number"] for a in detail["articles"]} == {"第一条", "第九条", "第四十四条"}

    def test_upload_rejects_bad_file(self, client: TestClient):
        resp = client.post(
            "/api/regulations/upload",
            files={"file": ("bad.exe", io.BytesIO(b"binary"), "application/octet-stream")},
            data={"name": "坏文件"},
        )
        assert resp.status_code == 400

        # 无条款结构 → 400 友好报错
        resp = client.post(
            "/api/regulations/upload",
            files={"file": ("plain.txt", io.BytesIO("没有条款结构的文本".encode("utf-8")), "text/plain")},
            data={"name": "无结构"},
        )
        assert resp.status_code == 400
        assert "条款" in resp.json()["detail"]


class TestAnalysisFlow:
    """全流程：建企业/产品 → 上传法规 → POST 分析 → GET 详情/列表 → GET 动作。"""

    def test_full_flow(self, client: TestClient):
        # 1. 建企业（收集健康数据、跨境传输、无隐私政策 → 高风险场景）
        company = client.post(
            "/api/companies",
            json={"name": "分析测试企业", "target_markets": ["Germany", "France"]},
        ).json()
        product = client.post(
            "/api/products",
            json={
                "company_id": company["id"],
                "name": "分析测试手表",
                "category": "智能穿戴",
                "collects_personal_data": True,
                "collects_health_data": True,
                "cross_border_data_transfer": True,
                "third_party_data_sharing": True,
                "has_privacy_policy": False,
            },
        ).json()

        # 2. 上传法规（第九条健康数据条款可供证据引用）
        upload = client.post(
            "/api/regulations/upload",
            files={"file": ("flow_reg.txt", io.BytesIO(_REGULATION_TEXT.encode("utf-8")), "text/plain")},
            data={"name": "流程测试条例", "jurisdiction": "EU"},
        ).json()

        # 3. 发起分析（指定刚上传的法规）
        resp = client.post(
            "/api/analysis",
            json={
                "company_id": company["id"],
                "product_id": product["id"],
                "regulation_id": upload["id"],
                "query": "分析该产品在该法规下的合规影响",
            },
        )
        assert resp.status_code == 201, resp.text
        result = resp.json()

        assert result["status"] == "completed"
        assert result["llm_mode"] == "mock"
        assert result["relevant"] is True
        assert result["risk_level"] in {"high", "medium"}
        assert result["summary"]
        assert result["confidence"] in {"high", "medium", "low"}
        assert result["affected_products"] == ["分析测试手表"]

        # 证据：引用真实条款、带 verified 标记
        assert result["evidence"], "应返回证据"
        for item in result["evidence"]:
            assert item["regulation"] and item["article"]
            assert item["content"]
            assert item["verified"] is True

        # 动作：非空且结构完整
        assert result["actions"], "应生成整改动作"
        for action in result["actions"]:
            assert action["title"] and action["priority"] in {"low", "medium", "high"}
            assert action["run_id"] == result["id"]

        # 4. GET 详情与 POST 返回一致
        detail = client.get(f"/api/analysis/{result['id']}")
        assert detail.status_code == 200
        assert detail.json()["id"] == result["id"]
        assert detail.json()["summary"] == result["summary"]

        # 5. 列表包含本次运行（含企业/产品名称）
        listing = client.get("/api/analysis")
        assert listing.status_code == 200
        item = next(i for i in listing.json() if i["id"] == result["id"])
        assert item["company_name"] == "分析测试企业"
        assert item["product_name"] == "分析测试手表"
        assert item["risk_level"] == result["risk_level"]

        # 6. GET /api/actions 包含本次动作
        actions = client.get("/api/actions")
        assert actions.status_code == 200
        run_actions = [a for a in actions.json() if a["run_id"] == result["id"]]
        assert len(run_actions) == len(result["actions"])

    def test_analysis_404s(self, client: TestClient):
        resp = client.post("/api/analysis", json={"company_id": 99999, "product_id": 1, "query": "x"})
        assert resp.status_code == 404
        assert "企业不存在" in resp.json()["detail"]

        company = client.post("/api/companies", json={"name": "404测试企业"}).json()
        resp = client.post(
            "/api/analysis", json={"company_id": company["id"], "product_id": 99999, "query": "x"}
        )
        assert resp.status_code == 404
        assert "产品不存在" in resp.json()["detail"]

        resp = client.get("/api/analysis/99999")
        assert resp.status_code == 404
        assert "分析记录不存在" in resp.json()["detail"]
