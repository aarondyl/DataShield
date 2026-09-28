"""对话线程与消息模型（当前版本仅建表预留）。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatThread(Base):
    """对话线程（预留）。"""

    __tablename__ = "chat_threads"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    """对话消息（预留）。"""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="user / assistant / system")
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    thread: Mapped[ChatThread] = relationship(back_populates="messages")
