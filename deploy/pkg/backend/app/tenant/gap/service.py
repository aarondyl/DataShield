"""Deterministic gap semantics that preserve Product Twin uncertainty."""

from __future__ import annotations

from app.tenant.gap.schemas import (
    ControlObservation,
    GapAnalysisResult,
    GapStatus,
    GapType,
    RequirementControlContext,
)
from app.understanding.schemas import FindingStatus


def _result(
    requirement: RequirementControlContext,
    observation: ControlObservation | None,
    status: GapStatus,
    gap_type: GapType,
    current_state: str,
    confidence: float,
    reasoning: str,
) -> GapAnalysisResult:
    return GapAnalysisResult(
        requirement_id=requirement.requirement_id,
        gap_status=status,
        gap_type=gap_type,
        current_state=current_state,
        required_state=requirement.required_state,
        affected_assets=(observation.affected_assets if observation and observation.affected_assets
                         else requirement.affected_assets),
        confidence=confidence,
        reasoning_summary=reasoning,
        supporting_fact_ids=observation.fact_ids if observation else [],
        supporting_evidence=observation.evidence if observation else [],
    )


def deterministic_gap_analysis(
    requirement: RequirementControlContext,
    observations: list[ControlObservation],
) -> GapAnalysisResult:
    relevant = [item for item in observations if item.control == requirement.required_control]
    present = [item for item in relevant if item.status == FindingStatus.PRESENT and not item.explicit_absence]
    absent = [item for item in relevant if item.explicit_absence]

    if present and absent:
        evidence = [item for item in present + absent if item.evidence]
        return GapAnalysisResult(
            requirement_id=requirement.requirement_id,
            gap_status=GapStatus.UNKNOWN,
            gap_type=GapType.UNKNOWN,
            current_state="产品事实对该控制是否存在给出了相互冲突的明确证据。",
            required_state=requirement.required_state,
            affected_assets=requirement.affected_assets,
            confidence=0,
            reasoning_summary="冲突必须由用户确认，不能自动选择一个来源。",
            supporting_fact_ids=[fact_id for item in present + absent for fact_id in item.fact_ids],
            supporting_evidence=[entry for item in evidence for entry in item.evidence],
        )

    if absent:
        item = max(absent, key=lambda value: value.confidence)
        return _result(
            requirement, item, GapStatus.CONFIRMED, GapType.MISSING_CONTROL,
            item.current_state or "用户已明确确认该控制不存在。", item.confidence,
            "确认过的用户事实明确声明控制缺失，因此形成已确认缺口。",
        )

    if present:
        item = max(present, key=lambda value: value.confidence)
        return _result(
            requirement, item, GapStatus.NO_GAP, GapType.UNKNOWN,
            item.current_state or "已有证据表明要求的控制存在。", item.confidence,
            "Product Twin 中存在该控制的肯定证据。",
        )

    partial = [item for item in relevant if item.status == FindingStatus.PARTIAL]
    if partial:
        item = max(partial, key=lambda value: value.confidence)
        return _result(
            requirement, item, GapStatus.POTENTIAL, GapType.PARTIAL_CONTROL,
            item.current_state or "只发现了部分控制实现。", item.confidence,
            "现有证据只覆盖部分要求，需要进一步验证或补全控制。",
        )

    not_detected = [item for item in relevant if item.status == FindingStatus.NOT_DETECTED]
    if not_detected:
        item = max(not_detected, key=lambda value: value.confidence)
        return _result(
            requirement, item, GapStatus.POTENTIAL, GapType.INSUFFICIENT_EVIDENCE,
            item.current_state or "在现有扫描范围内未检测到该控制。", item.confidence,
            "NOT_DETECTED 只说明有限范围内没有发现证据，不能证明控制不存在。",
        )

    unknown = [item for item in relevant if item.status == FindingStatus.UNKNOWN]
    item = max(unknown, key=lambda value: value.confidence) if unknown else None
    return _result(
        requirement, item, GapStatus.UNKNOWN, GapType.UNKNOWN,
        (item.current_state if item and item.current_state else "没有足够事实判断该控制状态。"),
        0,
        "产品上下文不足，不能判断是否存在缺口。",
    )
