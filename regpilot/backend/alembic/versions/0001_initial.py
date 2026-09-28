"""initial migration：全部业务表 + pgvector 扩展。

- PostgreSQL：``CREATE EXTENSION IF NOT EXISTS vector``，embedding 列为 ``vector(384)``；
- SQLite（本机降级）：embedding 列降级为 JSON，存 list[float]。

方言通过 ``op.get_bind().dialect.name`` 在迁移内判断，同一份迁移兼容两种后端。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
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
    if dialect == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("target_markets", sa.JSON(), nullable=True),
        sa.Column("business_model", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("target_markets", sa.JSON(), nullable=True),
        sa.Column("collects_personal_data", sa.Boolean(), nullable=True),
        sa.Column("collects_sensitive_data", sa.Boolean(), nullable=True),
        sa.Column("collects_health_data", sa.Boolean(), nullable=True),
        sa.Column("collects_location_data", sa.Boolean(), nullable=True),
        sa.Column("children_related", sa.Boolean(), nullable=True),
        sa.Column("third_party_data_sharing", sa.Boolean(), nullable=True),
        sa.Column("has_privacy_policy", sa.Boolean(), nullable=True),
        sa.Column("cross_border_data_transfer", sa.Boolean(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_products_company_id", "products", ["company_id"])

    op.create_table(
        "regulations",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("jurisdiction", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("effective_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )

    op.create_table(
        "regulation_articles",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("regulation_id", sa.Integer(), sa.ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("article_number", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=True),
        _embedding_column(dialect),
    )
    op.create_index("ix_regulation_articles_regulation_id", "regulation_articles", ["regulation_id"])

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("regulation_id", sa.Integer(), sa.ForeignKey("regulations.id"), nullable=True),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("llm_mode", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_analysis_runs_company_id", "analysis_runs", ["company_id"])
    op.create_index("ix_analysis_runs_product_id", "analysis_runs", ["product_id"])

    op.create_table(
        "impact_results",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relevant", sa.Boolean(), nullable=True),
        sa.Column("risk_level", sa.String(length=10), nullable=True),
        sa.Column("affected_products", sa.JSON(), nullable=True),
        sa.Column("affected_areas", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.String(length=10), nullable=True),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_impact_results_run_id", "impact_results", ["run_id"], unique=True)

    op.create_table(
        "compliance_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=True),
        sa.Column("department", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_compliance_actions_run_id", "compliance_actions", ["run_id"])

    op.create_table(
        "chat_threads",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"])

    op.create_table(
        "agent_memories",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        _embedding_column(dialect),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("agent_memories")
    op.drop_index("ix_chat_messages_thread_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_table("chat_threads")
    op.drop_index("ix_compliance_actions_run_id", table_name="compliance_actions")
    op.drop_table("compliance_actions")
    op.drop_index("ix_impact_results_run_id", table_name="impact_results")
    op.drop_table("impact_results")
    op.drop_index("ix_analysis_runs_product_id", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_company_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_index("ix_regulation_articles_regulation_id", table_name="regulation_articles")
    op.drop_table("regulation_articles")
    op.drop_table("regulations")
    op.drop_index("ix_products_company_id", table_name="products")
    op.drop_table("products")
    op.drop_table("companies")
