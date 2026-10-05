from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from app.understanding.jobs import authorize, get_store, JobStore
from app.understanding.website import analyze_website, public_url
from app.understanding.schemas import AnalysisJob, WebsiteRequest
router=APIRouter(prefix="/v1", tags=["Product understanding"])
@router.post("/analyze-website", response_model=AnalysisJob, status_code=202)
def submit(request: WebsiteRequest, background: BackgroundTasks, owner: str=Depends(authorize), store: JobStore=Depends(get_store)):
    try: public_url(request.url)
    except ValueError: raise HTTPException(400,"Only a resolvable public HTTP(S) URL is allowed") from None
    job=store.create("website",owner); background.add_task(store.run,job.model_copy(deep=True),lambda: analyze_website(request)); return job
@router.get("/website-analysis/{analysis_id}", response_model=AnalysisJob)
def retrieve(analysis_id: str, owner: str=Depends(authorize), store: JobStore=Depends(get_store)): return store.get(analysis_id,"website",owner)
