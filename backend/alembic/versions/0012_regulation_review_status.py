"""标记法规版本的人工核验状态。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "regulation_versions",
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="UNREVIEWED"),
    )


def downgrade() -> None:
    op.drop_column("regulation_versions", "review_status")
