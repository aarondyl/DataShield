"""Opaque evaluation browser sessions."""
import sqlalchemy as sa
from alembic import op
revision="0009"; down_revision="0008"; branch_labels=None; depends_on=None
def upgrade():
    op.create_table("evaluation_sessions",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("token_hash",sa.String(64),nullable=False),sa.Column("evaluation_user_id",sa.String(64),nullable=False),sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id",ondelete="CASCADE"),nullable=False),sa.Column("edition",sa.String(20),nullable=False),sa.Column("created_at",sa.DateTime(),server_default=sa.func.now(),nullable=False),sa.Column("expires_at",sa.DateTime(),nullable=False),sa.Column("revoked_at",sa.DateTime()))
    op.create_index("ix_evaluation_sessions_token_hash","evaluation_sessions",["token_hash"],unique=True);op.create_index("ix_evaluation_sessions_user","evaluation_sessions",["evaluation_user_id"]);op.create_index("ix_evaluation_sessions_company","evaluation_sessions",["company_id"]);op.create_index("ix_evaluation_sessions_expires","evaluation_sessions",["expires_at"])
def downgrade(): op.drop_table("evaluation_sessions")
