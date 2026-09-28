"""合规整改动作模型。"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ComplianceAction(Base):
    """由影响分析结果推导出的合规整改动作。"""

    __tablename__ = "compliance_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False, comment="动作标题")
    priority: Mapped[str] = mapped_column(String(10), default="medium", comment="low / medium / high")
    department: Mapped[str] = mapped_column(
        String(50),
        default="Legal",
        comment="责任部门：Legal / Product / Engineering / Security / Operations / Supply Chain / Management",
    )
    description: Mapped[str] = mapped_column(Text, default="", comment="动作详细说明")
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="支撑证据 {regulation, article}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    run: Mapped["AnalysisRun"] = relationship(back_populates="actions")  # noqa: F821
