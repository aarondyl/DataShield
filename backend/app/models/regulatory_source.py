"""全局法规智能层：官方监管来源 / 原始快照 / 入库运行记录。

对应任务书中的 ``regulatory_sources`` / ``source_snapshots`` / ``ingestion_runs`` 三张表。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RegulatorySource(Base):
    """一个官方监管来源（canonical source，如 EUR-Lex / 中国人大网）。"""

    __tablename__ = "regulatory_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    regulation_id: Mapped[int | None] = mapped_column(
        ForeignKey("regulations.id", ondelete="SET NULL"), nullable=True, index=True, comment="该来源产出的法规"
    )
    jurisdiction: Mapped[str] = mapped_column(String(50), default="", comment="法域，如 EU / CN")
    authority: Mapped[str] = mapped_column(String(200), default="", comment="发布/主管机关")
    source_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="来源名称，如 EUR-Lex / 中国人大网")
    base_url: Mapped[str] = mapped_column(String(500), default="", comment="来源面向公众的官方地址")
    fetch_url: Mapped[str] = mapped_column(String(500), default="", comment="实际抓取地址（http(s):// 或 file:// 快照路径）")
    source_type: Mapped[str] = mapped_column(String(20), default="local_file", comment="html / pdf / rss / api / index_page / local_file")
    parser_type: Mapped[str] = mapped_column(String(50), default="cn_law", comment="结构解析器：cn_law / gdpr_bilingual")
    priority: Mapped[int] = mapped_column(Integer, default=10, comment="抓取优先级，数值越小越优先")
    polling_interval: Mapped[int] = mapped_column(Integer, default=86400, comment="轮询间隔（秒）")
    is_active: Mapped[bool] = mapped_column(default=True, comment="是否参与定时轮询")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最近一次抓取时间")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最近一次成功抓取时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SourceSnapshot(Base):
    """抓取响应原始字节的持久快照；内容解析使用规范化文本。"""

    __tablename__ = "source_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("regulatory_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    regulation_id: Mapped[int | None] = mapped_column(
        ForeignKey("regulations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    snapshot_uri: Mapped[str] = mapped_column(String(500), default="", comment="原始响应快照文件路径")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, comment="规范化文本的 SHA256")
    raw_content_hash: Mapped[str] = mapped_column(
        String(64), default="", server_default="", nullable=False,
        comment="抓取响应原始字节的 SHA256",
    )
    content_length: Mapped[int] = mapped_column(Integer, default=0, comment="快照字节数")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="抓取时间")


class IngestionRun(Base):
    """一次法规入库/更新流水线的运行记录。"""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("regulatory_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    regulation_id: Mapped[int | None] = mapped_column(
        ForeignKey("regulations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="RUNNING", comment="RUNNING / NO_CHANGE / COMPLETED / FAILED")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    from_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="变更前版本")
    to_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="生成的新版本")
    changes_count: Mapped[int] = mapped_column(Integer, default=0, comment="检测到的条级变化数")
    requirements_count: Mapped[int] = mapped_column(Integer, default=0, comment="本次新提取的义务单元数")
    chunks_count: Mapped[int] = mapped_column(Integer, default=0, comment="本次新生成的 chunk 数")
    error: Mapped[str] = mapped_column(Text, default="", comment="失败原因")
    event_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="发布的 regulation.change.ready 事件")
