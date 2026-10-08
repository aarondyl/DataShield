from app.local_regulations.cache import LocalRegulationCache
from app.local_regulations.gateway import LocalRegulationGateway
from app.local_regulations.materializer import materialize_bundle
from app.db.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_gateway_reads_only_local_cache(tmp_path):
    c=LocalRegulationCache(tmp_path/"r.db")
    engine=create_engine(f"sqlite:///{tmp_path/'r.db'}"); Base.metadata.create_all(engine); Session=sessionmaker(bind=engine)
    p={"snapshot_cursor":1,"next_cursor":1,"events":[{"id":1,"event_id":"e","payload":{}}]}
    b={"event":{"event_id":"e"},"regulation":{"key":"r","name":"法规"},"version":{"key":"v","number":1,"content_hash":"h","is_current":True},"legal_units":[],"requirements":[{"key":"q","summary":"本地义务"}]}
    with Session() as db:
        with db.begin(): c.apply(p,[b],db=db,materialize=lambda x: materialize_bundle(db,x))
    gateway=LocalRegulationGateway(c, Session)
    assert gateway.requirements_for_event("e")[0]["summary"]=="本地义务"
    assert gateway.requirement_contexts_for_event("e")[0].summary=="本地义务"
    assert gateway.trigger("e").event_id=="e"
