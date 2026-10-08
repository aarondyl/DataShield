"""本地法规同步后的待评估任务；同步与评估分属独立事务。"""
from sqlalchemy import DateTime, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class LocalReevaluationTask(Base):
    __tablename__ = "local_reevaluation_tasks"
    __table_args__ = (UniqueConstraint("event_id", "product_id", name="uq_local_reevaluation_event_product"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class LocalRegulationBinding(Base):
    """云端稳定键与本地 ORM 主键的显式映射。"""
    __tablename__ = "local_regulation_bindings"
    __table_args__ = (UniqueConstraint("entity_type", "entity_key", name="uq_local_regulation_binding"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_key: Mapped[str] = mapped_column(String(512), nullable=False)
    local_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
