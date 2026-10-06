"""Load Product Twin facts without collapsing their provenance or uncertainty."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Product, ProductTwinFact, ProductTwinVersion
from app.tenant.context.ownership import resolve_tenant_product
from app.tenant.context.schemas import ProductContext, ProductFactConflict, ProductFactContext
from app.understanding.schemas import FindingStatus


_VIEW_GROUPS = {
    "markets": {"market_clues", "markets"},
    "product_categories": {"product_category"},
    "target_users": {"target_users"},
    "features": {"features"},
    "data_types": {"data_types"},
    "vendors": {"vendors"},
    "controls": {"controls", "capabilities", "public_documents"},
}


def _canonical_name(group: str, name: str) -> str:
    if group == "features" and name == "signup":
        return "user_registration"
    return name


def _priority(fact: ProductFactContext) -> tuple[int, float, int]:
    if fact.is_user_confirmed:
        rank = 4
    elif fact.source == "USER":
        rank = 3
    elif fact.source in {"REPOSITORY", "WEBSITE", "LEGACY"}:
        rank = 2
    else:
        rank = 1
    return rank, fact.confidence, -(fact.fact_id or 0)


def _active_facts(facts: Iterable[ProductFactContext]) -> list[ProductFactContext]:
    items = list(facts)
    superseded = {item.supersedes_fact_id for item in items if item.supersedes_fact_id is not None}
    return [
        item for item in items
        if item.review_status != "CORRECTED" and item.fact_id not in superseded
    ]


def _derived_view(
    facts: list[ProductFactContext], groups: set[str]
) -> list[ProductFactContext]:
    candidates: dict[str, list[ProductFactContext]] = defaultdict(list)
    for fact in _active_facts(facts):
        if fact.group in groups:
            candidates[_canonical_name(fact.group, fact.name)].append(fact)
    return [max(items, key=_priority) for items in candidates.values()]


def _conflicts(facts: list[ProductFactContext]) -> list[ProductFactConflict]:
    grouped: dict[tuple[str, str], list[ProductFactContext]] = defaultdict(list)
    for fact in _active_facts(facts):
        grouped[(fact.group, _canonical_name(fact.group, fact.name))].append(fact)
    conflicts: list[ProductFactConflict] = []
    for (group, name), items in grouped.items():
        asserted = [item for item in items if item.status != FindingStatus.UNKNOWN]
        statuses = {item.status for item in asserted}
        sources = {item.source for item in asserted}
        if len(statuses) > 1 and len(sources) > 1:
            conflicts.append(ProductFactConflict(
                group=group,
                name=name,
                fact_ids=[item.fact_id for item in asserted if item.fact_id is not None],
                statuses=sorted(statuses, key=lambda value: value.value),
                sources=sorted(sources),
            ))
    return conflicts


def _context(
    tenant_id: int,
    product_id: int,
    facts: list[ProductFactContext],
    *,
    version: ProductTwinVersion | None,
    legacy: bool,
) -> ProductContext:
    views = {name: _derived_view(facts, groups) for name, groups in _VIEW_GROUPS.items()}
    return ProductContext(
        tenant_id=tenant_id,
        product_id=product_id,
        product_twin_version_id=version.id if version else None,
        product_twin_version_number=version.version_number if version else None,
        facts=facts,
        conflicts=_conflicts(facts),
        used_legacy_fallback=legacy,
        **views,
    )


def _twin_fact(row: ProductTwinFact) -> ProductFactContext:
    return ProductFactContext(
        fact_id=row.id,
        group=row.group_name,
        name=row.name,
        status=FindingStatus(row.status),
        value=row.name,
        source=row.source_kind,
        confidence=row.confidence,
        evidence=list(row.evidence or []),
        scan_scope=dict(row.scan_scope or {}),
        review_status=row.confirmation_status,
        is_user_confirmed=(row.source_kind == "USER" and row.confirmation_status == "CONFIRMED"),
        supersedes_fact_id=row.supersedes_fact_id,
    )


def _legacy_fact(
    group: str,
    name: str,
    value,
    *,
    present: bool,
    confidence: float = 0.5,
) -> ProductFactContext:
    return ProductFactContext(
        group=group,
        name=name,
        status=FindingStatus.PRESENT if present else FindingStatus.UNKNOWN,
        value=value if present else None,
        source="LEGACY",
        confidence=confidence if present else 0,
        evidence=[{"type": "METADATA", "reason": "Legacy Product/Company compatibility fallback"}],
        scan_scope={"type": "legacy_product_fallback"},
        review_status="UNREVIEWED",
    )


def _legacy_facts(product: Product, company: Company) -> list[ProductFactContext]:
    facts: list[ProductFactContext] = []
    markets = product.target_markets or company.target_markets or []
    facts.extend(_legacy_fact("market_clues", str(market), str(market), present=True) for market in markets)
    if product.category:
        facts.append(_legacy_fact("product_category", product.category, product.category, present=True))

    booleans = {
        "data_types": {
            "personal_data": product.collects_personal_data,
            "sensitive_data": product.collects_sensitive_data,
            "health_data": product.collects_health_data,
            "location_data": product.collects_location_data,
        },
        "features": {
            "children_or_minors": product.children_related,
            "third_party_data_sharing": product.third_party_data_sharing,
            "cross_border_behavior": product.cross_border_data_transfer,
        },
        "controls": {
            "privacy_policy": product.has_privacy_policy,
            "third_party_sdk": product.uses_third_party_sdk,
        },
    }
    for group, values in booleans.items():
        for name, enabled in values.items():
            facts.append(_legacy_fact(group, name, True, present=bool(enabled)))
    facts.extend(
        _legacy_fact("vendors", str(vendor), str(vendor), present=True)
        for vendor in (product.third_party_sdks or [])
    )
    return facts


def load_product_context(db: Session, tenant_id: int, product_id: int) -> ProductContext:
    product = resolve_tenant_product(db, tenant_id, product_id)
    version = db.scalar(
        select(ProductTwinVersion)
        .where(ProductTwinVersion.product_id == product_id)
        .order_by(ProductTwinVersion.version_number.desc())
        .limit(1)
    )
    if version is not None:
        rows = db.scalars(
            select(ProductTwinFact)
            .where(ProductTwinFact.version_id == version.id)
            .order_by(ProductTwinFact.id)
        ).all()
        return _context(
            tenant_id, product_id, [_twin_fact(row) for row in rows], version=version, legacy=False
        )
    company = db.get(Company, tenant_id)
    assert company is not None  # ownership resolution already validated it
    return _context(
        tenant_id, product_id, _legacy_facts(product, company), version=None, legacy=True
    )


def load_product_context_version(db: Session, tenant_id: int, product_id: int, version_id: int) -> ProductContext:
    resolve_tenant_product(db, tenant_id, product_id)
    version = db.get(ProductTwinVersion, version_id)
    if not version or version.product_id != product_id:
        raise ValueError("Product Twin version does not belong to product")
    rows = db.scalars(select(ProductTwinFact).where(ProductTwinFact.version_id == version.id).order_by(ProductTwinFact.id)).all()
    return _context(tenant_id, product_id, [_twin_fact(row) for row in rows], version=version, legacy=False)
