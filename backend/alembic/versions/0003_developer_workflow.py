"""Add product profile fields and developer scan/issue workflow."""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column("products", sa.Column("uses_third_party_sdk", sa.Boolean(), nullable=True, server_default=sa.false()))
    op.add_column("products", sa.Column("third_party_sdks", sa.JSON(), nullable=True))
    op.add_column("products", sa.Column("privacy_policy_text", sa.Text(), nullable=True))
    op.create_table("developer_issues",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(50), nullable=True), sa.Column("source_key", sa.String(150), nullable=True),
        sa.Column("title", sa.String(300), nullable=False), sa.Column("risk_level", sa.String(10), nullable=True),
        sa.Column("why", sa.Text(), nullable=True), sa.Column("fix", sa.Text(), nullable=True),
        sa.Column("recommended_text", sa.Text(), nullable=True), sa.Column("placement", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=True), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()))
    op.create_index("ix_developer_issues_product_id", "developer_issues", ["product_id"])
    op.create_table("sdk_scans",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=True), sa.Column("content", sa.Text(), nullable=True),
        sa.Column("findings", sa.JSON(), nullable=True), sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()))
    op.create_index("ix_sdk_scans_product_id", "sdk_scans", ["product_id"])

def downgrade() -> None:
    op.drop_index("ix_sdk_scans_product_id", table_name="sdk_scans"); op.drop_table("sdk_scans")
    op.drop_index("ix_developer_issues_product_id", table_name="developer_issues"); op.drop_table("developer_issues")
    op.drop_column("products", "privacy_policy_text"); op.drop_column("products", "third_party_sdks"); op.drop_column("products", "uses_third_party_sdk")
