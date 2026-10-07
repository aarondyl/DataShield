"""Exercise Tenant Intelligence persistence on an Alembic-migrated database."""

from pathlib import Path
import sys

from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import engine
from app.models import Company, LegalUnit, Product, ProductTwinVersion, Regulation, RegulationVersion, Requirement
from app.tenant.applicability.schemas import ApplicabilityResult, DecisionSource
from app.tenant.context.schemas import ProductContext
from app.tenant.findings import (
    FindingCandidate,
    ImpactLevel,
    TenantTriggerType,
    build_input_snapshot,
    create_agent_run,
    persist_findings,
)
from app.tenant.gap.schemas import GapAnalysisResult, GapStatus, GapType
from app.tenant.regulatory.schemas import (
    LegalEvidence,
    RegulationSourceContext,
    RegulationTrigger,
    RequirementContext,
)


with Session(engine) as db:
    company = Company(name="Tenant Intelligence migration smoke")
    db.add(company)
    db.flush()
    product = Product(company_id=company.id, name="Tenant smoke product")
    db.add(product)
    regulation = Regulation(name="Tenant smoke regulation", jurisdiction="EU", source_url="https://example.com/law")
    db.add(regulation)
    db.flush()
    version = RegulationVersion(
        regulation_id=regulation.id, version_number=1, normalized_text="Article 1",
        content_hash="a" * 64, source_url=regulation.source_url, is_current=True,
    )
    db.add(version)
    db.flush()
    regulation.current_version_id = version.id
    unit = LegalUnit(version_id=version.id, unit_type="article", unit_number="Article 1",
                     heading="Notice", text="Providers shall give notice.")
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
        regulation_version=1, source_url=regulation.source_url,
    )
    evidence = LegalEvidence(
        legal_unit_id=unit.id, regulation_id=regulation.id, regulation_name=regulation.name,
        version_id=version.id, version=1, article="Article 1", heading="Notice",
        content=unit.text, source_url=regulation.source_url, requirement_ids=[requirement.id],
    )
    trigger = RegulationTrigger(
        event_id="evt_smoke", event_type="regulation.change.ready",
        regulation_id=regulation.id, version_id=version.id, requirement_ids=[requirement.id],
        legal_unit_ids=[unit.id], source=RegulationSourceContext(
            regulation_name=regulation.name, jurisdiction="EU", version=1,
            source_url=regulation.source_url,
        ),
    )
    product_context = ProductContext(
        tenant_id=company.id, product_id=product.id,
        product_twin_version_id=twin.id, product_twin_version_number=1,
    )
    snapshot = build_input_snapshot(product_context, trigger, [requirement_context], [evidence])
    run = create_agent_run(
        db, tenant_id=company.id, product_id=product.id,
        trigger_type=TenantTriggerType.REGULATION_CHANGE, trigger_id=trigger.event_id,
        input_snapshot=snapshot, model_provider="mock", model_name="deterministic",
        prompt_version="tenant-v1",
    )
    candidate = FindingCandidate(
        title="Tenant smoke finding", impact_level=ImpactLevel.MEDIUM, confidence=.8,
        applicability=ApplicabilityResult(
            requirement_id=requirement.id, applies=True, confidence=.9,
            reasoning_summary="Applies in the smoke scenario.",
            decision_source=DecisionSource.DETERMINISTIC,
        ),
        gap=GapAnalysisResult(
            requirement_id=requirement.id, gap_status=GapStatus.POTENTIAL,
            gap_type=GapType.INSUFFICIENT_EVIDENCE, current_state="Evidence is incomplete.",
            required_state="Give notice.", confidence=.8,
            reasoning_summary="Potential notice gap.",
        ),
        requirements=[requirement_context], legal_evidence=[evidence],
        product_twin_version_id=twin.id,
    )
    findings = persist_findings(db, run.id, [candidate])
    assert len(findings) == 1
    assert findings[0].product_twin_version_id == twin.id
