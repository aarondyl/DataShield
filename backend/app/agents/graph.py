"""LangGraph 工作流装配：load_context → retrieve → impact → evidence → (条件边) → action → save。

图结构::

    load_context
        → retrieve_regulations
        → impact_analysis
        → evidence_verification
        → 条件边：
            - verified 或不再重试 → action_planning
            - 否则（retry_count+1）→ 回到 impact_analysis（最多重试 1 次）
        → action_planning
        → save_result
        → END
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.action_agent import action_planning
from app.agents.evidence_agent import evidence_verification
from app.agents.impact_agent import impact_analysis
from app.agents.retrieval import retrieve_regulations
from app.agents.state import AgentState
from app.db.session import SessionLocal
from app.models import AnalysisRun, Company, ComplianceAction, ImpactResult, Product


def load_context(state: AgentState) -> dict[str, Any]:
    """从数据库加载企业与产品画像到 state（后续节点的分析依据）。"""
    with SessionLocal() as db:
        company = db.get(Company, state["company_id"])
        product = db.get(Product, state["product_id"])
        if company is None or product is None:
            raise ValueError("企业或产品不存在，无法加载分析上下文")
        company_dict = {
            "id": company.id,
            "name": company.name,
            "industry": company.industry,
            "country": company.country,
            "target_markets": company.target_markets or [],
            "business_model": company.business_model,
        }
        product_dict = {
            "id": product.id,
            "company_id": product.company_id,
            "name": product.name,
            "category": product.category,
            "target_markets": product.target_markets or [],
            "collects_personal_data": product.collects_personal_data,
            "collects_sensitive_data": product.collects_sensitive_data,
            "collects_health_data": product.collects_health_data,
            "collects_location_data": product.collects_location_data,
            "children_related": product.children_related,
            "third_party_data_sharing": product.third_party_data_sharing,
            "has_privacy_policy": product.has_privacy_policy,
            "cross_border_data_transfer": product.cross_border_data_transfer,
            "description": product.description,
        }
    return {"company": company_dict, "product": product_dict}


def route_after_evidence(state: AgentState) -> str:
    """evidence_verification 之后的条件路由。

    - 证据通过校验，或本次不再重试（should_retry=false，即已达重试上限）→ action_planning；
    - 否则回到 impact_analysis 重跑（retry_count 已在证据节点中 +1，最多重试 1 次）。
    """
    evidence_result = state.get("evidence_result") or {}
    if evidence_result.get("verified") or not evidence_result.get("should_retry"):
        return "action_planning"
    return "impact_analysis"


def save_result(state: AgentState) -> dict[str, Any]:
    """把运行状态、影响分析结果与整改动作落库。"""
    with SessionLocal() as db:
        run = db.get(AnalysisRun, state.get("run_id"))
        if run is None:
            return {}
        llm_mode = state.get("llm_mode")
        if llm_mode:
            run.llm_mode = llm_mode

        impact = state.get("impact_result")
        if impact is None:
            run.status = "failed"
            db.commit()
            return {}

        evidence_result = state.get("evidence_result") or {}
        # 落库的证据列表 = 已验证证据 + 未通过校验的证据（均带 verified 标记）
        evidence_items = (evidence_result.get("verified_evidence") or []) + (
            evidence_result.get("unsupported_claims") or []
        )

        db.add(
            ImpactResult(
                run_id=run.id,
                relevant=impact.get("relevant"),
                risk_level=impact.get("risk_level") or "low",
                affected_products=impact.get("affected_products") or [],
                affected_areas=impact.get("affected_areas") or [],
                summary=impact.get("summary") or "",
                reasoning_summary=impact.get("reasoning_summary") or "",
                evidence=evidence_items,
                confidence=impact.get("confidence") or "low",
            )
        )
        for action in state.get("actions") or []:
            db.add(
                ComplianceAction(
                    run_id=run.id,
                    title=action.get("title") or "未命名动作",
                    priority=action.get("priority") or "medium",
                    department=action.get("department") or "Legal",
                    description=action.get("description") or "",
                    evidence=action.get("evidence"),
                )
            )
        run.status = "completed"
        db.commit()
    return {}


def build_graph():
    """构建并编译法规影响分析工作流。"""
    builder = StateGraph(AgentState)
    builder.add_node("load_context", load_context)
    builder.add_node("retrieve_regulations", retrieve_regulations)
    builder.add_node("impact_analysis", impact_analysis)
    builder.add_node("evidence_verification", evidence_verification)
    builder.add_node("action_planning", action_planning)
    builder.add_node("save_result", save_result)

    builder.set_entry_point("load_context")
    builder.add_edge("load_context", "retrieve_regulations")
    builder.add_edge("retrieve_regulations", "impact_analysis")
    builder.add_edge("impact_analysis", "evidence_verification")
    builder.add_conditional_edges(
        "evidence_verification",
        route_after_evidence,
        {"action_planning": "action_planning", "impact_analysis": "impact_analysis"},
    )
    builder.add_edge("action_planning", "save_result")
    builder.add_edge("save_result", END)
    return builder.compile()


@lru_cache
def get_graph():
    """返回编译后的工作流单例。"""
    return build_graph()
