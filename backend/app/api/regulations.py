"""法规接口：列表（含条款数）/ 详情（含条款数组）/ 上传解析入库。"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Regulation, RegulationArticle
from app.rag.ingestion import SUPPORTED_EXTENSIONS, ingest_regulation_text, parse_upload_to_text
from app.schemas.regulation import (
    ArticleOut,
    RegulationDetailOut,
    RegulationOut,
    RegulationUploadResult,
)

router = APIRouter(prefix="/regulations", tags=["regulations"])

#: 上传文件大小上限（10 MB）
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.get("", response_model=list[RegulationOut])
def list_regulations(db: Session = Depends(get_db)) -> list[RegulationOut]:
    """法规列表（含每个法规的已入库条款数）。"""
    stmt = (
        select(Regulation, func.count(RegulationArticle.id))
        .outerjoin(RegulationArticle, RegulationArticle.regulation_id == Regulation.id)
        .group_by(Regulation.id)
        .order_by(Regulation.id)
    )
    results: list[RegulationOut] = []
    for regulation, article_count in db.execute(stmt).all():
        out = RegulationOut.model_validate(regulation)
        out.article_count = article_count
        results.append(out)
    return results


@router.get("/{regulation_id}", response_model=RegulationDetailOut)
def get_regulation(regulation_id: int, db: Session = Depends(get_db)) -> RegulationDetailOut:
    """法规详情（含条款数组，按入库顺序返回）。"""
    regulation = db.get(Regulation, regulation_id)
    if regulation is None:
        raise HTTPException(status_code=404, detail="法规不存在")
    articles = db.scalars(
        select(RegulationArticle)
        .where(RegulationArticle.regulation_id == regulation_id)
        .order_by(RegulationArticle.id)
    ).all()
    out = RegulationDetailOut.model_validate(regulation)
    out.article_count = len(articles)
    out.articles = [ArticleOut.model_validate(a) for a in articles]
    return out


@router.post("/upload", response_model=RegulationUploadResult, status_code=201)
async def upload_regulation(
    file: UploadFile = File(..., description="法规文件（.txt / .md / .pdf）"),
    name: str = Form(..., description="法规名称"),
    jurisdiction: str = Form("", description="法域，如 EU / CN"),
    description: str = Form("", description="法规简介"),
    source_url: str = Form("", description="官方来源链接"),
    db: Session = Depends(get_db),
) -> RegulationUploadResult:
    """上传法规文件：解析 → 条款切分 → 向量化 → 入库建索引。"""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 .txt / .md / .pdf 格式的法规文件")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="文件过大，最大支持 10MB")

    try:
        text = parse_upload_to_text(filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not text.strip():
        raise HTTPException(status_code=400, detail="未能从文件中提取到文本内容")

    try:
        regulation, count = ingest_regulation_text(
            db,
            name=name,
            jurisdiction=jurisdiction,
            description=description,
            source_url=source_url,
            text=text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RegulationUploadResult(id=regulation.id, name=regulation.name, articles_ingested=count)
