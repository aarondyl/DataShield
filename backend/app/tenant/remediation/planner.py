"""Grounded, linear Remediation planner over persisted Finding context."""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.llm import BaseLLMClient, get_llm_client
from app.models import Finding
from app.tenant.context.schemas import ProductFactContext
from app.tenant.findings.schemas import FindingRecordStatus, TenantAgentInputSnapshot
from app.tenant.findings.service import load_finding
from app.tenant.gap.schemas import GapStatus
from app.tenant.remediation.renderer import (
    build_code_change_plan,
    build_document_change_plan,
)
from app.tenant.remediation.schemas import (
    CodeChangePlan,
    CodeChangeProposal,
    DocumentChangePlan,
    DocumentChangeProposal,
    RemediationCreateRequest,
    RemediationEvidenceReference,
    RemediationPlanningInput,
    RemediationType,
    validate_remediation_grounding,
)
from app.tenant.remediation.service import (
    RemediationConflictError,
    RemediationNotFoundError,
    create_remediation,
    get_remediation,
    load_authoritative_applicability_context,
    load_authoritative_gap_context,
)
from app.understanding.schemas import FindingStatus


class RemediationPlanningError(RuntimeError):
    """Raised when trusted planning input or structured model output is invalid."""


class RemediationProviderError(RemediationPlanningError):
    """Raised when the configured model provider cannot produce a response."""


_SYSTEM_PROMPT = """You generate implementation recommendations grounded only in supplied evidence.

Rules:
- Do not invent legal requirements.
- Do not invent product facts.
- Do not invent file paths.
- Do not claim UNKNOWN facts are false.
- NOT_DETECTED does not mean confirmed absence.
- Return JSON matching the required schema.
- Do not include chain-of-thought. Use concise rationale only.
- Preserve the Finding's POTENTIAL or CONFIRMED level of certainty.
- A document draft always requires human review and is never ready to publish.
- Never write phrases such as "ready to publish", "final policy", "fully compliant", "legally compliant", "compliant final version", "non-compliant", "the product violates", or "confirmed absent" anywhere in the output.
- When a supplied product fact has status UNKNOWN, the draft_text must contain an explicit "[TO CONFIRM: ...]" placeholder for it.
- All user-facing text in the JSON values (change, rationale, constraints, acceptance_criteria, tests, section, draft_text, etc.) must be written in Simplified Chinese; keep field names, enum values and file paths unchanged.

Output exactly one JSON object with these top-level fields and no others.
The input keys are FACTS, LEGAL_REQUIREMENTS, LEGAL_EVIDENCE, GAP, USER_CONSTRAINTS and TASK.
For remediation type CODE_CHANGE:
- "requested_changes": non-empty array of {"target": string, "change": string, "rationale": string}
- "affected_files_or_components": non-empty array of strings chosen from FACTS.allowed_file_paths or USER_CONSTRAINTS.target_components
- "constraints": array of strings (may be empty)
- "acceptance_criteria": non-empty array of strings
- "tests": non-empty array of {"name": string, "purpose": string, "expected_result": string}
- "do_not_modify": array of strings (may be empty)
For remediation type DOCUMENT_CHANGE:
- "document_type": string copied from USER_CONSTRAINTS.document_type
- "proposed_changes": non-empty array of {"section": string, "change": string, "rationale": string}
- "draft_text": string with the full human-reviewable draft
- "evidence": non-empty array; each item must be one complete object copied verbatim from LEGAL_EVIDENCE, keeping all of its fields (requirement_id, legal_unit_id, regulation_id, regulation_name, version_id, version, article, heading, source_url). Plain strings, ids, or URLs are not valid evidence items.
- "acceptance_criteria": non-empty array of strings; every criterion must keep the draft subject to human review
"""

_FILE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".css", ".go", ".html", ".java", ".js", ".json",
    ".jsx", ".md", ".php", ".py", ".rb", ".rs", ".sql", ".toml", ".ts",
    ".tsx", ".vue", ".xml", ".yaml", ".yml",
}
_POTENTIAL_FORBIDDEN = (
    "definitely missing",
    "control is missing",
    "product violates",
    "the product violates",
    "non-compliant",
    "noncompliant",
    "illegal",
)
_LEGAL_CONCLUSION_FORBIDDEN = (
    "compliant final version",
    "fully compliant",
    "legally compliant",
    "ready to publish",
    "final policy",
    "non-compliant beyond doubt",
)
_ABSENCE_FORBIDDEN = (
    "confirmed absent",
    "definitely absent",
    "does not exist",
    "definitely missing",
)


