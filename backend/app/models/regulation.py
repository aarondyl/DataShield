"""法规与法规条款模型。

条款（RegulationArticle）是 RAG 检索的最小单元：
- ``embedding`` 列在 PostgreSQL 下为 pgvector 的 Vector(dim)，SQLite 下为 JSON（见 models/types.py）。

Regulation 同时是全局法规智能层（regintel）的「逻辑法规」载体：
一部 Regulation 下辖多个 RegulationVersion（见 models/regulation_version.py），
版本管理遵循「Version, never overwrite」原则。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import embedding_type


class Regulation(Base):
    """法规档案（一部逻辑法规）。"""

    __tablename__ = "regulations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False, comment="法规名称")
    jurisdiction: Mapped[str] = mapped_column(String(50), default="", comment="法域，如 EU / CN / US-CA")
    description: Mapped[str] = mapped_column(Text, default="", comment="法规简介")
    source_url: Mapped[str] = mapped_column(String(500), default="", comment="官方来源链接")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="发布日期")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="生效日期")
    # ---- 全局法规智能层扩展字段 ----
    official_identifier: Mapped[str] = mapped_column(String(200), default="", comment="官方文号，如 Regulation (EU) 2016/679")
    title: Mapped[str] = mapped_column(String(500), default="", comment="法规完整官方标题")
    short_name: Mapped[str] = mapped_column(String(100), default="", comment="简称，如 GDPR / PIPL")
    authority: Mapped[str] = mapped_column(String(200), default="", comment="发布机关")
    document_type: Mapped[str] = mapped_column(String(50), default="", comment="law / regulation / directive 等")
    status: Mapped[str] = mapped_column(String(20), default="in_force", comment="in_force / repealed / pending")
    original_language: Mapped[str] = mapped_column(String(20), default="", comment="原始语言，如 ZH / EN")
    canonical_source_url: Mapped[str] = mapped_column(String(500), default="", comment="canonical 官方来源地址")
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="当前生效版本（regulation_versions.id）")
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
