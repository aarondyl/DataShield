"""本地重评估任务：法规同步成功后才入队，失败可在本地重试。"""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Company, LocalReevaluationTask, Product

def enqueue(db: Session, event_id: str, product_ids: list[int]) -> list[LocalReevaluationTask]:
    rows=[]
    for product_id in sorted(set(product_ids)):
        row=db.scalar(select(LocalReevaluationTask).where(LocalReevaluationTask.event_id==event_id,LocalReevaluationTask.product_id==product_id))
        if row is None:
            row=LocalReevaluationTask(event_id=event_id,product_id=product_id); db.add(row); rows.append(row)
    return rows


def run_pending(session_factory=None, limit: int = 100) -> int:
    """运行本地待评估任务；不会联网，也不会将 Product Twin 或证据传出。"""
    if session_factory is None:
        from app.db.session import SessionLocal
        session_factory = SessionLocal
    with session_factory() as db:
        tasks = list(db.scalars(select(LocalReevaluationTask).where(
            LocalReevaluationTask.status.in_(("PENDING", "FAILED"))
        ).order_by(LocalReevaluationTask.id).limit(limit)).all())
    completed = 0
    for task in tasks:
        try:
            _run_task(task.id, session_factory)
            completed += 1
        except Exception:
            # 错误已经持久化；后续同步或显式重试仍可继续领取。
            continue
    return completed


def _run_task(task_id: int, session_factory) -> None:
    from app.core.config import get_settings
    from app.tenant.agent.graph import get_tenant_graph
    from app.tenant.findings.schemas import TenantTriggerType
    from app.tenant.findings.service import create_pending_agent_run

    try:
        with session_factory() as db:
            task = db.get(LocalReevaluationTask, task_id)
            if task is None or task.status == "COMPLETED": return
            product = db.get(Product, task.product_id)
            company = db.get(Company, product.company_id) if product else None
            if product is None or company is None:
                task.status, task.error = "FAILED", "产品或租户不存在"
                db.commit(); return
            tenant_id, product_id, event_id = company.id, product.id, task.event_id
            task.status, task.error = "RUNNING", ""
            db.commit()
            run = create_pending_agent_run(db, tenant_id=tenant_id, product_id=product_id,
                trigger_type=TenantTriggerType.REGULATION_CHANGE, trigger_id=event_id,
                model_provider=get_settings().llm_provider,
                model_name="deterministic/mock", prompt_version="local-regulation-v1")
        initial = {"tenant_id": tenant_id, "product_id": product_id, "trigger_type": "REGULATION_CHANGE",
            "trigger_id": event_id, "regulation_id": None, "requirement_ids": [], "query": "", "run_id": run.id,
            "requirements": [], "ready_requirement_ids": [], "legal_evidence": [], "missing_context": [],
            "applicability_results": [], "gap_results": [], "finding_candidates": [], "finding_ids": [], "status": "PENDING", "errors": []}
        get_tenant_graph().invoke(initial)
    except Exception as exc:
        with session_factory() as db:
            task = db.get(LocalReevaluationTask, task_id)
            task.status, task.error = "FAILED", str(exc)[:4000]
            db.commit()
        raise
    with session_factory() as db:
        task = db.get(LocalReevaluationTask, task_id)
        task.status, task.error = "COMPLETED", ""
        db.commit()
