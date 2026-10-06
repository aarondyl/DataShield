"""regintel migration：全局法规智能层的 8 张新表 + regulations 扩展列。

- PostgreSQL：legal_chunks.embedding 为 ``vector(384)``（pgvector）；
- SQLite（本机降级）：embedding 列降级为 JSON，存 list[float]。

新表：regulatory_sources / source_snapshots / ingestion_runs /
regulation_versions / legal_units / requirements / regulation_changes /
regulation_events / legal_chunks。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 向量维度（与 .env 的 EMBEDDING_DIM 默认值一致）
_EMBEDDING_DIM = 384


def _embedding_column(dialect: str) -> sa.Column:
    """按方言构造 embedding 列：pg 用 pgvector Vector，其余用 JSON。"""
    if dialect == "postgresql":
        from pgvector.sqlalchemy import Vector

        return sa.Column("embedding", Vector(_EMBEDDING_DIM), nullable=True)
    return sa.Column("embedding", sa.JSON(), nullable=True)


def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    # ---- regulations 表扩展列（全局法规智能层元数据）----
    with op.batch_alter_table("regulations") as batch:
        batch.add_column(sa.Column("official_identifier", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("title", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("short_name", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("authority", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("document_type", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("status", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("original_language", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("canonical_source_url", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("current_version_id", sa.Integer(), nullable=True))

    op.create_table(
        "regulatory_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("regulation_id", sa.Integer(), sa.ForeignKey("regulations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("jurisdiction", sa.String(length=50), nullable=True),
        sa.Column("authority", sa.String(length=200), nullable=True),
        sa.Column("source_name", sa.String(length=200), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("fetch_url", sa.String(length=500), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=True),
        sa.Column("parser_type", sa.String(length=50), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("polling_interval", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_regulatory_sources_regulation_id", "regulatory_sources", ["regulation_id"])

    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("regulatory_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("regulation_id", sa.Integer(), sa.ForeignKey("regulations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("snapshot_uri", sa.String(length=500), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content_length", sa.Integer(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_source_snapshots_source_id", "source_snapshots", ["source_id"])
    op.create_index("ix_source_snapshots_regulation_id", "source_snapshots", ["regulation_id"])

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("regulatory_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("regulation_id", sa.Integer(), sa.ForeignKey("regulations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("from_version_id", sa.Integer(), nullable=True),
        sa.Column("to_version_id", sa.Integer(), nullable=True),
        sa.Column("changes_count", sa.Integer(), nullable=True),
        sa.Column("requirements_count", sa.Integer(), nullable=True),
        sa.Column("chunks_count", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_ingestion_runs_source_id", "ingestion_runs", ["source_id"])
    op.create_index("ix_ingestion_runs_regulation_id", "ingestion_runs", ["regulation_id"])

    op.create_table(
        "regulation_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("regulation_id", sa.Integer(), sa.ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("effective_from", sa.DateTime(), nullable=True),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("raw_document_uri", sa.String(length=500), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=True),
        sa.UniqueConstraint("regulation_id", "version_number", name="uq_version_reg_no"),
    )
    op.create_index("ix_regulation_versions_regulation_id", "regulation_versions", ["regulation_id"])

    op.create_table(
        "legal_units",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("version_id", sa.Integer(), sa.ForeignKey("regulation_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_unit_id", sa.Integer(), sa.ForeignKey("legal_units.id", ondelete="SET NULL"), nullable=True),
        sa.Column("unit_type", sa.String(length=20), nullable=False),
        sa.Column("unit_number", sa.String(length=50), nullable=True),
        sa.Column("heading", sa.String(length=500), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("path", sa.String(length=500), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=True),
    )
    op.create_index("ix_legal_units_version_id", "legal_units", ["version_id"])

    op.create_table(
        "requirements",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("regulation_id", sa.Integer(), sa.ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.Integer(), sa.ForeignKey("regulation_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("legal_unit_id", sa.Integer(), sa.ForeignKey("legal_units.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requirement_type", sa.String(length=20), nullable=True),
        sa.Column("subject_type", sa.String(length=100), nullable=True),
        sa.Column("action_type", sa.String(length=100), nullable=True),
        sa.Column("object_type", sa.String(length=100), nullable=True),
        sa.Column("conditions_json", sa.JSON(), nullable=True),
        sa.Column("exceptions_json", sa.JSON(), nullable=True),
        sa.Column("summary", sa.String(length=1000), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("effective_from", sa.DateTime(), nullable=True),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_requirements_regulation_id", "requirements", ["regulation_id"])
    op.create_index("ix_requirements_version_id", "requirements", ["version_id"])

    op.create_table(
        "regulation_changes",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("regulation_id", sa.Integer(), sa.ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_version_id", sa.Integer(), sa.ForeignKey("regulation_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("to_version_id", sa.Integer(), sa.ForeignKey("regulation_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("legal_unit_id", sa.Integer(), sa.ForeignKey("legal_units.id", ondelete="SET NULL"), nullable=True),
        sa.Column("change_type", sa.String(length=20), nullable=False),
        sa.Column("old_text", sa.Text(), nullable=True),
        sa.Column("new_text", sa.Text(), nullable=True),
        sa.Column("semantic_summary", sa.Text(), nullable=True),
        sa.Column("materiality", sa.String(length=10), nullable=True),
        sa.Column("requirement_ids", sa.JSON(), nullable=True),
        sa.Column("detected_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_regulation_changes_regulation_id", "regulation_changes", ["regulation_id"])

    op.create_table(
        "regulation_events",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("event_id", sa.String(length=50), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=True),
        sa.Column("schema_version", sa.String(length=10), nullable=True),
        sa.Column("regulation_id", sa.Integer(), sa.ForeignKey("regulations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_regulation_events_regulation_id", "regulation_events", ["regulation_id"])

    op.create_table(
        "legal_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("regulation_id", sa.Integer(), sa.ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.Integer(), sa.ForeignKey("regulation_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("legal_unit_id", sa.Integer(), sa.ForeignKey("legal_units.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        _embedding_column(dialect),
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_legal_chunks_regulation_id", "legal_chunks", ["regulation_id"])
    op.create_index("ix_legal_chunks_version_id", "legal_chunks", ["version_id"])


def downgrade() -> None:
    op.drop_table("legal_chunks")
    op.drop_table("regulation_events")
    op.drop_table("regulation_changes")
    op.drop_table("requirements")
    op.drop_table("legal_units")
    op.drop_table("regulation_versions")
    op.drop_table("ingestion_runs")
    op.drop_table("source_snapshots")
    op.drop_table("regulatory_sources")
    with op.batch_alter_table("regulations") as batch:
        for column in (
            "official_identifier", "title", "short_name", "authority", "document_type",
            "status", "original_language", "canonical_source_url", "current_version_id",
        ):
            batch.drop_column(column)
