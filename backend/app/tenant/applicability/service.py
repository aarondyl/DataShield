"""Conservative deterministic checks performed before LLM reasoning."""

from __future__ import annotations

from typing import Any

from app.tenant.applicability.schemas import (
    ApplicabilityCondition,
    ApplicabilityResult,
    ContextFact,
    DecisionSource,
    MatchedFact,
    MissingContextItem,
    ProductApplicabilityContext,
    RequirementApplicabilityContext,
)
from app.understanding.schemas import FindingStatus


_EU_ALIASES = {
    "eu", "european union", "europe", "欧洲", "欧盟", "austria", "belgium",
    "bulgaria", "croatia", "cyprus", "czechia", "czech republic", "denmark",
    "estonia", "finland", "france", "germany", "greece", "hungary", "ireland",
    "italy", "latvia", "lithuania", "luxembourg", "malta", "netherlands",
    "poland", "portugal", "romania", "slovakia", "slovenia", "spain", "sweden",
}

_QUESTIONS = {
    "markets": "你的产品面向哪些国家或地区提供服务？",
    "jurisdiction": "你的产品面向哪些国家或地区提供服务？",
    "subject_types": "你的企业在相关数据处理中承担什么角色？",
    "product_category": "你的产品属于什么类型？",
    "target_users": "你的产品主要面向哪些用户群体？",
    "data_types": "你的产品处理哪些类型的数据？",
    "ai_features": "你的产品是否提供人工智能或自动化决策功能？",
    "business_model": "你的产品采用什么商业模式和业务活动？",
    "cross_border_behavior": "产品数据是否会跨国家或地区传输？",
    "children_or_minors": "产品是否面向或可能被儿童、未成年人使用？",
    "sensitive_data": "产品是否处理敏感个人数据？",
    "automated_decision_making": "产品是否执行对个人产生重要影响的自动化决策？",
}


def _tokens(value: Any) -> set[str]:
    if value is None:
        return set()
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return {str(item).strip().casefold() for item in values if str(item).strip()}


def _jurisdiction_tokens(value: Any) -> set[str]:
    tokens = _tokens(value)
    if tokens & _EU_ALIASES:
        tokens.add("eu")
    return tokens


def _usable(fact: ContextFact | None) -> bool:
    return fact is not None and fact.status not in {FindingStatus.UNKNOWN, FindingStatus.NOT_DETECTED}


def _matched(fact: ContextFact) -> MatchedFact:
    return MatchedFact(field=fact.field_path, value=fact.value, fact_ids=fact.fact_ids, evidence=fact.evidence)


def _question(field_path: str, requirement_id: int, custom: str | None = None) -> MissingContextItem:
    root = field_path.split(".", 1)[0]
    return MissingContextItem(
        field_path=field_path,
        question=custom or _QUESTIONS.get(root, f"请补充产品字段 {field_path} 的信息。"),
        reason="当前 Requirement 的适用性判断依赖此事实。",
        requirement_id=requirement_id,
    )


def _evaluate(condition: ApplicabilityCondition, fact: ContextFact) -> bool | None:
    if not _usable(fact):
        return None
    actual = fact.value
    expected = condition.value
    if condition.operator == "IS_TRUE":
        return actual is True
    if condition.operator == "IS_FALSE":
        return actual is False
    if condition.operator == "EQUALS":
        return str(actual).strip().casefold() == str(expected).strip().casefold()
    if condition.operator == "IN":
        return str(actual).strip().casefold() in _tokens(expected)
    if condition.operator == "CONTAINS_ANY":
        return bool(_tokens(actual) & _tokens(expected))
    return None


def _unknown_result(
    requirement_id: int,
    matched: list[MatchedFact],
    missing: list[MissingContextItem],
) -> ApplicabilityResult:
    return ApplicabilityResult(
        requirement_id=requirement_id,
        applies=None,
        confidence=0,
        matched_facts=matched,
        missing_context=missing,
        reasoning_summary="缺少判断该 Requirement 适用性所需的产品上下文。",
        decision_source=DecisionSource.INSUFFICIENT_CONTEXT,
    )


