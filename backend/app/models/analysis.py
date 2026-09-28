"""分析运行与影响结果模型。"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnalysisRun(Base):
    """一次法规影响分析的运行记录。"""

    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    regulation_id: Mapped[int | None] = mapped_column(
        ForeignKey("regulations.id"), nullable=True, comment="指定分析的法规；为空则全库检索"
    )
    query: Mapped[str] = mapped_column(Text, default="", comment="用户分析问题")
    status: Mapped[str] = mapped_column(
        String(20), default="pending", comment="pending / running / completed / failed"
    )
    llm_mode: Mapped[str] = mapped_column(String(20), default="", comment="实际生效的 LLM provider：api / mock")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    impact_result: Mapped["ImpactResult | None"] = relationship(
        back_populates="run", cascade="all, delete-orphan", uselist=False
    )
    actions: Mapped[list["ComplianceAction"]] = relationship(  # noqa: F821
        back_populates="run", cascade="all, delete-orphan"
    )


class ImpactResult(Base):
    """影响分析结构化结果（一次运行一条）。"""

    __tablename__ = "impact_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    relevant: Mapped[bool | None] = mapped_column(Boolean, nullable=True, comment="是否相关；证据不足时为 NULL")
    risk_level: Mapped[str] = mapped_column(String(10), default="low", comment="low / medium / high")
    affected_products: Mapped[list] = mapped_column(JSON, default=list, comment="受影响产品名称列表")
    affected_areas: Mapped[list] = mapped_column(JSON, default=list, comment="受影响业务领域列表")
    summary: Mapped[str] = mapped_column(Text, default="", comment="影响摘要")
    reasoning_summary: Mapped[str] = mapped_column(Text, default="", comment="推理过程摘要")
    evidence: Mapped[list] = mapped_column(JSON, default=list, comment="证据列表（含 content/source_url/verified）")
    confidence: Mapped[str] = mapped_column(String(10), default="low", comment="high / medium / low")

    run: Mapped[AnalysisRun] = relationship(back_populates="impact_result")
