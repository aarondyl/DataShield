"""Stable Product Twin context consumed by Tenant Intelligence."""

from typing import Any

from pydantic import Field

from app.understanding.schemas import Confidence, Contract, FindingStatus


class ProductFactContext(Contract):
    fact_id: int | None = None
    group: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    status: FindingStatus
    value: Any = None
    source: str = Field(min_length=1, max_length=30)
    confidence: Confidence
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    scan_scope: dict[str, Any] = Field(default_factory=dict)
    review_status: str = Field(min_length=1, max_length=30)
    is_user_confirmed: bool = False
    supersedes_fact_id: int | None = None


class ProductFactConflict(Contract):
    group: str
    name: str
    fact_ids: list[int] = Field(default_factory=list)
    statuses: list[FindingStatus] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class ProductContext(Contract):
    tenant_id: int = Field(ge=1)
    product_id: int = Field(ge=1)
    product_twin_version_id: int | None = None
    product_twin_version_number: int | None = None
    facts: list[ProductFactContext] = Field(default_factory=list)
    markets: list[ProductFactContext] = Field(default_factory=list)
    product_categories: list[ProductFactContext] = Field(default_factory=list)
    target_users: list[ProductFactContext] = Field(default_factory=list)
    features: list[ProductFactContext] = Field(default_factory=list)
    data_types: list[ProductFactContext] = Field(default_factory=list)
    vendors: list[ProductFactContext] = Field(default_factory=list)
    controls: list[ProductFactContext] = Field(default_factory=list)
    conflicts: list[ProductFactConflict] = Field(default_factory=list)
    used_legacy_fallback: bool = False
