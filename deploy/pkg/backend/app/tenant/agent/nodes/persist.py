from app.db.session import SessionLocal
from app.tenant.agent.state import TenantAgentState
from app.tenant.findings.service import mark_run_running, persist_findings


def start_run(state: TenantAgentState) -> dict:
    run_id = state.get("run_id")
    if run_id is None:
        raise RuntimeError("Tenant Agent run must be created before graph invocation")
    with SessionLocal() as db:
        mark_run_running(db, run_id)
    return {"status": "RUNNING"}


def persist(state: TenantAgentState) -> dict:
    run_id = state.get("run_id")
    if run_id is None:
        raise RuntimeError("Tenant Agent run is unavailable")
    with SessionLocal() as db:
        findings = persist_findings(
            db,
            run_id,
            state.get("finding_candidates", []),
            missing_context=state.get("missing_context", []),
            applicability_results=state.get("applicability_results", []),
            gap_results=state.get("gap_results", []),
        )
        status = "NEEDS_USER_INPUT" if state.get("missing_context") else "COMPLETED"
    return {"finding_ids": [item.id for item in findings], "status": status}
