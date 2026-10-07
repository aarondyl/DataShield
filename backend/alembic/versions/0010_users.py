"""Registered user accounts and link from evaluation sessions."""
import sqlalchemy as sa
from alembic import op
revision="0010"; down_revision="0009"; branch_labels=None; depends_on=None
def upgrade():
    op.create_table("users",
        sa.Column("id",sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column("email",sa.String(320),nullable=False),
        sa.Column("password_hash",sa.String(500),nullable=False),
        sa.Column("display_name",sa.String(200),nullable=False),
        sa.Column("company_id",sa.Integer(),sa.ForeignKey("companies.id"),nullable=False),
        sa.Column("edition",sa.String(20),nullable=False,server_default="developer"),
        sa.Column("email_verified",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("created_at",sa.DateTime(),server_default=sa.func.now(),nullable=False),
        sa.Column("last_login_at",sa.DateTime()))
    op.create_index("ix_users_email","users",["email"],unique=True)
    with op.batch_alter_table("evaluation_sessions") as batch:
        batch.add_column(sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",name="fk_evaluation_sessions_user_id"),nullable=True))
def downgrade():
    with op.batch_alter_table("evaluation_sessions") as batch:
        batch.drop_column("user_id")
    op.drop_table("users")