def _tokens(value: str) -> set[str]:
    normalized = value.casefold().replace("_", " ").replace("-", " ")
    return set(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", normalized))


def _relevance_terms(detail, gap) -> set[str]:
    text = " ".join([
        detail.finding.title,
        detail.finding.gap_summary,
        gap.current_state,
        gap.required_state,
        *(item.summary for item in detail.requirements),
        *(item.object_type for item in detail.requirements),
        *(item.action_type for item in detail.requirements),
    ])
    terms = _tokens(text)
    if terms & {"deletion", "delete", "erasure", "account"}:
        terms.update({"account", "deletion", "delete", "erasure", "user", "profile"})
    if terms & {"ai", "transparency", "disclosure", "人工智能", "透明度"}:
        terms.update({
            "ai", "artificial", "intelligence", "transparency", "disclosure",
            "chat", "generation", "target", "users", "public", "documents",
        })
    if terms & {"privacy", "notice", "document", "policy", "告知", "政策"}:
        terms.update({"privacy", "notice", "document", "policy", "public"})
    return terms


def select_relevant_product_facts(
    facts: list[ProductFactContext],
    *,
    detail,
    gap,
    remediation_type: RemediationType,
) -> list[ProductFactContext]:
    """Select a deterministic historical subset without embeddings or current Twin reads."""

    terms = _relevance_terms(detail, gap)
    supporting_ids = set(gap.supporting_fact_ids)
    selected: list[tuple[int, int, ProductFactContext]] = []
    for position, fact in enumerate(facts):
        evidence_text = " ".join(
            str(value)
            for item in fact.evidence
            for value in item.values()
            if isinstance(value, (str, int, float))
        )
        haystack = " ".join([
            fact.group,
            fact.name,
            str(fact.value or ""),
            evidence_text,
        ])
        score = len(terms & _tokens(haystack))
        if fact.fact_id is not None and fact.fact_id in supporting_ids:
            score += 100
        if remediation_type == RemediationType.DOCUMENT_CHANGE and fact.group == "public_documents":
            score += 2
        if score > 0:
            selected.append((score, position, fact))
    selected.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in selected[:20]]


def _allowed_paths(facts: list[ProductFactContext]) -> list[str]:
    paths = []
    for fact in facts:
        for evidence in fact.evidence:
            for key in ("file", "path"):
                value = evidence.get(key)
                if isinstance(value, str) and value.strip():
                    paths.append(value.strip().replace("\\", "/"))
    return list(dict.fromkeys(paths))


def _looks_like_path(value: str) -> bool:
    normalized = value.strip().replace("\\", "/")
    if normalized.startswith(("/", "./", "../")):
        return True
    if PurePosixPath(normalized).suffix.casefold() in _FILE_SUFFIXES:
        return True
    return "/" in normalized and " " not in normalized


def _validate_code_targets(proposal: CodeChangeProposal, allowed_paths: list[str]) -> None:
    allowed = {item.replace("\\", "/") for item in allowed_paths}
    targets = [
        *proposal.affected_files_or_components,
        *(item.target for item in proposal.requested_changes),
    ]
    invented = sorted({
        item for item in targets
        if _looks_like_path(item) and item.replace("\\", "/") not in allowed
    })
    if invented:
        raise RemediationPlanningError(
            f"Remediation proposal contains file paths absent from Product evidence: {invented}"
        )


def _evidence_references(detail) -> list[RemediationEvidenceReference]:
    requirement_ids = {item.id for item in detail.requirements}
    references = []
    for evidence in detail.legal_evidence:
        for requirement_id in sorted(set(evidence.requirement_ids) & requirement_ids):
            references.append(RemediationEvidenceReference(
                requirement_id=requirement_id,
                legal_unit_id=evidence.legal_unit_id,
                regulation_id=evidence.regulation_id,
                regulation_name=evidence.regulation_name,
                version_id=evidence.version_id,
                version=evidence.version,
                article=evidence.article,
                heading=evidence.heading,
                source_url=evidence.source_url,
            ))
    if not references:
        raise RemediationPlanningError("Finding has no canonical evidence references for planning")
    return references


def _all_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _all_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_strings(item)


