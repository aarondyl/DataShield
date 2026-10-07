"""Add disabled flag to registered users."""
import sqlalchemy as sa
from alembic import op
revision="0011"; down_revision="0010"; branch_labels=None; depends_on=None
def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("disabled",sa.Boolean(),nullable=False,server_default=sa.false()))
def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("disabled")
