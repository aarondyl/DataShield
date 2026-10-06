"""Map Product Twin control facts to Commit 1 gap semantics."""

from __future__ import annotations

from app.tenant.agent.state import TenantAgentState
from app.tenant.context.schemas import ProductFactContext
from app.tenant.gap.schemas import ControlObservation, RequirementControlContext
from app.tenant.gap.service import deterministic_gap_analysis
from app.tenant.regulatory.schemas import RequirementContext
from app.understanding.schemas import FindingStatus


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
                required_state=requirement.summary or f"Implement {control}",
            ),
            observations,
        ))
    return {"gap_results": results}
