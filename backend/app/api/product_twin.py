"""Internal Product Twin API. Shared service key authorizes calls, not tenant identity."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ProductTwinAnalysisRef, ProductTwinVersion
from app.understanding.jobs import JobStore, authorize, get_store, validate_product_scope
from app.understanding.schemas import Confidence, Contract, Fact, FindingStatus
from app.understanding.twin import add_manual_fact, attach_analysis, current_view, decide_fact, version_view

router = APIRouter(prefix="/v1/products/{product_id}/twin", tags=["Product Twin"])


class AttachRequest(Contract):
    company_id: int = Field(ge=1)
    analysis_id: str = Field(min_length=1, max_length=64)
    kind: Literal["repository", "website"]


class FactInput(Contract):
    name: str = Field(min_length=1, max_length=200)
    status: FindingStatus
    confidence: Confidence

    def as_fact(self) -> Fact:
        return Fact(name=self.name, status=self.status, confidence=self.confidence)


class ManualFactRequest(Contract):
    company_id: int = Field(ge=1)
    group: str = Field(min_length=1, max_length=40)
    fact: FactInput
    note: str = Field(min_length=1, max_length=1000)


class DecisionRequest(Contract):
    company_id: int = Field(ge=1)
    note: str = Field(default="", max_length=1000)
    actor_label: str = Field(default="", max_length=200)


class CorrectionRequest(DecisionRequest):
    fact: FactInput


@router.post("/analyses", status_code=201)
def attach(product_id: int, payload: AttachRequest, db: Session = Depends(get_db),
           owner: str = Depends(authorize), store: JobStore = Depends(get_store)):
    validate_product_scope(db, payload.company_id, product_id)
    job = store.get(payload.analysis_id, payload.kind, owner)
    return version_view(db, attach_analysis(db, product_id, job))


@router.post("/facts", status_code=201)
def manual_fact(product_id: int, payload: ManualFactRequest, db: Session = Depends(get_db),
                owner: str = Depends(authorize)):
    validate_product_scope(db, payload.company_id, product_id)
    return version_view(db, add_manual_fact(db, product_id, payload.group, payload.fact.as_fact(), payload.note))


@router.get("")
def current(product_id: int, company_id: int = Query(ge=1), db: Session = Depends(get_db),
            owner: str = Depends(authorize)):
    validate_product_scope(db, company_id, product_id)
    return current_view(db, product_id)


@router.get("/versions")
def versions(product_id: int, company_id: int = Query(ge=1), db: Session = Depends(get_db),
             owner: str = Depends(authorize)):
    validate_product_scope(db, company_id, product_id)
    rows = db.scalars(select(ProductTwinVersion).where(ProductTwinVersion.product_id == product_id)
                      .order_by(ProductTwinVersion.version_number.desc())).all()
    return [{"version": row.version_number, "reason": row.reason, "source_analysis_id": row.source_analysis_id,
             "created_at": row.created_at} for row in rows]


@router.get("/versions/{version_number}")
def version(product_id: int, version_number: int, company_id: int = Query(ge=1), db: Session = Depends(get_db),
            owner: str = Depends(authorize)):
    validate_product_scope(db, company_id, product_id)
    row = db.scalar(select(ProductTwinVersion).where(ProductTwinVersion.product_id == product_id,
                                                     ProductTwinVersion.version_number == version_number))
    if row is None:
        raise HTTPException(404, "Product Twin version not found")
    return version_view(db, row)


@router.get("/analysis-refs/{analysis_id}")
def analysis_ref(product_id: int, analysis_id: str, company_id: int = Query(ge=1),
                 db: Session = Depends(get_db), owner: str = Depends(authorize)):
    validate_product_scope(db, company_id, product_id)
    ref = db.get(ProductTwinAnalysisRef, analysis_id)
    if ref is None or ref.product_id != product_id:
        raise HTTPException(404, "Analysis reference not found")
    return {"analysis_id": ref.analysis_id, "kind": ref.kind, "result_sha256": ref.result_sha256,
            "scan_scope": ref.scan_scope, "captured_at": ref.captured_at, "result": ref.result}


@router.post("/facts/{fact_id}/confirm")
def confirm(product_id: int, fact_id: int, payload: DecisionRequest, db: Session = Depends(get_db),
            owner: str = Depends(authorize)):
    validate_product_scope(db, payload.company_id, product_id)
    return version_view(db, decide_fact(db, product_id, fact_id, "CONFIRM", payload.note, payload.actor_label))


@router.post("/facts/{fact_id}/correct")
def correct(product_id: int, fact_id: int, payload: CorrectionRequest, db: Session = Depends(get_db),
            owner: str = Depends(authorize)):
    validate_product_scope(db, payload.company_id, product_id)
    return version_view(db, decide_fact(db, product_id, fact_id, "CORRECT", payload.note,
                                        payload.actor_label, payload.fact.as_fact()))
