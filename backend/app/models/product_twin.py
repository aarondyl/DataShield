"""Append-only Product Twin snapshots and immutable analysis references."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductTwinVersion(Base):
    __tablename__ = "product_twin_versions"
    __table_args__ = (UniqueConstraint("product_id", "version_number", name="uq_product_twin_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    source_analysis_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProductTwinAnalysisRef(Base):
    __tablename__ = "product_twin_analysis_refs"

    analysis_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    scan_scope: Mapped[dict] = mapped_column(JSON, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProductTwinFact(Base):
    __tablename__ = "product_twin_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("product_twin_versions.id", ondelete="CASCADE"), index=True)
    group_name: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    analysis_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("product_twin_analysis_refs.analysis_id", ondelete="RESTRICT"), nullable=True
    )
    evidence: Mapped[list] = mapped_column(JSON, nullable=False)
    scan_scope: Mapped[dict] = mapped_column(JSON, nullable=False)
    confirmation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNREVIEWED")
    supersedes_fact_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ProductTwinDecision(Base):
    __tablename__ = "product_twin_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("product_twin_versions.id", ondelete="CASCADE"))
    fact_id: Mapped[int] = mapped_column(ForeignKey("product_twin_facts.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    actor_label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
