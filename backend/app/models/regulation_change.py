"""全局法规智能层：条级变化记录 / 法规变化事件。

对应任务书中的 ``regulation_changes`` 表与 ``regulation.change.ready`` 事件。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: 条级变化类型
CHANGE_TYPES = ("ADDED", "MODIFIED", "REMOVED", "RENUMBERED")
#: 变化重要性分级
MATERIALITY_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
#: 向量索引就绪后才允许发布的事件类型
EVENT_TYPE_CHANGE_READY = "regulation.change.ready"


class RegulationChange(Base):
    """两个版本之间的一条法律单元级变化。"""

    __tablename__ = "regulation_changes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    regulation_id: Mapped[int] = mapped_column(
        ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("regulation_versions.id", ondelete="SET NULL"), nullable=True
    )
    to_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("regulation_versions.id", ondelete="SET NULL"), nullable=True
    )
    legal_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("legal_units.id", ondelete="SET NULL"), nullable=True, comment="涉及的法律单元（新版本侧）"
    )
    change_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="ADDED / MODIFIED / REMOVED / RENUMBERED")
    old_text: Mapped[str] = mapped_column(Text, default="", comment="旧文本（ADDED 时为空）")
    new_text: Mapped[str] = mapped_column(Text, default="", comment="新文本（REMOVED 时为空）")
    semantic_summary: Mapped[str] = mapped_column(Text, default="", comment="变化的语义摘要（LLM 或规则生成）")
    materiality: Mapped[str] = mapped_column(String(10), default="LOW", comment="LOW / MEDIUM / HIGH / CRITICAL")
    requirement_ids: Mapped[list] = mapped_column(JSON, default=list, comment="本次变化新提取的 requirement id 列表")
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RegulationEvent(Base):
    """已发布的法规变化事件（仅当数据库/义务/向量索引全部就绪后发布）。"""

    __tablename__ = "regulation_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment="对外事件 id，如 evt_000001")
    event_type: Mapped[str] = mapped_column(String(50), default=EVENT_TYPE_CHANGE_READY)
    schema_version: Mapped[str] = mapped_column(String(10), default="1.0")
    regulation_id: Mapped[int | None] = mapped_column(
        ForeignKey("regulations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    version_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="变化产生的新版本")
    payload: Mapped[dict] = mapped_column(JSON, default=dict, comment="完整事件报文（regulation.change.ready 标准结构）")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
