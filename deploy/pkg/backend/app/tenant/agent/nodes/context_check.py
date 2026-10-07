"""Build conservative applicability inputs and identify missing product facts."""

from __future__ import annotations

from typing import Any

from app.tenant.agent.state import TenantAgentState
from app.tenant.applicability.schemas import (
    ApplicabilityCondition,
    ContextFact,
    ProductApplicabilityContext,
    RequirementApplicabilityContext,
)
from app.tenant.applicability.service import deterministic_applicability_precheck
from app.tenant.context.schemas import ProductContext, ProductFactContext
from app.tenant.regulatory.schemas import RequirementContext
from app.understanding.schemas import FindingStatus


_FIELD_ALIASES = {
    "market": "markets", "jurisdiction": "markets", "markets": "markets",
    "subject": "subject_types", "subject_type": "subject_types",
    "product_type": "product_category", "product_category": "product_category",
    "target_user": "target_users", "target_users": "target_users",
    "data_type": "data_types", "data_types": "data_types",
    "ai": "ai_features", "ai_feature": "ai_features", "ai_features": "ai_features",
    "business_model": "business_model", "cross_border": "cross_border_behavior",
    "children": "children_or_minors", "minors": "children_or_minors",
    "sensitive_data": "sensitive_data", "automated_decision": "automated_decision_making",
}


def _field_for_fact(fact: ProductFactContext) -> list[str]:
    root = {
        "market_clues": "markets", "markets": "markets",
        "product_category": "product_category", "target_users": "target_users",
        "data_types": "data_types", "features": "features", "controls": "controls",
        "capabilities": "controls", "public_documents": "controls",
    }.get(fact.group, fact.group)
    fields = [root, f"{root}.{fact.name}"]
    if fact.name in {
        "ai_features", "business_model", "cross_border_behavior", "children_or_minors",
        "sensitive_data", "automated_decision_making", "subject_types",
    }:
        fields.append(fact.name)
    return fields


def _context_fact(field: str, facts: list[ProductFactContext], *, aggregate: bool) -> ContextFact:
    usable = [item for item in facts if item.status not in {FindingStatus.UNKNOWN, FindingStatus.NOT_DETECTED}]
    selected = max(facts, key=lambda item: (item.is_user_confirmed, item.source == "USER", item.confidence))
    if aggregate:
        value: Any = [item.value if item.value is not None else item.name for item in usable]
        status = FindingStatus.PRESENT if usable else selected.status
        confidence = min((item.confidence for item in usable), default=selected.confidence)
    else:
        value = selected.value
        if selected.status == FindingStatus.PRESENT and value == selected.name:
            value = True
        status = selected.status
        confidence = selected.confidence
    confirmed = bool(facts) and all(item.is_user_confirmed for item in facts)
    complete = confirmed and all(item.scan_scope.get("complete", True) for item in facts)
    return ContextFact(
        field_path=field,
        value=value,
        status=status,
        confidence=confidence,
        confirmed=confirmed,
        complete=complete,
        fact_ids=[item.fact_id for item in facts if item.fact_id is not None],
        evidence=[entry for item in facts for entry in item.evidence],
    )


def build_product_applicability_context(product: ProductContext) -> ProductApplicabilityContext:
    indexed: dict[str, list[ProductFactContext]] = {}
    for fact in product.facts:
        for field in _field_for_fact(fact):
            indexed.setdefault(field, []).append(fact)
    views = {
        "markets": product.markets,
        "product_category": product.product_categories,
        "target_users": product.target_users,
        "data_types": product.data_types,
        "features": product.features,
        "vendors": product.vendors,
        "controls": product.controls,
    }
    for field, facts in views.items():
        if facts:
            indexed[field] = facts
    return ProductApplicabilityContext(facts={
        field: _context_fact(field, facts, aggregate=("." not in field))
        for field, facts in indexed.items() if facts
    })


def _condition(item: Any) -> list[ApplicabilityCondition]:
    if not isinstance(item, dict):
        return []
    if item.get("field_path"):
        return [ApplicabilityCondition(
            field_path=str(item["field_path"]),
            operator=item.get("operator", "EQUALS"),
            value=item.get("value"),
            question=item.get("question"),
        )]
    result = []
    for key, value in item.items():
        field = _FIELD_ALIASES.get(str(key), str(key))
        operator = ("CONTAINS_ANY" if field in {
            "markets", "subject_types", "product_category", "target_users", "data_types"
        } or isinstance(value, list) else "EQUALS")
        result.append(ApplicabilityCondition(
            field_path=field,
            operator=operator,
            value=([value] if operator == "CONTAINS_ANY" and not isinstance(value, list) else value),
        ))
    return result


def build_requirement_applicability_context(
    requirement: RequirementContext,
) -> RequirementApplicabilityContext:
    text = " ".join((requirement.object_type, requirement.action_type, requirement.summary)).casefold()
    required_fields: list[str] = []
    if any(word in text for word in ("biometric", "生物识别")):
        required_fields.append("data_types.biometric")
    elif any(word in text for word in ("personal data", "personal information", "个人数据", "个人信息")):
        required_fields.append("data_types")
    if any(word in text for word in ("artificial intelligence", "ai system", "automated decision", "人工智能", "自动化决策")):
        required_fields.append("ai_features")
    if any(word in text for word in ("child", "minor", "儿童", "未成年人")):
        required_fields.append("children_or_minors")
    conditions = [condition for item in requirement.conditions for condition in _condition(item)]
    exceptions = [condition for item in requirement.exceptions for condition in _condition(item)]
    return RequirementApplicabilityContext(
        requirement_id=requirement.id,
        jurisdiction=requirement.jurisdiction or None,
        subject_type=requirement.subject_type or None,
        conditions=conditions,
        exceptions=exceptions,
        required_fields=list(dict.fromkeys(required_fields)),
    )


def check_context_sufficiency(state: TenantAgentState) -> dict:
    product = state.get("product_context")
    if product is None:
        raise RuntimeError("Product context is unavailable")
    product_input = build_product_applicability_context(product)
    results = []
    missing = []
    ready = []
    for requirement in state.get("requirements", []):
        result = deterministic_applicability_precheck(
            build_requirement_applicability_context(requirement), product_input
        )
        if result is None:
            ready.append(requirement.id)
        else:
            results.append(result)
            missing.extend(result.missing_context)
    return {
        "ready_requirement_ids": ready,
        "applicability_results": results,
        "missing_context": missing,
    }