def deterministic_applicability_precheck(
    requirement: RequirementApplicabilityContext,
    product: ProductApplicabilityContext,
) -> ApplicabilityResult | None:
    """Return a conclusive pre-check, an insufficient-context result, or None.

    ``None`` means the available facts are sufficient but the conditions need
    structured LLM reasoning. It is distinct from ``applies=None``, which means
    the product context itself is missing.
    """

    matched: list[MatchedFact] = []
    missing: list[MissingContextItem] = []

    for field_path in requirement.required_fields:
        fact = product.facts.get(field_path)
        if not _usable(fact):
            missing.append(_question(field_path, requirement.requirement_id))

    if requirement.jurisdiction:
        fact = product.facts.get("markets") or product.facts.get("jurisdiction")
        if not _usable(fact):
            missing.append(_question("markets", requirement.requirement_id))
        else:
            expected = _jurisdiction_tokens(requirement.jurisdiction)
            actual = _jurisdiction_tokens(fact.value)
            if expected & actual:
                matched.append(_matched(fact))
            elif fact.confirmed and fact.complete:
                return ApplicabilityResult(
                    requirement_id=requirement.requirement_id,
                    applies=False,
                    confidence=fact.confidence,
                    matched_facts=[_matched(fact)],
                    reasoning_summary="已确认的完整市场范围不包含该 Requirement 的法域。",
                    decision_source=DecisionSource.DETERMINISTIC,
                )
            else:
                missing.append(_question("markets", requirement.requirement_id))

    standard_conditions: list[ApplicabilityCondition] = []
    if requirement.subject_type:
        standard_conditions.append(ApplicabilityCondition(
            field_path="subject_types", operator="CONTAINS_ANY", value=[requirement.subject_type]
        ))
    if requirement.product_types:
        standard_conditions.append(ApplicabilityCondition(
            field_path="product_category", operator="IN", value=requirement.product_types
        ))

    for condition in [*standard_conditions, *requirement.conditions]:
        fact = product.facts.get(condition.field_path)
        if not _usable(fact):
            missing.append(_question(condition.field_path, requirement.requirement_id, condition.question))
            continue
        outcome = _evaluate(condition, fact)
        if outcome is True:
            matched.append(_matched(fact))
        elif outcome is False and fact.confirmed and fact.complete:
            return ApplicabilityResult(
                requirement_id=requirement.requirement_id,
                applies=False,
                confidence=fact.confidence,
                matched_facts=[*matched, _matched(fact)],
                reasoning_summary=f"已确认的产品事实不满足适用条件 {condition.field_path}。",
                decision_source=DecisionSource.DETERMINISTIC,
            )
        else:
            # A partial or incomplete non-match cannot prove absence.
            missing.append(_question(condition.field_path, requirement.requirement_id, condition.question))

    for exception in requirement.exceptions:
        fact = product.facts.get(exception.field_path)
        if not _usable(fact):
            missing.append(_question(exception.field_path, requirement.requirement_id, exception.question))
            continue
        outcome = _evaluate(exception, fact)
        if outcome is True:
            return ApplicabilityResult(
                requirement_id=requirement.requirement_id,
                applies=False,
                confidence=fact.confidence,
                matched_facts=[*matched, _matched(fact)],
                reasoning_summary=f"已确认的产品事实满足例外条件 {exception.field_path}。",
                decision_source=DecisionSource.DETERMINISTIC,
            )
        if outcome is False and fact.confirmed and fact.complete:
            matched.append(_matched(fact))
        else:
            # An unresolved exception requires reasoning rather than a guess.
            return None

    if missing:
        unique = {item.field_path: item for item in missing}
        return _unknown_result(requirement.requirement_id, matched, list(unique.values()))

    confidence = min((product.facts[f.field].confidence for f in matched), default=0.8)
    return ApplicabilityResult(
        requirement_id=requirement.requirement_id,
        applies=True,
        confidence=confidence,
        matched_facts=matched,
        reasoning_summary="产品事实满足该 Requirement 的确定性适用条件，且未命中例外。",
        decision_source=DecisionSource.DETERMINISTIC,
    )
