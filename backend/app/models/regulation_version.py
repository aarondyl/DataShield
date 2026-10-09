"""全局法规智能层：法规版本 / 法律结构单元。

对应任务书中的 ``regulation_versions`` / ``legal_units`` 两张表。
原则：**Version, never overwrite** —— 新版本绝不覆盖旧版本，旧版本整棵结构树保留。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RegulationVersion(Base):
    """法规的一个历史版本（含抓取到的规范化全文与内容哈希）。"""

    __tablename__ = "regulation_versions"
    __table_args__ = (UniqueConstraint("regulation_id", "version_number", name="uq_version_reg_no"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    regulation_id: Mapped[int] = mapped_column(
        ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, comment="版本号，从 1 递增")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="官方发布时间")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="生效时间")
    effective_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="失效时间（被新版本取代时回填）")
    source_url: Mapped[str] = mapped_column(String(500), default="", comment="本版本抓取地址")
    raw_document_uri: Mapped[str] = mapped_column(String(500), default="", comment="原始快照文件路径")
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False, comment="规范化后的全文")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, comment="SHA256(normalized_text)，用于版本检测")
    review_status: Mapped[str] = mapped_column(
        String(32), default="UNREVIEWED", nullable=False,
        comment="法律内容审核状态；自动抓取不得标记为已人工核验",
    )
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="抓取入库时间")
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否为当前生效版本")


class LegalUnit(Base):
    """法律结构单元：chapter / section / article / paragraph，按版本组成树。"""

    __tablename__ = "legal_units"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("regulation_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("legal_units.id", ondelete="SET NULL"), nullable=True, comment="父单元（如 article 的父为 chapter）"
    )
    unit_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="chapter / section / article / paragraph")
    unit_number: Mapped[str] = mapped_column(String(50), default="", comment="单元编号，如 第十三条 / Article 13")
    heading: Mapped[str] = mapped_column(String(500), default="", comment="单元标题（中英文章节/条款标题）")
    text: Mapped[str] = mapped_column(Text, default="", comment="该单元自身文本（article 含其下全部款项）")
    path: Mapped[str] = mapped_column(String(500), default="", comment="结构路径，如 第二章/第一节/第十三条")
    order_index: Mapped[int] = mapped_column(Integer, default=0, comment="同版本内的全局顺序")
