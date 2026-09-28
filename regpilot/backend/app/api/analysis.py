"""影响分析接口：POST 运行 LangGraph 工作流；GET 列表 / GET 详情。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.graph import get_graph
from app.agents.state import AgentState
from app.core.config import get_settings
from app.db.session import get_db
from app.models import AnalysisRun, Company, ComplianceAction, ImpactResult, Product, Regulation
from app.schemas.analysis import AnalysisListItem, AnalysisOut, AnalysisRequest, EvidenceOut
from app.schemas.action import ActionOut

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _build_analysis_out(db: Session, run: AnalysisRun) -> AnalysisOut:
    """把运行记录 + 影响结果 + 整改动作组装为完整响应体。"""
    result = db.scalar(select(ImpactResult).where(ImpactResult.run_id == run.id))
    actions = db.scalars(
        select(ComplianceAction).where(ComplianceAction.run_id == run.id).order_by(ComplianceAction.id)
    ).all()

    evidence: list[EvidenceOut] = []
    if result is not None:
        for item in result.evidence or []:
            if isinstance(item, dict):
                evidence.append(
                    EvidenceOut(
                        regulation=item.get("regulation", ""),
                        article=item.get("article", ""),
                        content=item.get("content", ""),
                        source_url=item.get("source_url", ""),
                        reason=item.get("reason", ""),
                        verified=bool(item.get("verified", False)),
                    )
                )

    return AnalysisOut(
        id=run.id,
        status=run.status,
        relevant=result.relevant if result else None,
        risk_level=result.risk_level if result else None,
        affected_products=result.affected_products if result else [],
        affected_areas=result.affected_areas if result else [],
        summary=result.summary if result else "",
        reasoning_summary=result.reasoning_summary if result else "",
        confidence=result.confidence if result else None,
        evidence=evidence,
        actions=[ActionOut.model_validate(a) for a in actions],
        llm_mode=run.llm_mode,
        created_at=run.created_at,
    )


@router.post("", response_model=AnalysisOut, status_code=201)
def run_analysis(payload: AnalysisRequest, db: Session = Depends(get_db)) -> AnalysisOut:
    """发起一次法规影响分析：运行 LangGraph 工作流并落库，返回完整结果。"""
    if db.get(Company, payload.company_id) is None:
        raise HTTPException(status_code=404, detail="企业不存在")
    if db.get(Product, payload.product_id) is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    if payload.regulation_id is not None and db.get(Regulation, payload.regulation_id) is None:
        raise HTTPException(status_code=404, detail="指定的法规不存在")

    run = AnalysisRun(
        company_id=payload.company_id,
        product_id=payload.product_id,
        regulation_id=payload.regulation_id,
        query=payload.query,
        status="running",
        llm_mode=get_settings().llm_provider,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    initial_state: AgentState = {
        "run_id": run.id,
        "company_id": payload.company_id,
        "product_id": payload.product_id,
        "regulation_id": payload.regulation_id,
        "query": payload.query,
        "retrieved_chunks": [],
        "impact_result": None,
        "evidence_result": None,
        "actions": [],
        "retry_count": 0,
    }

    try:
        get_graph().invoke(initial_state)
    except Exception as exc:  # 工作流内部异常（LLM 失败已在节点内降级，不会走到这里）
        run.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"分析流程执行失败：{exc}") from exc

    db.refresh(run)
    return _build_analysis_out(db, run)


@router.get("", response_model=list[AnalysisListItem])
def list_analyses(db: Session = Depends(get_db)) -> list[AnalysisListItem]:
    """分析运行列表（含企业/产品名称、风险等级、状态），按时间倒序。"""
    stmt = (
        select(AnalysisRun, Company.name, Product.name, ImpactResult)
        .join(Company, AnalysisRun.company_id == Company.id)
        .join(Product, AnalysisRun.product_id == Product.id)
        .outerjoin(ImpactResult, ImpactResult.run_id == AnalysisRun.id)
        .order_by(AnalysisRun.id.desc())
    )
    items: list[AnalysisListItem] = []
    for run, company_name, product_name, result in db.execute(stmt).all():
        items.append(
            AnalysisListItem(
                id=run.id,
                company_name=company_name,
                product_name=product_name,
                risk_level=result.risk_level if result else None,
                relevant=result.relevant if result else None,
                status=run.status,
                created_at=run.created_at,
            )
        )
    return items


@router.get("/{run_id}", response_model=AnalysisOut)
def get_analysis(run_id: int, db: Session = Depends(get_db)) -> AnalysisOut:
    """分析运行完整详情。"""
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return _build_analysis_out(db, run)
