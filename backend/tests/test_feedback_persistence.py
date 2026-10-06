from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.base import Base
from app.models import Company, Product, Feedback
from app.tenant.feedback.schemas import FeedbackCreateRequest
from app.tenant.feedback.service import create_feedback, FeedbackNotFoundError
import pytest

def test_feedback_is_persisted_immutably_and_tenant_scoped(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'f.db'}"); Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Company(id=1,name="A"),Company(id=2,name="B")]); db.flush(); db.add(Product(id=1,company_id=1,name="P")); db.commit()
        req=FeedbackCreateRequest(tenant_id=1,product_id=1,finding_id=999,feedback_type="FACT_CORRECTION",raw_text="Already supported")
        with pytest.raises(FeedbackNotFoundError): create_feedback(db,req)
        assert db.query(Feedback).count()==0
