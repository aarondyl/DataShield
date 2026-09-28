"""法规与法规条款模型。

条款（RegulationArticle）是 RAG 检索的最小单元：
- ``embedding`` 列在 PostgreSQL 下为 pgvector 的 Vector(dim)，SQLite 下为 JSON（见 models/types.py）。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import embedding_type


class Regulation(Base):
    """法规档案。"""

    __tablename__ = "regulations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False, comment="法规名称")
    jurisdiction: Mapped[str] = mapped_column(String(50), default="", comment="法域，如 EU / CN / US-CA")
    description: Mapped[str] = mapped_column(Text, default="", comment="法规简介")
    source_url: Mapped[str] = mapped_column(String(500), default="", comment="官方来源链接")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="发布日期")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="生效日期")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    articles: Mapped[list["RegulationArticle"]] = relationship(
        back_populates="regulation", cascade="all, delete-orphan"
    )


class RegulationArticle(Base):
    """法规条款（含向量）。"""

    __tablename__ = "regulation_articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    regulation_id: Mapped[int] = mapped_column(
        ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    article_number: Mapped[str] = mapped_column(String(50), nullable=False, comment="条款号，如 第九条 / Article 9")
    title: Mapped[str] = mapped_column(String(300), default="", comment="条款标题")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="条款正文（或长条款切分后的片段）")
    topic: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="主题标签，如 跨境传输")
    embedding: Mapped[list[float] | None] = mapped_column(embedding_type(), nullable=True, comment="条款向量")

    regulation: Mapped[Regulation] = relationship(back_populates="articles")
