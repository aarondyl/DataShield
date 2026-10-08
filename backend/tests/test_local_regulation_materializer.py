from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app import models  # noqa
from app.local_regulations.materializer import materialize_bundle

def test_bundle_materializes_real_local_foreign_keys(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'local.db'}"); Base.metadata.create_all(engine)
    db=sessionmaker(bind=engine)()
    bundle={"regulation":{"key":"EU:GDPR","name":"GDPR","jurisdiction":"EU"},"version":{"key":"EU:GDPR:v1","number":1,"content_hash":"h","is_current":True},"legal_units":[{"key":"u","path":"Article 1","unit_number":"1","heading":"范围","text":"文本"}],"requirements":[{"key":"q","legal_unit_key":"u","summary":"义务","action":"inform","type":"obligation","conditions":[],"exceptions":[]}]}
    ids=materialize_bundle(db,bundle); db.commit()
    assert ids["regulation_id"] > 0 and ids["version_id"] > 0 and ids["requirement:q"] > 0
