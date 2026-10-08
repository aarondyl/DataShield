"""本地法规同步稳定键与重评估任务。"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("local_reevaluation_tasks",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("event_id", sa.String(100), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("event_id", "product_id", name="uq_local_reevaluation_event_product"))
    op.create_table("local_regulation_bindings",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_key", sa.String(512), nullable=False), sa.Column("local_id", sa.Integer(), nullable=False),
        sa.UniqueConstraint("entity_type", "entity_key", name="uq_local_regulation_binding"))
    op.create_index("ix_local_regulation_bindings_local_id", "local_regulation_bindings", ["local_id"])


def downgrade():
    op.drop_table("local_regulation_bindings")
    op.drop_table("local_reevaluation_tasks")
