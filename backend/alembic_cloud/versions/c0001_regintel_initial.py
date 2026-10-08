"""Cloud 公共法规专用初始结构。

迁移显式限定表集合；禁止改用通用 alembic 链，以免创建 Company、Product 或 Finding 等私有表。
"""
from alembic import op

revision = "c0001"
down_revision = None
branch_labels = None
depends_on = None


def _tables():
    from app.models.legal_chunk import LegalChunk
    from app.models.regulation import Regulation, RegulationArticle
    from app.models.regulation_change import RegulationChange, RegulationEvent
    from app.models.regulation_version import LegalUnit, RegulationVersion
    from app.models.regulatory_source import IngestionRun, RegulatorySource, SourceSnapshot
    from app.models.requirement import Requirement
    return [
        Regulation.__table__, RegulationArticle.__table__, RegulationVersion.__table__, LegalUnit.__table__,
        Requirement.__table__, LegalChunk.__table__, RegulationChange.__table__, RegulationEvent.__table__,
        RegulatorySource.__table__, SourceSnapshot.__table__, IngestionRun.__table__,
    ]


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    from app.db.base import Base
    Base.metadata.create_all(bind=bind, tables=_tables(), checkfirst=True)


def downgrade():
    from app.db.base import Base
    Base.metadata.drop_all(bind=op.get_bind(), tables=list(reversed(_tables())), checkfirst=True)
