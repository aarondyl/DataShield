"""全局法规智能层：法律 chunk（pgvector 向量索引的载体）。

chunk 按法律结构切分（优先 article，过长时按 paragraph 细分），
旧版本 chunk 在新版本生效后置为 ``is_active = false``，永不删除。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.types import embedding_type


class LegalChunk(Base):
    """一条可检索的法律文本 chunk（含向量与追溯元数据）。"""

    __tablename__ = "legal_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    regulation_id: Mapped[int] = mapped_column(
        ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[int] = mapped_column(
        ForeignKey("regulation_versions.id", ondelete="CASCADE"), nullable=False, index=True,
        comment="生成该 chunk 内容的版本",
    )
    legal_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("legal_units.id", ondelete="SET NULL"), nullable=True, comment="来源法律单元"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="chunk 文本")
    embedding: Mapped[list[float] | None] = mapped_column(embedding_type(), nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(100), default="", comment="生成向量的模型/provider 标识")
    token_count: Mapped[int] = mapped_column(Integer, default=0, comment="chunk 字符数（近似 token 量）")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, comment="jurisdiction/article/version/effective_from 等检索元数据")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="false 表示已被新版本 chunk 取代")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
