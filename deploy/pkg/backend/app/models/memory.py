"""Agent 记忆模型（当前版本仅建表预留，向量列同样按方言切换）。"""

from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.types import embedding_type


class AgentMemory(Base):
    """Agent 长期记忆条目（预留）。"""

    __tablename__ = "agent_memories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="记忆内容")
    embedding: Mapped[list[float] | None] = mapped_column(embedding_type(), nullable=True, comment="记忆向量")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
