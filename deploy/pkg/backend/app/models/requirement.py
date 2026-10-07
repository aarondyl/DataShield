"""全局法规智能层：结构化义务单元（Requirement）。

法律文本进一步转化为「什么主体在什么条件下需要做什么」的结构化义务，
供 User Agent 消费。置信度低于阈值的结果标记为 NEEDS_REVIEW，不静默当成确定事实。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: 置信度阈值：低于该值的提取结果标记为 NEEDS_REVIEW
CONFIDENCE_REVIEW_THRESHOLD = 0.7


class Requirement(Base):
    """一条结构化法律义务单元。"""

    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    regulation_id: Mapped[int] = mapped_column(
        ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[int] = mapped_column(
        ForeignKey("regulation_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    legal_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("legal_units.id", ondelete="SET NULL"), nullable=True, comment="来源条款"
    )
    requirement_type: Mapped[str] = mapped_column(
        String(20), default="obligation", comment="obligation / prohibition / right / permission"
    )
    subject_type: Mapped[str] = mapped_column(String(100), default="", comment="义务主体，如 个人信息处理者 / controller")
    action_type: Mapped[str] = mapped_column(String(100), default="", comment="动作类型，如 inform / obtain_consent / delete")
    object_type: Mapped[str] = mapped_column(String(100), default="", comment="作用对象，如 个人信息 / personal_data")
    conditions_json: Mapped[list] = mapped_column(JSON, default=list, comment="适用条件列表")
    exceptions_json: Mapped[list] = mapped_column(JSON, default=list, comment="例外情形列表")
    summary: Mapped[str] = mapped_column(String(1000), default="", comment="义务的一句话摘要")
    confidence: Mapped[float] = mapped_column(Float, default=0.0, comment="提取置信度 0-1")
    status: Mapped[str] = mapped_column(
        String(20), default="ACTIVE", comment="ACTIVE / NEEDS_REVIEW / SUPERSEDED（被新版本取代）"
    )
    effective_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
