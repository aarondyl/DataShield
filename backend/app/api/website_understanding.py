from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.understanding.jobs import authorize, get_store, JobStore, validate_product_scope
from app.understanding.website import analyze_website, public_url
from app.understanding.schemas import AnalysisJob, WebsiteRequest

router = APIRouter(prefix="/v1", tags=["Product understanding"])


@router.post("/analyze-website", response_model=AnalysisJob, status_code=202)
def submit(request: WebsiteRequest, background: BackgroundTasks,
           owner: str = Depends(authorize), store: JobStore = Depends(get_store), db: Session = Depends(get_db)):
    validate_product_scope(db, request.company_id, request.product_id)
    try:
        public_url(request.url)
    except ValueError:
        raise HTTPException(400, "Only a public HTTP(S) URL without credentials or query parameters is allowed") from None
    job = store.create("website", owner, request.product_id)
    background.add_task(store.run, job.model_copy(deep=True), lambda: analyze_website(request))
    return job


@router.get("/website-analysis/{analysis_id}", response_model=AnalysisJob)
def retrieve(analysis_id: str, owner: str = Depends(authorize), store: JobStore = Depends(get_store)):
    return store.get(analysis_id, "website", owner)
