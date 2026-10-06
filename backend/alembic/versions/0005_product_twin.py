"""Product Twin snapshots and product-linked understanding jobs.

The understanding job table predates Alembic and may already exist. Adopt it
without discarding stored jobs; new deployments create it through this migration.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "product_understanding_jobs" not in tables:
        op.create_table(
            "product_understanding_jobs",
            sa.Column("analysis_id", sa.String(64), primary_key=True),
            sa.Column("owner", sa.String(64), nullable=False),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("created_at", sa.String(40), nullable=False),
            sa.Column("updated_at", sa.String(40), nullable=False),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        )
    elif "product_id" not in {c["name"] for c in sa.inspect(bind).get_columns("product_understanding_jobs")}:
        with op.batch_alter_table("product_understanding_jobs") as batch:
            batch.add_column(sa.Column("product_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_understanding_job_product", "products", ["product_id"], ["id"], ondelete="SET NULL")
    if not any(i["name"] == "ix_understanding_jobs_product_id" for i in sa.inspect(bind).get_indexes("product_understanding_jobs")):
        op.create_index("ix_understanding_jobs_product_id", "product_understanding_jobs", ["product_id"])

    op.create_table(
        "product_twin_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("source_analysis_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("product_id", "version_number", name="uq_product_twin_version"),
    )
    op.create_index("ix_product_twin_versions_product_id", "product_twin_versions", ["product_id"])
    op.create_table(
        "product_twin_analysis_refs",
        sa.Column("analysis_id", sa.String(64), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("result_sha256", sa.String(64), nullable=False),
        sa.Column("scan_scope", sa.JSON(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_product_twin_analysis_refs_product_id", "product_twin_analysis_refs", ["product_id"])
    op.create_table(
        "product_twin_facts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version_id", sa.Integer(), sa.ForeignKey("product_twin_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_name", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_kind", sa.String(20), nullable=False),
        sa.Column("analysis_id", sa.String(64), sa.ForeignKey("product_twin_analysis_refs.analysis_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("scan_scope", sa.JSON(), nullable=False),
        sa.Column("confirmation_status", sa.String(20), nullable=False),
        sa.Column("supersedes_fact_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_product_twin_facts_version_id", "product_twin_facts", ["version_id"])
    op.create_table(
        "product_twin_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.Integer(), sa.ForeignKey("product_twin_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fact_id", sa.Integer(), sa.ForeignKey("product_twin_facts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("note", sa.String(1000), nullable=False),
        sa.Column("actor_label", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_product_twin_decisions_product_id", "product_twin_decisions", ["product_id"])


def downgrade() -> None:
    op.drop_table("product_twin_decisions")
    op.drop_table("product_twin_facts")
    op.drop_table("product_twin_analysis_refs")
    op.drop_table("product_twin_versions")
    op.drop_index("ix_understanding_jobs_product_id", table_name="product_understanding_jobs")
    # Keep the pre-existing jobs table and its data when reverting this feature.
    with op.batch_alter_table("product_understanding_jobs") as batch:
        batch.drop_column("product_id")
