"""全局法规智能层测试：解析 / 种子入库 / Legal Search / 版本与变化 / 事件闭环。

覆盖任务书 Definition of Done：
法规入库 → 查看 Regulation / Version / Article / Requirement → 语义检索 →
模拟来源更新 → 检测变化 → 新版本 + RegulationChange → 义务更新 →
增量 embedding（旧 chunk 失效）→ 检索到最新内容 → 追溯官方来源 → regulation.change.ready。
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.regintel.adapters import BACKEND_ROOT
from app.regintel.diffing import diff_articles
from app.regintel.normalization import content_hash, normalize_text
from app.regintel.parsing import article_key, article_units, cn_number_to_int, parse_legal_text
from app.regintel.requirements import extract_requirements

_DATA_DIR = BACKEND_ROOT / "data" / "regulations"


@pytest.fixture(scope="module")
def client():
    """TestClient 上下文管理器：触发 lifespan（建表 + 种子数据 + 向量索引）。"""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# 纯函数单元测试：规范化 / 解析 / diff / 义务提取
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_hash_stable(self):
        a = normalize_text("第一条  测试\r\n\r\n\r\n第二条　测试")
        b = normalize_text("第一条 测试\n\n第二条 测试")
        assert a == b
        assert content_hash(a) == content_hash(b)

    def test_hash_differs_on_content_change(self):
        assert content_hash(normalize_text("第一条 甲")) != content_hash(normalize_text("第一条 乙"))


class TestCnNumber:
    def test_basic(self):
        assert cn_number_to_int("一") == 1
        assert cn_number_to_int("七十四") == 74
        assert cn_number_to_int("一百零三") == 103
        assert cn_number_to_int("十三") == 13

    def test_article_key(self):
        assert article_key("第十三条") == "13"
        assert article_key("第六十六条之一") == "66-1"
        assert article_key("Article 13") == "13"
        assert article_key("Article 13a") == "13a"


class TestParsing:
    def test_cn_law_structure(self):
        units = parse_legal_text((_DATA_DIR / "pipl.txt").read_text(encoding="utf-8"), "cn_law")
        articles = article_units(units)
        assert len(articles) == 74
        chapters = [u for u in units if u.unit_type == "chapter"]
        assert len(chapters) == 8  # 目录已跳过，正文八章
        assert articles[0].path == "第一章/第一条"
        assert articles[-1].unit_number == "第七十四条"

    def test_gdpr_bilingual_structure(self):
        units = parse_legal_text((_DATA_DIR / "gdpr.txt").read_text(encoding="utf-8"), "gdpr_bilingual")
        articles = article_units(units)
        assert len(articles) == 99
        assert len([u for u in units if u.unit_type == "chapter"]) == 11
        assert len([u for u in units if u.unit_type == "section"]) == 15
        art9 = next(u for u in articles if u.unit_number == "Article 9")
        assert "special categories" in art9.heading.lower()
        assert "第9条" in art9.heading
        assert art9.path.startswith("CHAPTER II/")


class TestDiff:
    def test_modified_added_removed(self):
        old = {"1": ("第一条", "原文甲"), "2": ("第二条", "原文乙"), "3": ("第三条", "原文丙")}
        new = {"1": ("第一条", "原文甲改"), "3": ("第三条", "原文丙"), "4": ("第四条", "原文丁")}
        changes = diff_articles(old, new)
        by_type = {c.change_type: c for c in changes}
        assert by_type["MODIFIED"].unit_number == "第一条"
        assert by_type["ADDED"].unit_number == "第四条"
        assert by_type["REMOVED"].unit_number == "第二条"
        assert by_type["REMOVED"].materiality == "HIGH"

    def test_renumbered(self):
        old = {"1": ("第一条", "内容完全相同的条款")}
        new = {"2": ("第二条", "内容完全相同的条款")}
        changes = diff_articles(old, new)
        assert len(changes) == 1
        assert changes[0].change_type == "RENUMBERED"
        assert changes[0].old_unit_number == "第一条"

    def test_no_change(self):
        old = {"1": ("第一条", "相同")}
        assert diff_articles(old, old) == []


class TestRequirementExtraction:
    def test_cn_obligation(self):
        items = extract_requirements("第十七条", "个人信息处理者应当主动删除个人信息；未取得个人同意的，应当立即停止处理。")
        assert items
        assert all("status" in item for item in items)
        obligations = [i for i in items if i["requirement_type"] == "obligation"]
        assert obligations and obligations[0]["subject_type"] == "个人信息处理者"

    def test_cn_prohibition(self):
        items = extract_requirements("第十条", "任何组织、个人不得非法收集、使用、加工、传输他人个人信息。")
        assert items and items[0]["requirement_type"] == "prohibition"

    def test_en_obligation(self):
        items = extract_requirements(
            "Article 13",
            "the controller shall provide the data subject with information. the processor may not subcontract.",
            language="en",
            default_subject="controller",
        )
        types = {i["requirement_type"] for i in items}
        assert "obligation" in types and "prohibition" in types

    def test_low_confidence_marked_needs_review(self):
        items = extract_requirements("第二十条", "处理者可以视情况简化相关流程。")
        assert items and items[0]["confidence"] < 0.7
        assert items[0]["status"] == "NEEDS_REVIEW"


# ---------------------------------------------------------------------------
# API 全流程测试（种子 → 检索 → 版本/证据 → 变化闭环）
# ---------------------------------------------------------------------------


class TestSeededKnowledgeBase:
    def test_regulations_with_current_version(self, client: TestClient):
        regs = client.get("/api/v1/regulations").json()
        names = {r["name"] for r in regs}
        assert {"GDPR（通用数据保护条例）", "个人信息保护法", "数据安全法"} <= names
        for reg in regs:
            assert reg["current_version_id"] is not None
            assert reg["current_version_number"] == 1
            assert reg["article_count"] > 0
            assert reg["requirement_count"] > 0
            assert reg["canonical_source_url"]

    def test_regulation_detail_and_versions(self, client: TestClient):
        regs = client.get("/api/v1/regulations").json()
        pipl = next(r for r in regs if r["name"] == "个人信息保护法")
        assert pipl["official_identifier"] == "中华人民共和国主席令第九十一号"
        assert pipl["authority"] == "全国人民代表大会常务委员会"

        versions = client.get(f"/api/v1/regulations/{pipl['id']}/versions").json()
        assert len(versions) == 1
        assert versions[0]["version_number"] == 1
        assert versions[0]["is_current"] is True
        assert versions[0]["content_hash"]

    def test_requirements_api(self, client: TestClient):
        regs = client.get("/api/v1/regulations").json()
        pipl = next(r for r in regs if r["name"] == "个人信息保护法")
        reqs = client.get("/api/v1/requirements", params={"regulation_id": pipl["id"]}).json()
        assert reqs
        first = reqs[0]
        detail = client.get(f"/api/v1/requirements/{first['id']}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["requirement_type"] in ("obligation", "prohibition", "right", "permission")
        assert 0 <= body["confidence"] <= 1

    def test_legal_unit_evidence(self, client: TestClient):
        """Evidence API：条文文本 + article/paragraph + regulation + version + 官方来源。"""
        regs = client.get("/api/v1/regulations").json()
        pipl = next(r for r in regs if r["name"] == "个人信息保护法")
        reqs = client.get("/api/v1/requirements", params={"regulation_id": pipl["id"]}).json()
        unit_id = reqs[0]["legal_unit_id"]
        resp = client.get(f"/api/v1/legal-units/{unit_id}")
        assert resp.status_code == 200
        unit = resp.json()
        assert unit["text"]
        assert unit["unit_number"].startswith("第")
        assert unit["regulation_name"] == "个人信息保护法"
        assert unit["version_number"] == 1
        assert unit["is_current_version"] is True
        assert unit["official_source_url"].startswith("https://")

    def test_legal_search(self, client: TestClient):
        resp = client.post(
            "/api/v1/legal-search",
            json={"query": "向境外提供个人信息应当具备什么条件", "jurisdictions": ["CN"], "top_k": 5},
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert results
        for item in results:
            assert item["chunk_id"] > 0
            assert item["source_url"]
            assert item["similarity_score"] is not None
        # 跨境条款（第三十八条）应被命中
        assert any(r["article"] == "第三十八条" for r in results)

    def test_legal_search_regulation_filter(self, client: TestClient):
        regs = client.get("/api/v1/regulations").json()
        gdpr = next(r for r in regs if "GDPR" in r["name"])
        resp = client.post(
            "/api/v1/legal-search",
            json={"query": "consent of the data subject", "regulation_ids": [gdpr["id"]], "top_k": 3},
        )
        results = resp.json()["results"]
        assert results and all(r["regulation_id"] == gdpr["id"] for r in results)


class TestChangeDetectionFlow:
    """人工模拟一次 source 更新 → 完整变化闭环（任务书 DoD 第 8-17 项）。"""

    def test_full_change_flow(self, client: TestClient):
        sources = client.get("/api/v1/sources").json()
        pipl_source = next(s for s in sources if s["fetch_url"].endswith("pipl.txt"))

        live_file = BACKEND_ROOT / pipl_source["fetch_url"]
        original = live_file.read_text(encoding="utf-8")
        fixture = (BACKEND_ROOT / "data" / "fixtures" / "pipl_update.txt").read_text(encoding="utf-8")
        assert original != fixture
        try:
            # 8. 人工模拟 source 更新
            live_file.write_text(fixture, encoding="utf-8")

            # 9-11. 触发流水线：检测到 change → 新 RegulationVersion → RegulationChange
            resp = client.post(f"/api/v1/sources/{pipl_source['id']}/ingest")
            assert resp.status_code == 200, resp.text
            run = resp.json()
            assert run["status"] == "COMPLETED"
            assert run["changes_count"] == 3  # 第十三条修改 + 第十六条删除 + 第六十六条之一新增
            assert run["event_id"] is not None

            regs = client.get("/api/v1/regulations").json()
            pipl = next(r for r in regs if r["name"] == "个人信息保护法")
            versions = client.get(f"/api/v1/regulations/{pipl['id']}/versions").json()
            assert [v["version_number"] for v in versions] == [1, 2]
            assert versions[0]["is_current"] is False  # 旧版本保留但不生效
            assert versions[1]["is_current"] is True

            changes = client.get("/api/v1/changes", params={"regulation_id": pipl["id"]}).json()
            by_type = {c["change_type"]: c for c in changes}
            assert set(by_type) == {"MODIFIED", "REMOVED", "ADDED"}
            assert by_type["ADDED"]["article"] == "第六十六条之一"
            assert by_type["REMOVED"]["article"] == "第十六条"
            change_detail = client.get(f"/api/v1/changes/{by_type['MODIFIED']['id']}").json()
            assert change_detail["semantic_summary"]
            assert change_detail["old_text"] != change_detail["new_text"]
            assert change_detail["source_url"]

            # 12. Requirement 更新：新条款产生新义务；被删条款义务 SUPERSEDED
            added_reqs = change_detail  # MODIFIED 变化应带新 requirement ids
            assert added_reqs["requirement_ids"]
            req = client.get(f"/api/v1/requirements/{added_reqs['requirement_ids'][0]}").json()
            assert req["version_id"] == versions[1]["id"]

            # 15. /legal-search 能搜到最新内容（新增条款）
            search = client.post(
                "/api/v1/legal-search",
                json={"query": "人工智能生成合成内容应当显著标识", "top_k": 3},
            ).json()["results"]
            assert search and search[0]["article"] == "第六十六条之一"
            assert search[0]["version_id"] == versions[1]["id"]
            assert search[0]["requirement_ids"], "新条款应关联 requirement"

            # 修改后的第十三条可检索且为新版 chunk
            search13 = client.post(
                "/api/v1/legal-search",
                json={"query": "取得个人的明示同意", "top_k": 3},
            ).json()["results"]
            top13 = next(r for r in search13 if r["article"] == "第十三条")
            assert top13["version_id"] == versions[1]["id"]
            assert "明示同意" in top13["content"]

            # 16. 从 search result 追溯官方来源
            unit = client.get(f"/api/v1/legal-units/{search[0]['legal_unit_id']}").json()
            assert unit["official_source_url"] == pipl["canonical_source_url"]

            # 17. regulation.change.ready 事件（嵌入索引就绪后才发布）
            events = client.get("/api/v1/events").json()
            event = next(e for e in events if e["id"] == run["event_id"])
            assert event["event_type"] == "regulation.change.ready"
            payload = event["payload"]
            assert payload["regulation_id"] == pipl["id"]
            assert payload["version_id"] == versions[1]["id"]
            assert payload["materiality"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            assert payload["affected_legal_unit_ids"]
            assert payload["requirement_ids"]

            # 版本未变时再次抓取 → NO_CHANGE
            rerun = client.post(f"/api/v1/sources/{pipl_source['id']}/ingest").json()
            assert rerun["status"] == "NO_CHANGE"
        finally:
            live_file.write_text(original, encoding="utf-8")

    def test_old_chunks_inactive(self, client: TestClient):
        """14. 旧 chunk inactive：变化条款的旧 chunk 不出现在当前检索，但仍可追溯。"""
        regs = client.get("/api/v1/regulations").json()
        pipl = next(r for r in regs if r["name"] == "个人信息保护法")
        versions = client.get(f"/api/v1/regulations/{pipl['id']}/versions").json()
        v1, v2 = versions[0], versions[1]

        # 旧版（v1）的第十六条已被删除：当前检索不应命中
        current = client.post(
            "/api/v1/legal-search", json={"query": "第十六条 拒绝提供产品或者服务", "top_k": 10}
        ).json()["results"]
        assert all(r["article"] != "第十六条" or r["version_id"] != v1["id"] for r in current)

        # current_only=false 可检索历史版本（Version, never overwrite）
        history = client.post(
            "/api/v1/legal-search",
            json={
                "query": "第十六条 拒绝提供产品或者服务",
                "top_k": 10,
                "current_only": False,
            },
        ).json()["results"]
        assert any(r["article"] == "第十六条" and r["version_id"] == v1["id"] for r in history)
