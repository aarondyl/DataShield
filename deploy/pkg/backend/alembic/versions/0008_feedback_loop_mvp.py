"""Feedback loop immutable records and candidates."""
import sqlalchemy as sa
from alembic import op
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", sa.Integer(), sa.ForeignKey("findings.id", ondelete="RESTRICT")),
        sa.Column("remediation_id", sa.Integer(), sa.ForeignKey("remediations.id", ondelete="RESTRICT")),
        sa.Column("feedback_type", sa.String(30), nullable=False), sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False, server_default=""),
        sa.Column("useful", sa.Boolean()), sa.Column("negative_reason", sa.String(30)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("feedback_type IN ('FACT_CORRECTION','FINDING_FEEDBACK','REMEDIATION_FEEDBACK')", name="ck_feedback_type"))
    for c in ("tenant_id","product_id","finding_id","remediation_id"): op.create_index(f"ix_feedback_{c}","feedback",[c])
    op.create_table("feedback_candidates",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("feedback_id",sa.Integer(),sa.ForeignKey("feedback.id",ondelete="CASCADE"),nullable=False),
        sa.Column("tenant_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False), sa.Column("product_id",sa.Integer(),sa.ForeignKey("products.id",ondelete="CASCADE"),nullable=False),
        sa.Column("candidate_type",sa.String(30),nullable=False), sa.Column("status",sa.String(30),nullable=False),
        sa.Column("target_fact_id",sa.Integer(),sa.ForeignKey("product_twin_facts.id",ondelete="RESTRICT")),
        sa.Column("proposed_name",sa.String(200)),sa.Column("proposed_value",sa.JSON()),sa.Column("proposed_status",sa.String(20)),
        sa.Column("reasoning_summary",sa.Text(),nullable=False),sa.Column("confidence",sa.Float(),nullable=False),
        sa.Column("clarification_question",sa.String(1000)),sa.Column("clarification_answer",sa.Text()),
        sa.Column("applied_fact_id",sa.Integer(),sa.ForeignKey("product_twin_facts.id",ondelete="RESTRICT")),
        sa.Column("applied_twin_version_id",sa.Integer(),sa.ForeignKey("product_twin_versions.id",ondelete="RESTRICT")),
        sa.Column("reanalysis_run_id",sa.Integer(),sa.ForeignKey("tenant_agent_runs.id",ondelete="RESTRICT")),sa.Column("last_error",sa.Text(),nullable=False,server_default=""),
        sa.Column("model_provider",sa.String(50),nullable=False,server_default=""),sa.Column("model_name",sa.String(100),nullable=False,server_default=""),sa.Column("prompt_version",sa.String(50),nullable=False,server_default=""),
        sa.Column("created_at",sa.DateTime(),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(),nullable=False,server_default=sa.func.now()),
        sa.CheckConstraint("candidate_type IN ('FACT_CORRECTION','FINDING_FEEDBACK','REMEDIATION_FEEDBACK')",name="ck_feedback_candidate_type"),
        sa.CheckConstraint("status IN ('PROPOSED','NEEDS_CLARIFICATION','CONFIRMED','REJECTED','APPLIED')",name="ck_feedback_candidate_status"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1",name="ck_feedback_candidate_confidence"))
    for c in ("feedback_id","tenant_id","product_id","status","candidate_type"): op.create_index(f"ix_feedback_candidates_{c}","feedback_candidates",[c])
    op.create_table("feedback_candidate_requirements",sa.Column("candidate_id",sa.Integer(),sa.ForeignKey("feedback_candidates.id",ondelete="CASCADE"),primary_key=True),sa.Column("requirement_id",sa.Integer(),sa.ForeignKey("requirements.id",ondelete="RESTRICT"),primary_key=True))
    op.create_index("ix_feedback_candidate_requirements_requirement_id","feedback_candidate_requirements",["requirement_id"])

def downgrade():
    op.drop_table("feedback_candidate_requirements"); op.drop_table("feedback_candidates"); op.drop_table("feedback")
