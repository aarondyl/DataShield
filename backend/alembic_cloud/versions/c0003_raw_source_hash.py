"""为来源快照保存抓取响应的原始字节哈希。"""

import sqlalchemy as sa
from alembic import op

revision = "c0003"
down_revision = "c0002"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("source_snapshots")}
    if "raw_content_hash" not in columns:
        with op.batch_alter_table("source_snapshots") as batch:
            batch.add_column(sa.Column("raw_content_hash", sa.String(64), nullable=False, server_default=""))


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("source_snapshots")}
    if "raw_content_hash" in columns:
        with op.batch_alter_table("source_snapshots") as batch:
            batch.drop_column("raw_content_hash")