def _validate_language(
    proposal: CodeChangeProposal | DocumentChangeProposal,
    *,
    gap_status: str,
    facts: list[ProductFactContext],
) -> None:
    text = "\n".join(_all_strings(proposal.model_dump(mode="json"))).casefold()
    forbidden = list(_LEGAL_CONCLUSION_FORBIDDEN)
    if gap_status == "POTENTIAL":
        forbidden.extend(_POTENTIAL_FORBIDDEN)
    if any(fact.status in {FindingStatus.UNKNOWN, FindingStatus.NOT_DETECTED} for fact in facts):
        forbidden.extend(_ABSENCE_FORBIDDEN)
    matches = sorted({phrase for phrase in forbidden if phrase in text})
    if matches:
        raise RemediationPlanningError(
            f"Remediation proposal overstates Finding or Product evidence: {matches}"
        )
    if isinstance(proposal, DocumentChangeProposal):
        if any(fact.status == FindingStatus.UNKNOWN for fact in facts) and not re.search(
            r"\[(?:TO CONFIRM|INSERT|CONFIRM)[^\]]*\]", proposal.draft_text, re.IGNORECASE
        ):
            raise RemediationPlanningError(
                "Document draft must use an explicit placeholder for UNKNOWN product facts"
            )


def _prompt_input(
    planning_input: RemediationPlanningInput,
    *,
    gap,
    allowed_paths: list[str],
    references: list[RemediationEvidenceReference],
) -> str:
    payload = {
        "FACTS": {
            "finding": {
                "id": planning_input.finding_id,
                "title": planning_input.finding_title,
                "gap_status": planning_input.gap_status,
                "confidence": planning_input.finding_confidence,
            },
            "product_facts": [
                item.model_dump(mode="json") for item in planning_input.relevant_product_facts
            ],
            "allowed_file_paths": allowed_paths,
        },
        "LEGAL_REQUIREMENTS": [
            item.model_dump(mode="json") for item in planning_input.requirements
        ],
        "LEGAL_EVIDENCE": [item.model_dump(mode="json") for item in references],
        "GAP": gap.model_dump(mode="json"),
        "USER_CONSTRAINTS": {
            "target_components": planning_input.planner_request.target_components,
            "constraints": planning_input.planner_request.constraints,
            "document_type": planning_input.planner_request.document_type,
        },
        "TASK": (
            "Return only a CODE_CHANGE CodeChangeProposal JSON object."
            if planning_input.planner_request.remediation_type == RemediationType.CODE_CHANGE
            else "Return only a DOCUMENT_CHANGE DocumentChangeProposal JSON object."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _llm_context(
    planning_input: RemediationPlanningInput,
    *,
    allowed_paths: list[str],
    references: list[RemediationEvidenceReference],
) -> dict[str, Any]:
    return {
        "task": (
            "remediation-code"
            if planning_input.planner_request.remediation_type == RemediationType.CODE_CHANGE
            else "remediation-document"
        ),
        "finding": {
            "id": planning_input.finding_id,
            "title": planning_input.finding_title,
            "gap_status": planning_input.gap_status,
        },
        "requirements": [item.model_dump(mode="json") for item in planning_input.requirements],
        "allowed_evidence_references": [item.model_dump(mode="json") for item in references],
        "allowed_paths": allowed_paths,
        "target_components": planning_input.planner_request.target_components,
        "user_constraints": planning_input.planner_request.constraints,
        "document_type": planning_input.planner_request.document_type,
        "has_unknown_facts": any(
            item.status == FindingStatus.UNKNOWN
            for item in planning_input.relevant_product_facts
        ),
    }


def _structured_proposal(
    client: BaseLLMClient,
    planning_input: RemediationPlanningInput,
    *,
    gap,
    allowed_paths: list[str],
    references: list[RemediationEvidenceReference],
) -> CodeChangeProposal | DocumentChangeProposal:
    try:
        raw = client.chat_json(
            _SYSTEM_PROMPT,
            _prompt_input(
                planning_input,
                gap=gap,
                allowed_paths=allowed_paths,
                references=references,
            ),
            context=_llm_context(
                planning_input,
                allowed_paths=allowed_paths,
                references=references,
            ),
        )
    except Exception as exc:
        raise RemediationProviderError(f"LLM remediation generation failed: {exc}") from exc
    if not isinstance(raw, dict):
        raise RemediationPlanningError("LLM remediation output is not a JSON object")
    contract = (
        CodeChangeProposal
        if planning_input.planner_request.remediation_type == RemediationType.CODE_CHANGE
        else DocumentChangeProposal
    )
    try:
        return contract.model_validate(raw)
    except ValidationError as exc:
        raise RemediationPlanningError(f"LLM remediation output failed schema validation: {exc}") from exc


def plan_remediation(
    db: Session,
    tenant_id: int,
    finding_id: int,
    request: RemediationCreateRequest,
    *,
    llm_client: BaseLLMClient | None = None,
):
    """Plan and persist one grounded Remediation without mutating source domains."""

    if request.tenant_id != tenant_id:
        raise RemediationNotFoundError("Finding does not exist for this tenant")
    detail = load_finding(db, tenant_id, finding_id)
    if detail is None:
        raise RemediationNotFoundError("Finding does not exist for this tenant")
    if detail.finding.status != FindingRecordStatus.OPEN:
        raise RemediationConflictError(
            f"Cannot plan remediation for Finding in {detail.finding.status.value} status"
        )
    finding = db.get(Finding, finding_id)
    if finding is None or finding.tenant_id != tenant_id:
        raise RemediationNotFoundError("Finding does not exist for this tenant")

    gap = load_authoritative_gap_context(db, finding)
    applicability = load_authoritative_applicability_context(db, finding, gap.requirement_id)
    try:
        historical = TenantAgentInputSnapshot.model_validate(detail.run.input_snapshot)
    except ValidationError as exc:
        raise RemediationPlanningError("Finding historical Product Context is invalid") from exc
    if (
        historical.tenant_id != tenant_id
        or historical.product_id != detail.finding.product_id
        or historical.product_twin_version_id != detail.finding.product_twin_version_id
    ):
        raise RemediationPlanningError("Finding historical Product Context does not match the Finding")

    relevant_facts = select_relevant_product_facts(
        historical.product_context.facts,
        detail=detail,
        gap=gap,
        remediation_type=request.remediation_type,
    )
    planning_input = RemediationPlanningInput(
        finding_id=detail.finding.id,
        tenant_id=detail.finding.tenant_id,
        product_id=detail.finding.product_id,
        finding_title=detail.finding.title,
        impact_level=detail.finding.impact_level,
        finding_confidence=detail.finding.confidence,
        applicability_summary=applicability.reasoning_summary,
        gap_status=gap.gap_status.value,
        gap_type=gap.gap_type.value,
        gap_summary=gap.reasoning_summary,
        gap_current_state=gap.current_state,
        gap_required_state=gap.required_state,
        product_twin_version_id=detail.finding.product_twin_version_id,
        requirements=detail.requirements,
        legal_evidence=detail.legal_evidence,
        relevant_product_facts=relevant_facts,
        planner_request=request,
    )
    references = _evidence_references(detail)
    allowed_paths = _allowed_paths(relevant_facts)
    try:
        client = llm_client or get_llm_client()
    except Exception as exc:
        raise RemediationProviderError(f"LLM remediation client is unavailable: {exc}") from exc
    proposal = _structured_proposal(
        client,
        planning_input,
        gap=gap,
        allowed_paths=allowed_paths,
        references=references,
    )
    _validate_language(
        proposal,
        gap_status=planning_input.gap_status,
        facts=relevant_facts,
    )

    if isinstance(proposal, CodeChangeProposal):
        _validate_code_targets(proposal, allowed_paths)
        plan: CodeChangePlan | DocumentChangePlan = build_code_change_plan(
            planning_input, proposal
        )
        prompt_version = "remediation-code-v1"
        title = f"实施整改：{detail.finding.title}"
    else:
        if proposal.document_type != request.document_type:
            raise RemediationPlanningError("Document proposal type does not match the request")
        plan = build_document_change_plan(planning_input, proposal)
        prompt_version = "remediation-document-v1"
        title = f"更新文档：{detail.finding.title}"

    validate_remediation_grounding(
        plan,
        {item.id for item in detail.requirements},
        {item.legal_unit_id for item in detail.legal_evidence},
    )
    qualifier = "潜在缺口" if gap.gap_status == GapStatus.POTENTIAL else "已确认缺口"
    summary = (
        f"针对{qualifier}的 {request.remediation_type.value} 整改方案（基于所提供的法规与产品证据）；"
        "执行前需人工审核。"
    )
    record = create_remediation(
        db,
        planning_input=planning_input,
        plan=plan,
        title=title,
        summary=summary,
        model_provider=client.provider_name,
        model_name=getattr(client, "model_name", ""),
        prompt_version=prompt_version,
    )
    return get_remediation(db, tenant_id, record.id)
