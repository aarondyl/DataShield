from app.local_regulations.cache import LocalRegulationCache
from app.local_regulations.materializer import materialize_bundle
from app.db.base import Base
from app.models import Requirement
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import pytest


def _page_bundle():
    page={"snapshot_cursor":7,"next_cursor":7,"events":[{"id":7,"event_id":"evt_7"}]}
    bundle={"event":{"event_id":"evt_7"},"regulation":{"key":"EU:GDPR","name":"GDPR"},"version":{"key":"EU:GDPR:v2","number":2,"content_hash":"h","is_current":True},"legal_units":[{"key":"u","path":"1"}],"requirements":[{"key":"r","legal_unit_key":"u","summary":"义务"}]}
    return page,bundle

def test_cache_commits_cursor_with_bundle_atomically(tmp_path):
    c=LocalRegulationCache(tmp_path/"regulations.db")
    page={"snapshot_cursor":7,"next_cursor":7,"events":[{"id":7,"event_id":"evt_7"}]}
    bundle={"event":{"event_id":"evt_7"},"regulation":{"key":"EU:GDPR"},"version":{"key":"EU:GDPR:v2"},"legal_units":[{"key":"u"}],"requirements":[{"key":"r"}]}
    c.apply(page,[bundle]); assert c.progress()==(7,0,0)
    with c.connect() as db: assert db.execute("select count(*) from cached_requirements").fetchone()[0]==1


def test_incompatible_bundle_version_never_advances_cursor(tmp_path):
    cache = LocalRegulationCache(tmp_path / "regulations.db")
    page, bundle = _page_bundle()
    bundle["schema_version"] = "2.0"
    with pytest.raises(ValueError, match="契约版本"):
        cache.apply(page, [bundle])
    assert cache.progress() == (0, 0, 0)


def test_incompatible_page_and_stalled_pagination_preserve_cache(tmp_path):
    cache = LocalRegulationCache(tmp_path / 'regulations.db')
    page, bundle = _page_bundle()
    page['schema_version'] = '2.0'
    with pytest.raises(ValueError, match='契约版本'):
        cache.apply(page, [bundle])
    with pytest.raises(ValueError, match='未取得进展'):
        cache.apply({'snapshot_cursor': 7, 'next_cursor': 0, 'events': [], 'has_more': True}, [])
    assert cache.progress() == (0, 0, 0)

def test_cache_rejects_incomplete_or_backward_page(tmp_path):
    c=LocalRegulationCache(tmp_path/"r.db")
    page={"snapshot_cursor":2,"next_cursor":2,"events":[{"id":2,"event_id":"e2"}]}
    try: c.apply(page,[])
    except ValueError: pass
    else: assert False

def test_cache_rejects_duplicate_and_bad_final_cursor(tmp_path):
    c=LocalRegulationCache(tmp_path/"r.db")
    page={"snapshot_cursor":2,"next_cursor":1,"events":[{"id":2,"event_id":"e2"}]}
    bundle={"event":{"event_id":"e2"},"regulation":{"key":"r"},"version":{"key":"v"},"legal_units":[],"requirements":[]}
    try: c.apply(page,[bundle])
    except ValueError: pass
    else: assert False


def test_orm_failure_rolls_back_cache_and_cursor_in_one_sqlite_transaction(tmp_path):
    path=tmp_path/"local.db"; c=LocalRegulationCache(path)
    engine=create_engine(f"sqlite:///{path}"); Base.metadata.create_all(engine); Session=sessionmaker(bind=engine)
    page,bundle=_page_bundle(); bundle["requirements"][0]["legal_unit_key"]="missing"
    with Session() as db:
        with pytest.raises(ValueError), db.begin():
            c.apply(page,[bundle],db=db,materialize=lambda item: materialize_bundle(db,item))
    assert c.progress()==(0,0,0)
    with c.connect() as db: assert db.execute("select count(*) from cached_events").fetchone()[0] == 0


def test_failure_injection_and_repeat_event_keep_committed_progress_safe(tmp_path):
    path=tmp_path/"local.db"; c=LocalRegulationCache(path)
    engine=create_engine(f"sqlite:///{path}"); Base.metadata.create_all(engine); Session=sessionmaker(bind=engine)
    page,bundle=_page_bundle()
    with Session() as db:
        with pytest.raises(RuntimeError), db.begin():
            c.apply(page,[bundle],db=db,materialize=lambda _: (_ for _ in ()).throw(RuntimeError("inject")))
    assert c.progress()==(0,0,0)
    for _ in range(2):
        with Session() as db:
            with db.begin(): c.apply(page,[bundle],db=db,materialize=lambda item: materialize_bundle(db,item))
    assert c.progress()==(7,0,0)
    with Session() as db: assert len(db.scalars(select(Requirement)).all()) == 1
