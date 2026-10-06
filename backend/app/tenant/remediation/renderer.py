"""Deterministic rendering for executable-by-humans code change prompts."""

from __future__ import annotations

from collections.abc import Iterable

from app.tenant.remediation.schemas import (
    AuthoritativeProblemFields,
    CodeChangePlan,
    CodeChangeProposal,
    RemediationEvidenceReference,
    RemediationPlanningInput,
)


def build_authoritative_problem_fields(
    planning_input: RemediationPlanningInput,
) -> AuthoritativeProblemFields:
    """Copy factual fields from the trusted Finding/Gap context."""

    return AuthoritativeProblemFields(
        problem=planning_input.finding_title,
        current_state=planning_input.gap_current_state,
        required_state=planning_input.gap_required_state,
    )


def _items(values: Iterable[str]) -> str:
    items = list(values)
    return "\n".join(f"- {item}" for item in items) if items else "- None specified"


def _requested_changes(proposal: CodeChangeProposal) -> str:
    return "\n".join(
        f"- **{item.target}**: {item.change}\n  Rationale: {item.rationale}"
        for item in proposal.requested_changes
    )


def _tests(proposal: CodeChangeProposal) -> str:
    return "\n".join(
        f"- **{item.name}**\n  Purpose: {item.purpose}\n  Expected result: {item.expected_result}"
        for item in proposal.tests
    )


def _legal_requirements(planning_input: RemediationPlanningInput) -> str:
    return "\n".join(
        (
            f"- Requirement {item.id} ({item.regulation_name}, version "
            f"{item.regulation_version or item.version_id}): {item.summary}"
        )
        for item in sorted(planning_input.requirements, key=lambda value: value.id)
    )


def _evidence(planning_input: RemediationPlanningInput) -> str:
    return "\n".join(
        (
            f"- Legal unit {item.legal_unit_id}; {item.regulation_name} "
            f"v{item.version}; {item.article or 'article not specified'}; "
            f"requirements {sorted(item.requirement_ids)}; source: "
            f"{item.source_url or 'not available'}"
        )
        for item in sorted(
            planning_input.legal_evidence,
            key=lambda value: (value.legal_unit_id, tuple(sorted(value.requirement_ids))),
        )
    )


def _product_facts(planning_input: RemediationPlanningInput) -> str:
    if not planning_input.relevant_product_facts:
        return "- No additional Product Twin facts were selected. Do not infer missing product behavior."
    return "\n".join(
        (
            f"- {item.group}.{item.name}: {item.status.value} "
            f"(source={item.source}, confidence={item.confidence:.2f}, "
            f"review={item.review_status})"
        )
        for item in sorted(
            planning_input.relevant_product_facts,
            key=lambda value: (value.group, value.name, value.fact_id or 0),
        )
    )


def render_coding_prompt(
    planning_input: RemediationPlanningInput,
    proposal: CodeChangeProposal,
) -> str:
    """Render a stable prompt without LLM calls, timestamps, or invented paths."""

    authoritative = build_authoritative_problem_fields(planning_input)
    return f"""# Context
Finding ID: {planning_input.finding_id}
Product ID: {planning_input.product_id}
Impact level: {planning_input.impact_level.value}
Finding confidence: {planning_input.finding_confidence:.2f}
Product Twin version ID: {planning_input.product_twin_version_id or 'legacy fallback'}

Relevant Product Facts:
{_product_facts(planning_input)}

# Compliance Problem
{authoritative.problem}

Applicability: {planning_input.applicability_summary}
Gap: {planning_input.gap_summary}

# Legal Requirement
{_legal_requirements(planning_input)}

# Current State
{authoritative.current_state}

# Required State
{authoritative.required_state}

# Requested Changes
{_requested_changes(proposal)}

# Affected Components
{_items(proposal.affected_files_or_components)}

# Constraints
{_items(proposal.constraints)}

# Acceptance Criteria
{_items(proposal.acceptance_criteria)}

# Tests
{_tests(proposal)}

# Do Not Modify
{_items(proposal.do_not_modify)}

# Evidence
{_evidence(planning_input)}

# Execution Instructions
- Verify the repository before modifying code.
- Do not assume referenced paths exist unless provided by evidence.
- Preserve unrelated behavior.
- Do not modify files outside the requested scope without justification.
- Compliance references are context, not permission to invent legal requirements.
"""


def build_code_change_plan(
    planning_input: RemediationPlanningInput,
    proposal: CodeChangeProposal,
) -> CodeChangePlan:
    """Combine trusted fact fields, proposal fields, and the rendered prompt."""

    authoritative = build_authoritative_problem_fields(planning_input)
    return CodeChangePlan(
        **authoritative.model_dump(),
        **proposal.model_dump(),
        coding_prompt=render_coding_prompt(planning_input, proposal),
    )
