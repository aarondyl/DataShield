"""为法规来源快照增加原始响应 SHA256。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("source_snapshots")}
    if "raw_content_hash" not in columns:
        with op.batch_alter_table("source_snapshots") as batch:
            batch.add_column(sa.Column("raw_content_hash", sa.String(length=64), nullable=False, server_default=""))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("source_snapshots")}
    if "raw_content_hash" in columns:
        with op.batch_alter_table("source_snapshots") as batch:
            batch.drop_column("raw_content_hash")
