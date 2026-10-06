"""Persistence models for Tenant Intelligence runs, findings and traceability."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TenantAgentRun(Base):
    __tablename__ = "tenant_agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','RUNNING','COMPLETED','NEEDS_USER_INPUT','FAILED')",
            name="ck_tenant_agent_runs_status",
        ),
        Index("ix_tenant_agent_runs_trigger_type", "trigger_type"),
        Index("ix_tenant_agent_runs_trigger_id", "trigger_id"),
        Index("ix_tenant_agent_runs_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    model_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    findings: Mapped[list["Finding"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    missing_context: Mapped[list["TenantMissingContextItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint("status IN ('OPEN','DISMISSED','RESOLVED')", name="ck_findings_status"),
        CheckConstraint(
            "impact_level IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_findings_impact_level",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_findings_confidence"),
        Index("ix_findings_status", "status"),
        Index("ix_findings_impact_level", "impact_level"),
        Index("ix_findings_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("tenant_agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    impact_level: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    applicability_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    gap_status: Mapped[str] = mapped_column(String(20), nullable=False)
    gap_type: Mapped[str] = mapped_column(String(40), nullable=False)
    gap_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    product_twin_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_twin_versions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    run: Mapped[TenantAgentRun] = relationship(back_populates="findings")
    requirement_links: Mapped[list["FindingRequirement"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )
    evidence_links: Mapped[list["FindingEvidence"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )


class FindingRequirement(Base):
    __tablename__ = "finding_requirements"
    __table_args__ = (
        UniqueConstraint("finding_id", "requirement_id", name="uq_finding_requirement"),
        Index("ix_finding_requirements_requirement_id", "requirement_id"),
    )

    finding_id: Mapped[int] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), primary_key=True
    )
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id", ondelete="RESTRICT"), primary_key=True
    )

    finding: Mapped[Finding] = relationship(back_populates="requirement_links")


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"
    __table_args__ = (
        Index("ix_finding_evidence_finding_id", "finding_id"),
        Index("ix_finding_evidence_legal_unit_id", "legal_unit_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
    )
    legal_unit_id: Mapped[int] = mapped_column(
        ForeignKey("legal_units.id", ondelete="RESTRICT"), nullable=False
    )
    requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="RESTRICT"), nullable=True
    )
    evidence_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    finding: Mapped[Finding] = relationship(back_populates="evidence_links")


class TenantMissingContextItem(Base):
    __tablename__ = "tenant_missing_context_items"
    __table_args__ = (
        CheckConstraint("status IN ('OPEN')", name="ck_tenant_missing_context_status"),
        Index("ix_tenant_missing_context_run_id", "run_id"),
        Index("ix_tenant_missing_context_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("tenant_agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True
    )
    field_path: Mapped[str] = mapped_column(String(200), nullable=False)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    run: Mapped[TenantAgentRun] = relationship(back_populates="missing_context")
