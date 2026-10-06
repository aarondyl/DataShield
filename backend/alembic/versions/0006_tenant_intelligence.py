"""Tenant Intelligence runs, findings, canonical links and missing context."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger_type", sa.String(32), nullable=False),
        sa.Column("trigger_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("model_provider", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("input_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','COMPLETED','NEEDS_USER_INPUT','FAILED')",
            name="ck_tenant_agent_runs_status",
        ),
    )
    for column in ("tenant_id", "product_id", "trigger_type", "trigger_id", "status"):
        op.create_index(f"ix_tenant_agent_runs_{column}", "tenant_agent_runs", [column])

    op.create_table(
        "findings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("tenant_agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger_type", sa.String(32), nullable=False),
        sa.Column("trigger_id", sa.String(100), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("impact_level", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("applicability_summary", sa.Text(), nullable=False),
        sa.Column("gap_status", sa.String(20), nullable=False),
        sa.Column("gap_type", sa.String(40), nullable=False),
        sa.Column("gap_summary", sa.Text(), nullable=False),
        sa.Column("product_twin_version_id", sa.Integer(), sa.ForeignKey("product_twin_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('OPEN','DISMISSED','RESOLVED')", name="ck_findings_status"),
        sa.CheckConstraint("impact_level IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_findings_impact_level"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_findings_confidence"),
    )
    for column in ("tenant_id", "product_id", "run_id", "status", "impact_level", "created_at"):
        op.create_index(f"ix_findings_{column}", "findings", [column])

    op.create_table(
        "finding_requirements",
        sa.Column("finding_id", sa.Integer(), sa.ForeignKey("findings.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("requirements.id", ondelete="RESTRICT"), primary_key=True),
        sa.UniqueConstraint("finding_id", "requirement_id", name="uq_finding_requirement"),
    )
    op.create_index("ix_finding_requirements_requirement_id", "finding_requirements", ["requirement_id"])

    op.create_table(
        "finding_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("finding_id", sa.Integer(), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("legal_unit_id", sa.Integer(), sa.ForeignKey("legal_units.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("requirements.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("evidence_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_finding_evidence_finding_id", "finding_evidence", ["finding_id"])
    op.create_index("ix_finding_evidence_legal_unit_id", "finding_evidence", ["legal_unit_id"])

    op.create_table(
        "tenant_missing_context_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("tenant_agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True),
        sa.Column("field_path", sa.String(200), nullable=False),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('OPEN')", name="ck_tenant_missing_context_status"),
    )
    op.create_index("ix_tenant_missing_context_run_id", "tenant_missing_context_items", ["run_id"])
    op.create_index("ix_tenant_missing_context_status", "tenant_missing_context_items", ["status"])


def downgrade() -> None:
    op.drop_table("tenant_missing_context_items")
    op.drop_table("finding_evidence")
    op.drop_table("finding_requirements")
    op.drop_table("findings")
    op.drop_table("tenant_agent_runs")
