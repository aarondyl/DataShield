"""为法规版本标注人工核验状态。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("regulation_versions")}
    if "review_status" not in columns:
        with op.batch_alter_table("regulation_versions") as batch:
            batch.add_column(
                sa.Column("review_status", sa.String(length=32), nullable=False, server_default="UNREVIEWED")
            )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("regulation_versions")}
    if "review_status" in columns:
        with op.batch_alter_table("regulation_versions") as batch:
            batch.drop_column("review_status")
