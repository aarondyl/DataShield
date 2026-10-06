"""Product Twin and legacy Product conversion into stable tenant context."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import Company, Product, ProductTwinFact, ProductTwinVersion
from app.tenant.context import (
    TenantProductMismatchError,
    load_product_context,
    resolve_tenant_product,
)


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tenant-context.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _products(db):
    db.add_all([Company(id=1, name="Tenant A"), Company(id=2, name="Tenant B")])
    db.flush()
    db.add_all([
        Product(id=1, company_id=1, name="Product A"),
        Product(id=2, company_id=2, name="Product B"),
    ])
    db.commit()


def test_tenant_product_ownership_success_and_mismatch(db):
    _products(db)
    assert resolve_tenant_product(db, 1, 1).name == "Product A"
    with pytest.raises(TenantProductMismatchError):
        resolve_tenant_product(db, 1, 2)


def test_current_twin_preserves_facts_conflicts_and_user_priority(db):
    _products(db)
    old = ProductTwinVersion(product_id=1, version_number=1, reason="old")
    current = ProductTwinVersion(product_id=1, version_number=2, reason="current")
    db.add_all([old, current])
    db.flush()
    db.add_all([
        ProductTwinFact(version_id=old.id, group_name="data_types", name="biometric",
                        status="PRESENT", confidence=.2, source_kind="WEBSITE", evidence=[],
                        scan_scope={}, confirmation_status="UNREVIEWED"),
        ProductTwinFact(version_id=current.id, group_name="data_types", name="biometric",
                        status="NOT_DETECTED", confidence=.8, source_kind="REPOSITORY",
                        evidence=[{"reason": "scan"}], scan_scope={"files": 10},
                        confirmation_status="UNREVIEWED"),
        ProductTwinFact(version_id=current.id, group_name="data_types", name="biometric",
                        status="PRESENT", confidence=1, source_kind="USER",
                        evidence=[{"reason": "owner confirmed"}], scan_scope={"type": "user_input"},
                        confirmation_status="CONFIRMED"),
        ProductTwinFact(version_id=current.id, group_name="features", name="unknown_feature",
                        status="UNKNOWN", confidence=0, source_kind="WEBSITE", evidence=[],
                        scan_scope={}, confirmation_status="UNREVIEWED"),
    ])
    db.commit()

    context = load_product_context(db, 1, 1)

    assert context.product_twin_version_id == current.id
    assert context.product_twin_version_number == 2
    biometric = [item for item in context.facts if item.name == "biometric"]
    assert {item.status.value for item in biometric} == {"PRESENT", "NOT_DETECTED"}
    selected = next(item for item in context.data_types if item.name == "biometric")
    assert selected.source == "USER" and selected.is_user_confirmed is True
    assert context.conflicts[0].name == "biometric"
    unknown = next(item for item in context.facts if item.name == "unknown_feature")
    assert unknown.status.value == "UNKNOWN"


def test_corrected_fact_is_not_active_in_derived_view(db):
    _products(db)
    version = ProductTwinVersion(product_id=1, version_number=1, reason="correction")
    db.add(version)
    db.flush()
    db.add_all([
        ProductTwinFact(version_id=version.id, group_name="features", name="chat",
                        status="NOT_DETECTED", confidence=.7, source_kind="WEBSITE", evidence=[],
                        scan_scope={}, confirmation_status="CORRECTED"),
        ProductTwinFact(version_id=version.id, group_name="features", name="chat",
                        status="PRESENT", confidence=1, source_kind="USER", evidence=[{"reason": "corrected"}],
                        scan_scope={}, confirmation_status="CONFIRMED"),
    ])
    db.commit()

    context = load_product_context(db, 1, 1)

    assert len([item for item in context.features if item.name == "chat"]) == 1
    assert context.features[0].status.value == "PRESENT"


def test_user_control_priority_applies_across_source_groups(db):
    _products(db)
    version = ProductTwinVersion(product_id=1, version_number=1, reason="control")
    db.add(version)
    db.flush()
    db.add_all([
        ProductTwinFact(version_id=version.id, group_name="capabilities", name="ai_disclosure",
                        status="NOT_DETECTED", confidence=.9, source_kind="WEBSITE", evidence=[],
                        scan_scope={}, confirmation_status="UNREVIEWED"),
        ProductTwinFact(version_id=version.id, group_name="controls", name="ai_disclosure",
                        status="PRESENT", confidence=1, source_kind="USER", evidence=[{"reason": "confirmed"}],
                        scan_scope={}, confirmation_status="CONFIRMED"),
    ])
    db.commit()

    context = load_product_context(db, 1, 1)

    selected = [item for item in context.controls if item.name == "ai_disclosure"]
    assert len(selected) == 1
    assert selected[0].source == "USER"


def test_legacy_true_is_present_and_false_is_unknown(db):
    db.add(Company(id=1, name="Tenant", target_markets=["EU"]))
    db.flush()
    db.add(Product(id=1, company_id=1, name="Legacy", collects_personal_data=True,
                   collects_sensitive_data=False, category="SaaS"))
    db.commit()

    context = load_product_context(db, 1, 1)

    assert context.used_legacy_fallback is True
    personal = next(item for item in context.facts if item.name == "personal_data")
    sensitive = next(item for item in context.facts if item.name == "sensitive_data")
    assert personal.status.value == "PRESENT" and personal.confidence < .7
    assert sensitive.status.value == "UNKNOWN" and sensitive.value is None
