"""Add registered Web users and link their sessions."""

from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(500), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("edition", sa.String(20), nullable=False, server_default="developer"),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    with op.batch_alter_table("evaluation_sessions") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", name="fk_evaluation_sessions_user_id"), nullable=True))
    op.create_index("ix_evaluation_sessions_user_id", "evaluation_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_sessions_user_id", table_name="evaluation_sessions")
    with op.batch_alter_table("evaluation_sessions") as batch:
        batch.drop_column("user_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
