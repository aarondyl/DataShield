"""Map Product Twin control facts to Commit 1 gap semantics."""

from __future__ import annotations

from app.tenant.agent.state import TenantAgentState
from app.tenant.context.schemas import ProductFactContext
from app.tenant.gap.schemas import ControlObservation, RequirementControlContext
from app.tenant.gap.service import deterministic_gap_analysis
from app.tenant.regulatory.schemas import RequirementContext
from app.understanding.schemas import FindingStatus


#: 内部控制键 → 面向用户的中文展示名（Finding 标题 / 缺口描述使用）
CONTROL_DISPLAY_NAMES = {
    "ai_disclosure": "AI 交互披露",
    "privacy_notice": "隐私告知",
    "privacy_policy": "隐私政策",
    "account_deletion": "账号删除能力",
    "consent_management": "同意管理",
}


def control_display_name(control: str) -> str:
    """把内部控制键（如 ai_disclosure）转成中文展示名；未知键回退为可读英文。"""
    return CONTROL_DISPLAY_NAMES.get(control, control.replace("_", " "))


def required_control_name(requirement: RequirementContext) -> str:
    text = " ".join((requirement.action_type, requirement.object_type, requirement.summary)).casefold()
    if any(word in text for word in ("transparen", "disclos", "inform", "透明", "披露", "告知")):
        return "ai_disclosure" if any(word in text for word in ("ai", "artificial intelligence", "人工智能")) else "privacy_notice"
    if any(word in text for word in ("delete", "erasure", "删除")):
        return "account_deletion"
    if any(word in text for word in ("consent", "同意")):
        return "consent_management"
    if any(word in text for word in ("privacy policy", "隐私政策")):
        return "privacy_policy"
    return requirement.action_type.strip().casefold().replace(" ", "_") or requirement.object_type.strip().casefold().replace(" ", "_")


def _matches(fact: ProductFactContext, control: str) -> bool:
    canonical = fact.name.casefold().replace(" ", "_")
    return canonical == control or canonical in {f"missing_{control}", f"{control}_absent"}


def _observation(fact: ProductFactContext, control: str) -> ControlObservation:
    review = fact.review_status if fact.review_status in {"UNREVIEWED", "CONFIRMED", "CORRECTED"} else "UNREVIEWED"
    explicit_absence = bool(
        fact.source == "USER"
        and review == "CONFIRMED"
        and fact.status == FindingStatus.PRESENT
        and (fact.value is False or fact.name.casefold() in {f"missing_{control}", f"{control}_absent"})
        and fact.evidence
    )
    return ControlObservation(
        control=control,
        status=fact.status,
        confidence=fact.confidence,
        source_kind=fact.source,
        confirmation_status=review,
        explicit_absence=explicit_absence,
        current_state=("用户已确认该控制不存在。" if explicit_absence else f"Product Twin 状态：{fact.status.value}"),
        affected_assets=list(fact.scan_scope.get("paths", [])),
        fact_ids=[fact.fact_id] if fact.fact_id is not None else [],
        evidence=fact.evidence,
    )


def analyze_gaps(state: TenantAgentState) -> dict:
    product = state.get("product_context")
    if product is None:
        raise RuntimeError("Product context is unavailable")
    requirements = {item.id: item for item in state.get("requirements", [])}
    results = []
    for applicability in state.get("applicability_results", []):
        if applicability.applies is not True:
            continue
        requirement = requirements[applicability.requirement_id]
        control = required_control_name(requirement)
        observations = [
            _observation(fact, control) for fact in product.controls if _matches(fact, control)
        ]
        results.append(deterministic_gap_analysis(
            RequirementControlContext(
                requirement_id=requirement.id,
                required_control=control,
                required_state=requirement.summary or f"实现{control_display_name(control)}控制",
            ),
            observations,
        ))
    return {"gap_results": results}
