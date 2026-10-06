from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.understanding.jobs import authorize, get_store, JobStore, validate_product_scope
from app.understanding.repository import analyze_repository, validate_root
from app.understanding.schemas import AnalysisJob, RepositoryRequest

router = APIRouter(prefix="/v1", tags=["Product understanding"])


@router.post("/analyze-repository", response_model=AnalysisJob, status_code=202)
def submit(request: RepositoryRequest, background: BackgroundTasks,
           owner: str = Depends(authorize), store: JobStore = Depends(get_store), db: Session = Depends(get_db)):
    validate_product_scope(db, request.company_id, request.product_id)
    try:
        validate_root(request)
    except (ValueError, OSError):
        raise HTTPException(400, "Repository path or selection is not permitted") from None
    job = store.create("repository", owner, request.product_id)
    background.add_task(store.run, job.model_copy(deep=True), lambda: analyze_repository(request))
    return job


@router.get("/repository-analysis/{analysis_id}", response_model=AnalysisJob)
def retrieve(analysis_id: str, owner: str = Depends(authorize), store: JobStore = Depends(get_store)):
    return store.get(analysis_id, "repository", owner)
