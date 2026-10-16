"""Fresh Desktop installations include a real, searchable law corpus offline."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import Company, LegalUnit, Regulation, RegulationVersion, Requirement, RegulatorySource
from app.services.seed_regintel import seed_regintel_if_empty


def test_local_corpus_seeds_pipl_and_dsl_without_sample_business_data(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'local.db').as_posix()}")
    Base.metadata.create_all(engine)
    source_directory = tmp_path / "user-data" / "regulations" / "sources"

    with Session(engine) as db:
        assert seed_regintel_if_empty(
            db,
            regulation_codes={"pipl", "dsl"},
            source_directory=source_directory,
        )
        regulations = db.scalars(select(Regulation).order_by(Regulation.short_name)).all()
        assert {row.short_name for row in regulations} == {"PIPL", "DSL"}
        assert db.scalar(select(func.count()).select_from(Company)) == 0
        assert db.scalar(select(func.count()).select_from(LegalUnit)) > 100
        assert db.scalar(select(func.count()).select_from(Requirement)) > 100
        assert db.scalar(select(func.count()).select_from(RegulatorySource)) == 2
        assert all(source_directory.joinpath(f"{code}.txt").is_file() for code in ("pipl", "dsl"))
        assert all(
            version.review_status == "UNREVIEWED"
            for version in db.scalars(select(RegulationVersion)).all()
        )

    engine.dispose()
