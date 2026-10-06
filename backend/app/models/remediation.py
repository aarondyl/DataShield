"""Persistence models for immutable remediation plans and canonical traceability."""

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Remediation(Base):
    __tablename__ = "remediations"
    __table_args__ = (
        CheckConstraint(
            "remediation_type IN ('CODE_CHANGE','DOCUMENT_CHANGE')",
            name="ck_remediations_type",
        ),
        CheckConstraint(
            "status IN ('PROPOSED','APPROVED','REJECTED')",
            name="ck_remediations_status",
        ),
        Index("ix_remediations_status", "status"),
        Index("ix_remediations_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    remediation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PROPOSED")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    product_twin_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_twin_versions.id", ondelete="SET NULL"), nullable=True
    )
    model_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    requirement_links: Mapped[list["RemediationRequirement"]] = relationship(
        back_populates="remediation", cascade="all, delete-orphan"
    )
    evidence_links: Mapped[list["RemediationEvidence"]] = relationship(
        back_populates="remediation", cascade="all, delete-orphan"
    )


class RemediationRequirement(Base):
    __tablename__ = "remediation_requirements"
    __table_args__ = (
        UniqueConstraint(
            "remediation_id", "requirement_id", name="uq_remediation_requirement"
        ),
        Index("ix_remediation_requirements_requirement_id", "requirement_id"),
    )

    remediation_id: Mapped[int] = mapped_column(
        ForeignKey("remediations.id", ondelete="CASCADE"), primary_key=True
    )
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id", ondelete="RESTRICT"), primary_key=True
    )

    remediation: Mapped[Remediation] = relationship(back_populates="requirement_links")


class RemediationEvidence(Base):
    __tablename__ = "remediation_evidence"
    __table_args__ = (
        Index("ix_remediation_evidence_legal_unit_id", "legal_unit_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    remediation_id: Mapped[int] = mapped_column(
        ForeignKey("remediations.id", ondelete="CASCADE"), nullable=False
    )
    legal_unit_id: Mapped[int] = mapped_column(
        ForeignKey("legal_units.id", ondelete="RESTRICT"), nullable=False
    )
    requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirements.id", ondelete="RESTRICT"), nullable=True
    )
    evidence_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    remediation: Mapped[Remediation] = relationship(back_populates="evidence_links")
