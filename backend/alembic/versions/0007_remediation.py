"""Remediation plans and canonical Finding traceability."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "remediations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("finding_id", sa.Integer(), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("remediation_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("input_snapshot_json", sa.JSON(), nullable=False),
        sa.Column(
            "product_twin_version_id",
            sa.Integer(),
            sa.ForeignKey("product_twin_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("model_provider", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "remediation_type IN ('CODE_CHANGE','DOCUMENT_CHANGE')",
            name="ck_remediations_type",
        ),
        sa.CheckConstraint(
            "status IN ('PROPOSED','APPROVED','REJECTED')",
            name="ck_remediations_status",
        ),
    )
    for column in ("finding_id", "tenant_id", "product_id", "status", "created_at"):
        op.create_index(f"ix_remediations_{column}", "remediations", [column])

    op.create_table(
        "remediation_requirements",
        sa.Column(
            "remediation_id",
            sa.Integer(),
            sa.ForeignKey("remediations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "requirement_id",
            sa.Integer(),
            sa.ForeignKey("requirements.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.UniqueConstraint(
            "remediation_id", "requirement_id", name="uq_remediation_requirement"
        ),
    )
    op.create_index(
        "ix_remediation_requirements_requirement_id",
        "remediation_requirements",
        ["requirement_id"],
    )

    op.create_table(
        "remediation_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "remediation_id",
            sa.Integer(),
            sa.ForeignKey("remediations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "legal_unit_id",
            sa.Integer(),
            sa.ForeignKey("legal_units.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "requirement_id",
            sa.Integer(),
            sa.ForeignKey("requirements.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("evidence_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_remediation_evidence_legal_unit_id",
        "remediation_evidence",
        ["legal_unit_id"],
    )


def downgrade() -> None:
    op.drop_table("remediation_evidence")
    op.drop_table("remediation_requirements")
    op.drop_table("remediations")
