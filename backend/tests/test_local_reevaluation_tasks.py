from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app import models  # noqa
from app.local_regulations.tasks import enqueue

def test_event_product_task_is_idempotent(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'tasks.db'}"); Base.metadata.create_all(engine)
    db=sessionmaker(bind=engine)()
    assert len(enqueue(db,"evt_1",[2,2,3]))==2; db.commit()
    assert enqueue(db,"evt_1",[2,3])==[]
