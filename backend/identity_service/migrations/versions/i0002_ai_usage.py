"""Persist prompt-free Cloud AI usage for rate limits and cost accounting."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "i0002"
down_revision = "i0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # i0001 creates current metadata for a brand-new database; an installed
    # database already stamped i0001 needs this additive table migration.
    if not inspect(bind).has_table("identity_ai_usage"):
        op.create_table(
            "identity_ai_usage",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("identity_users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("model", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
            sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    indexes = {index["name"] for index in inspect(bind).get_indexes("identity_ai_usage")}
    if "ix_identity_ai_usage_user_created" not in indexes:
        op.create_index("ix_identity_ai_usage_user_created", "identity_ai_usage", ["user_id", "created_at"])


def downgrade():
    bind = op.get_bind()
    if inspect(bind).has_table("identity_ai_usage"):
        op.drop_index("ix_identity_ai_usage_user_created", table_name="identity_ai_usage")
        op.drop_table("identity_ai_usage")
