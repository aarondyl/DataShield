"""Structured LLM fallback for applicability cases unresolved by deterministic rules."""

from __future__ import annotations

import json

from app.core.llm import get_llm_client
from app.tenant.agent.nodes.context_check import (
    build_product_applicability_context,
    build_requirement_applicability_context,
)
from app.tenant.agent.state import TenantAgentState
from app.tenant.applicability.schemas import (
    ApplicabilityResult,
    DecisionSource,
    MissingContextItem,
)

PROMPT_VERSION = "tenant-applicability-v1"


def _fallback(requirement_id: int, reason: str) -> ApplicabilityResult:
    item = MissingContextItem(
        requirement_id=requirement_id,
        field_path="applicability_review",
        question="请人工确认该 Requirement 是否适用于当前产品。",
        reason=reason,
    )
    return ApplicabilityResult(
        requirement_id=requirement_id,
        applies=None,
        confidence=0,
        missing_context=[item],
        reasoning_summary="自动适用性判断未能产生有效的结构化结果，需要人工确认。",
        decision_source=DecisionSource.INSUFFICIENT_CONTEXT,
    )


def _llm_result(requirement, product, evidence) -> ApplicabilityResult:
    requirement_input = build_requirement_applicability_context(requirement)
    product_input = build_product_applicability_context(product)
    relevant_fields = {
        "markets", "subject_types", *requirement_input.required_fields,
        *(item.field_path for item in requirement_input.conditions),
        *(item.field_path for item in requirement_input.exceptions),
    }
    facts = {
        key: value.model_dump(mode="json")
        for key, value in product_input.facts.items()
        if key in relevant_fields or any(key.startswith(f"{root}.") for root in relevant_fields)
    }
    legal = [item.model_dump(mode="json") for item in evidence if requirement.id in item.requirement_ids]
    payload = {
        "requirement": requirement.model_dump(mode="json"),
        "product_facts": facts,
        "legal_evidence": legal,
    }
    system_prompt = (
        "Decide whether one legal requirement applies to one product. Be conservative; "
        "retrieval alone never proves applicability.\n"
        "Return exactly one JSON object with these fields and no others:\n"
        '- "applies": true, false, or null\n'
        '- "confidence": number between 0 and 1\n'
        '- "matched_facts": array of {"field": string, "value": any, "fact_ids": array of integers, '
        '"evidence": array} (may be empty)\n'
        '- "missing_context": array of {"field_path": string, "question": string, "reason": string} '
        "(may be empty)\n"
        '- "reasoning_summary": short audit summary string, not hidden reasoning'
    )
    client = get_llm_client()
    raw = client.chat_json(
        system_prompt,
        json.dumps(payload, ensure_ascii=False),
        context={"task": "tenant_applicability", **payload},
    )
    raw.update({"requirement_id": requirement.id, "decision_source": DecisionSource.LLM.value})
    return ApplicabilityResult.model_validate(raw)


def analyze_applicability(state: TenantAgentState) -> dict:
    product = state.get("product_context")
    if product is None:
        raise RuntimeError("Product context is unavailable")
    ready = set(state.get("ready_requirement_ids", []))
    results = list(state.get("applicability_results", []))
    missing = list(state.get("missing_context", []))
    for requirement in state.get("requirements", []):
        if requirement.id not in ready:
            continue
        try:
            result = _llm_result(requirement, product, state.get("legal_evidence", []))
        except Exception as exc:
            result = _fallback(requirement.id, f"结构化适用性判断失败：{type(exc).__name__}")
        results.append(result)
        missing.extend(result.missing_context)
    return {"applicability_results": results, "missing_context": missing}
