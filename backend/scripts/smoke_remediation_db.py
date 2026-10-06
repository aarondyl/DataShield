"""Exercise Remediation persistence and canonical traceability on PostgreSQL."""

from pathlib import Path
import sys

from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.llm import MockLLMClient
from app.db.session import engine
from app.models import (
    Company, LegalUnit, Product, ProductTwinVersion, Regulation, RegulationVersion, Requirement,
)
from app.tenant.applicability.schemas import ApplicabilityResult, DecisionSource
from app.tenant.context.schemas import ProductContext
from app.tenant.findings import (
    FindingCandidate, ImpactLevel, TenantTriggerType, build_input_snapshot,
    create_agent_run, persist_findings,
)
from app.tenant.gap.schemas import GapAnalysisResult, GapStatus, GapType
from app.tenant.regulatory.schemas import LegalEvidence, ManualScanContext, RequirementContext
from app.tenant.remediation import (
    RemediationCreateRequest, RemediationStatus, RemediationType,
    approve_remediation, get_remediation, plan_remediation,
)


with Session(engine) as db:
    company = Company(name="Remediation migration smoke")
    db.add(company)
    db.flush()
    product = Product(company_id=company.id, name="Remediation smoke product")
    regulation = Regulation(
        name="Remediation smoke regulation", jurisdiction="EU",
        canonical_source_url="https://example.com/remediation-law",
    )
    db.add_all([product, regulation])
    db.flush()
    version = RegulationVersion(
        regulation_id=regulation.id, version_number=1, normalized_text="Article 1",
        content_hash="r" * 64, is_current=True,
    )
    db.add(version)
    db.flush()
    regulation.current_version_id = version.id
    unit = LegalUnit(
        version_id=version.id, unit_type="article", unit_number="Article 1",
        heading="Transparency", text="Providers shall give notice.",
    )
    db.add(unit)
    db.flush()
    requirement = Requirement(
        regulation_id=regulation.id, version_id=version.id, legal_unit_id=unit.id,
        requirement_type="obligation", subject_type="provider", action_type="inform",
        object_type="users", summary="Give notice", confidence=1, status="ACTIVE",
    )
    twin = ProductTwinVersion(product_id=product.id, version_number=1, reason="SMOKE")
    db.add_all([requirement, twin])
    db.commit()

    requirement_context = RequirementContext(
        id=requirement.id, regulation_id=regulation.id, version_id=version.id,
        legal_unit_id=unit.id, requirement_type="obligation", subject_type="provider",
        action_type="inform", object_type="users", summary="Give notice", confidence=1,
        status="ACTIVE", regulation_name=regulation.name, jurisdiction="EU",
        regulation_version=1, source_url=regulation.canonical_source_url,
    )
    evidence = LegalEvidence(
        legal_unit_id=unit.id, regulation_id=regulation.id, regulation_name=regulation.name,
        version_id=version.id, version=1, article="Article 1", heading="Transparency",
        content=unit.text, source_url=regulation.canonical_source_url,
        requirement_ids=[requirement.id],
    )
    applicability = ApplicabilityResult(
        requirement_id=requirement.id, applies=True, confidence=.9,
        reasoning_summary="The requirement applies in the smoke scenario.",
        decision_source=DecisionSource.DETERMINISTIC,
    )
    gap = GapAnalysisResult(
        requirement_id=requirement.id, gap_status=GapStatus.POTENTIAL,
        gap_type=GapType.INSUFFICIENT_EVIDENCE,
        current_state="The available evidence does not establish that notice is present.",
        required_state="Give notice.", confidence=.8,
        reasoning_summary="The notice control may require verification.",
    )
    context = ProductContext(
        tenant_id=company.id, product_id=product.id,
        product_twin_version_id=twin.id, product_twin_version_number=1,
    )
    trigger = ManualScanContext(requirement_ids=[requirement.id])
    snapshot = build_input_snapshot(context, trigger, [requirement_context], [evidence])
    run = create_agent_run(
        db, tenant_id=company.id, product_id=product.id,
        trigger_type=TenantTriggerType.MANUAL_SCAN, trigger_id=None, input_snapshot=snapshot,
        model_provider="mock", model_name="deterministic", prompt_version="tenant-v1",
    )
    candidates = [FindingCandidate(
        title="Transparency notice may be insufficient", impact_level=ImpactLevel.MEDIUM,
        confidence=.8, applicability=applicability, gap=gap,
        requirements=[requirement_context], legal_evidence=[evidence],
        product_twin_version_id=twin.id,
    )]
    finding = persist_findings(db, run.id, candidates)[0]

    detail = plan_remediation(
        db, company.id, finding.id,
        RemediationCreateRequest(
            tenant_id=company.id, remediation_type=RemediationType.CODE_CHANGE,
            target_components=["notice component"],
        ),
        llm_client=MockLLMClient(),
    )
    assert detail.requirements[0].id == requirement.id
    assert detail.legal_evidence[0].legal_unit_id == unit.id
    assert detail.product_twin_version.id == twin.id
    approved = approve_remediation(db, company.id, detail.remediation.id, note="smoke approval")
    assert approved.status == RemediationStatus.APPROVED
    reloaded = get_remediation(db, company.id, detail.remediation.id)
    assert reloaded.remediation.status == RemediationStatus.APPROVED
