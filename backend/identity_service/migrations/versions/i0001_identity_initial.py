"""Identity-only schema; this metadata contains no product or RegIntel tables."""

from alembic import op

revision = "i0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    from identity_service import models  # noqa: F401
    from identity_service.base import IdentityBase

    IdentityBase.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    from identity_service import models  # noqa: F401
    from identity_service.base import IdentityBase

    IdentityBase.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
