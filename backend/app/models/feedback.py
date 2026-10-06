"""Immutable feedback and reviewable candidate persistence."""
from datetime import datetime
from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (CheckConstraint("feedback_type IN ('FACT_CORRECTION','FINDING_FEEDBACK','REMEDIATION_FEEDBACK')", name="ck_feedback_type"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[int | None] = mapped_column(ForeignKey("findings.id", ondelete="RESTRICT"), index=True)
    remediation_id: Mapped[int | None] = mapped_column(ForeignKey("remediations.id", ondelete="RESTRICT"), index=True)
    feedback_type: Mapped[str] = mapped_column(String(30), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    useful: Mapped[bool | None] = mapped_column(Boolean)
    negative_reason: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    candidates: Mapped[list["FeedbackCandidate"]] = relationship(back_populates="feedback", cascade="all, delete-orphan")


class FeedbackCandidate(Base):
    __tablename__ = "feedback_candidates"
    __table_args__ = (
        CheckConstraint("candidate_type IN ('FACT_CORRECTION','FINDING_FEEDBACK','REMEDIATION_FEEDBACK')", name="ck_feedback_candidate_type"),
        CheckConstraint("status IN ('PROPOSED','NEEDS_CLARIFICATION','CONFIRMED','REJECTED','APPLIED')", name="ck_feedback_candidate_status"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_feedback_candidate_confidence"),
        Index("ix_feedback_candidates_status", "status"), Index("ix_feedback_candidates_type", "candidate_type"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback.id", ondelete="CASCADE"), index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    candidate_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    target_fact_id: Mapped[int | None] = mapped_column(ForeignKey("product_twin_facts.id", ondelete="RESTRICT"))
    proposed_name: Mapped[str | None] = mapped_column(String(200))
    proposed_value: Mapped[object | None] = mapped_column(JSON)
    proposed_status: Mapped[str | None] = mapped_column(String(20))
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    clarification_question: Mapped[str | None] = mapped_column(String(1000))
    clarification_answer: Mapped[str | None] = mapped_column(Text)
    applied_fact_id: Mapped[int | None] = mapped_column(ForeignKey("product_twin_facts.id", ondelete="RESTRICT"))
    applied_twin_version_id: Mapped[int | None] = mapped_column(ForeignKey("product_twin_versions.id", ondelete="RESTRICT"))
    reanalysis_run_id: Mapped[int | None] = mapped_column(ForeignKey("tenant_agent_runs.id", ondelete="RESTRICT"))
    last_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    feedback: Mapped[Feedback] = relationship(back_populates="candidates")


class FeedbackCandidateRequirement(Base):
    __tablename__ = "feedback_candidate_requirements"
    candidate_id: Mapped[int] = mapped_column(ForeignKey("feedback_candidates.id", ondelete="CASCADE"), primary_key=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id", ondelete="RESTRICT"), primary_key=True, index=True)
