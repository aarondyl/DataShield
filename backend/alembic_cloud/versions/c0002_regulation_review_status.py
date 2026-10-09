"""为自动采集的法规版本标注人工核验状态。"""

from alembic import op
import sqlalchemy as sa

revision = "c0002"
down_revision = "c0001"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("regulation_versions")}
    if "review_status" not in columns:
        with op.batch_alter_table("regulation_versions") as batch:
            batch.add_column(sa.Column("review_status", sa.String(length=32), nullable=False, server_default="UNREVIEWED"))
    op.execute("UPDATE regulation_versions SET review_status = 'UNREVIEWED' WHERE review_status IS NULL OR review_status = ''")


def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("regulation_versions")}
    if "review_status" in columns:
        with op.batch_alter_table("regulation_versions") as batch:
            batch.drop_column("review_status")
