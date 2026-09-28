"""Agent 工作流测试：mock LLM 全图运行（SmartWatch X1 场景）+ 证据校验重试逻辑单测。"""

import pytest
from sqlalchemy import select

from app.agents.evidence_agent import evidence_verification
from app.agents.graph import build_graph, route_after_evidence
from app.db.session import SessionLocal, init_db
from app.models import AnalysisRun, Company, ComplianceAction, ImpactResult, Product
from app.services.seed import seed_if_empty


@pytest.fixture(scope="module", autouse=True)
def seeded_db():
    """模块级夹具：建表 + 写入种子数据（ABC Technology / SmartWatch X1 / 预置法规）。"""
    init_db()
    with SessionLocal() as db:
        seed_if_empty(db)
    yield


def _seed_ids() -> tuple[int, int]:
    """返回种子企业与产品的 ID。"""
    with SessionLocal() as db:
        company = db.scalar(select(Company).where(Company.name == "ABC Technology"))
        product = db.scalar(select(Product).where(Product.name == "SmartWatch X1"))
        assert company is not None and product is not None
        return company.id, product.id


def _run_full_graph() -> dict:
    """以种子企业/产品跑完整工作流，返回最终状态。"""
    company_id, product_id = _seed_ids()
    with SessionLocal() as db:
        run = AnalysisRun(
            company_id=company_id,
            product_id=product_id,
            regulation_id=None,
            query="请分析 SmartWatch X1 进入欧盟市场的法规影响与合规要求",
            status="running",
            llm_mode="mock",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

    final_state = build_graph().invoke(
        {
            "run_id": run_id,
            "company_id": company_id,
            "product_id": product_id,
            "regulation_id": None,
            "query": "请分析 SmartWatch X1 进入欧盟市场的法规影响与合规要求",
            "retrieved_chunks": [],
            "impact_result": None,
            "evidence_result": None,
            "actions": [],
            "retry_count": 0,
        }
    )
    final_state["_run_id"] = run_id
    return final_state


class TestFullGraph:
    """mock LLM 跑完整 graph（SmartWatch X1 场景）。"""

    @classmethod
    def setup_class(cls):
        cls.state = _run_full_graph()

    def test_retrieved_chunks_non_empty(self):
        chunks = self.state["retrieved_chunks"]
        assert chunks, "应检索到相关法规条款"
        # 必备字段齐全
        for key in ("chunk_id", "regulation_name", "article_number", "content", "source_url", "jurisdiction"):
            assert key in chunks[0]

    def test_impact_result_structured(self):
        impact = self.state["impact_result"]
        assert impact is not None
        # SmartWatch X1 收集健康数据且检索到 GDPR 第9条 → 相关 + 高风险
        assert impact["relevant"] is True
        assert impact["risk_level"] == "high"
        assert impact["confidence"] in {"high", "medium"}
        assert "SmartWatch X1" in impact["affected_products"]
        assert impact["affected_areas"], "应给出受影响业务领域"
        assert impact["summary"]
        assert impact["reasoning_summary"]

    def test_evidence_references_real_chunks(self):
        """证据的 chunk_id 必须来自实际检索到的条款（严禁编造）。"""
        chunk_ids = {str(c["chunk_id"]) for c in self.state["retrieved_chunks"]}
        evidence = self.state["impact_result"]["evidence"]
        assert evidence, "高风险场景应给出证据"
        for item in evidence:
            assert str(item["chunk_id"]) in chunk_ids

    def test_evidence_verified(self):
        evidence_result = self.state["evidence_result"]
        assert evidence_result["verified"] is True
        assert evidence_result["unsupported_claims"] == []
        assert len(evidence_result["verified_evidence"]) >= 1
        # 已验证证据携带内容与来源，供前端展示
        first = evidence_result["verified_evidence"][0]
        assert first["content"] and first["verified"] is True

    def test_actions_non_empty_and_structured(self):
        actions = self.state["actions"]
        assert actions, "应生成整改动作"
        for action in actions:
            assert action["title"]
            assert action["priority"] in {"low", "medium", "high"}
            assert action["department"] in {
                "Legal", "Product", "Engineering", "Security", "Operations", "Supply Chain", "Management",
            }
        # 健康数据 + 无隐私政策 + 跨境传输 → 至少应覆盖这些高优先级主题中的两个
        titles = " ".join(a["title"] for a in actions)
        assert ("特殊类别" in titles) or ("健康" in titles)
        assert ("隐私政策" in titles) or ("跨境" in titles)

    def test_result_persisted(self):
        """save_result 节点应把结果与动作落库。"""
        run_id = self.state["_run_id"]
        with SessionLocal() as db:
            run = db.get(AnalysisRun, run_id)
            assert run.status == "completed"
            assert run.llm_mode == "mock"
            result = db.scalar(select(ImpactResult).where(ImpactResult.run_id == run_id))
            assert result is not None and result.relevant is True
            actions = db.scalars(
                select(ComplianceAction).where(ComplianceAction.run_id == run_id)
            ).all()
            assert len(actions) == len(self.state["actions"])


class TestEvidenceRetry:
    """证据校验失败 → 重试逻辑单测（不跑全图）。"""

    _CHUNKS = [
        {
            "chunk_id": 1,
            "regulation_name": "GDPR",
            "article_number": "第9条",
            "title": "特殊类别个人数据的处理",
            "content": "第9条 特殊类别个人数据的处理\n原则上禁止处理健康数据等特殊类别个人数据。",
            "source_url": "https://example.com/gdpr",
            "jurisdiction": "EU",
            "topic": "特殊类别数据",
        }
    ]

    def _state_with_fake_evidence(self, retry_count: int) -> dict:
        return {
            "retrieved_chunks": self._CHUNKS,
            "impact_result": {
                "relevant": True,
                "risk_level": "high",
                "evidence": [
                    {"regulation": "GDPR", "article": "第99条", "chunk_id": 999, "reason": "编造的证据"}
                ],
            },
            "retry_count": retry_count,
        }

    def test_unsupported_evidence_triggers_retry_once(self):
        # 第一次：证据编造 → 不通过、应重试、retry_count+1
        out1 = evidence_verification(self._state_with_fake_evidence(0))
        assert out1["evidence_result"]["verified"] is False
        assert out1["evidence_result"]["should_retry"] is True
        assert len(out1["evidence_result"]["unsupported_claims"]) == 1
        assert out1["retry_count"] == 1
        # 路由回 impact_analysis 重跑
        assert route_after_evidence({"evidence_result": out1["evidence_result"]}) == "impact_analysis"

        # 第二次（retry_count 已达 1）：不再重试，放行到 action_planning
        out2 = evidence_verification(self._state_with_fake_evidence(out1["retry_count"]))
        assert out2["evidence_result"]["should_retry"] is False
        assert out2["retry_count"] == 1
        assert route_after_evidence({"evidence_result": out2["evidence_result"]}) == "action_planning"

    def test_verified_evidence_passes(self):
        state = {
            "retrieved_chunks": self._CHUNKS,
            "impact_result": {
                "relevant": True,
                "risk_level": "high",
                "evidence": [{"regulation": "GDPR", "article": "第9条", "chunk_id": 1, "reason": "真实证据"}],
            },
            "retry_count": 0,
        }
        out = evidence_verification(state)
        assert out["evidence_result"]["verified"] is True
        assert out["evidence_result"]["should_retry"] is False
        assert out["retry_count"] == 0
        verified = out["evidence_result"]["verified_evidence"][0]
        assert verified["verified"] is True
        assert verified["content"] and verified["source_url"]
        assert route_after_evidence({"evidence_result": out["evidence_result"]}) == "action_planning"

    def test_relevant_without_evidence_not_verified(self):
        """判定相关但证据列表为空 → 不通过（结论缺乏证据支持）。"""
        state = {
            "retrieved_chunks": self._CHUNKS,
            "impact_result": {"relevant": True, "risk_level": "high", "evidence": []},
            "retry_count": 0,
        }
        out = evidence_verification(state)
        assert out["evidence_result"]["verified"] is False
        assert out["evidence_result"]["should_retry"] is True
