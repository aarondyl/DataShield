"""Build conservative, traceable Finding candidates."""

from app.tenant.agent.nodes.gap_analysis import control_display_name, required_control_name
from app.tenant.agent.state import TenantAgentState
from app.tenant.findings.schemas import FindingCandidate, ImpactLevel
from app.tenant.gap.schemas import GapStatus


def _impact(gap_status: GapStatus, materiality: str) -> ImpactLevel:
    if materiality == "HIGH":
        return ImpactLevel.HIGH if gap_status == GapStatus.CONFIRMED else ImpactLevel.MEDIUM
    if materiality == "CRITICAL":
        return ImpactLevel.HIGH
    if gap_status == GapStatus.CONFIRMED:
        return ImpactLevel.MEDIUM
    return ImpactLevel.LOW if materiality == "LOW" else ImpactLevel.MEDIUM


def build_findings(state: TenantAgentState) -> dict:
    requirements = {item.id: item for item in state.get("requirements", [])}
    applications = {item.requirement_id: item for item in state.get("applicability_results", [])}
    product = state.get("product_context")
    trigger = state.get("regulation_trigger")
    materiality = trigger.materiality if trigger else "LOW"
    candidates = []
    for gap in state.get("gap_results", []):
        if gap.gap_status not in {GapStatus.POTENTIAL, GapStatus.CONFIRMED}:
            continue
        requirement = requirements[gap.requirement_id]
        applicability = applications[gap.requirement_id]
        evidence = [item for item in state.get("legal_evidence", []) if requirement.id in item.requirement_ids]
        confidence = min(applicability.confidence, gap.confidence, requirement.confidence)
        if not evidence:
            confidence = min(confidence, 0.49)
        if requirement.status == "NEEDS_REVIEW":
            confidence = min(confidence, 0.69)
        if product and product.conflicts:
            confidence = min(confidence, 0.69)
        control = control_display_name(required_control_name(requirement))
        title = (
            f"缺少{control}"
            if gap.gap_status == GapStatus.CONFIRMED
            else f"{control}可能不完善"
        )
        candidates.append(FindingCandidate(
            title=title,
            impact_level=_impact(gap.gap_status, materiality),
            confidence=confidence,
            applicability=applicability,
            gap=gap,
            requirements=[requirement],
            legal_evidence=evidence,
            product_twin_version_id=state.get("product_twin_version_id"),
        ))
    return {"finding_candidates": candidates}
