from app.db.session import SessionLocal
from app.tenant.agent.state import TenantAgentState
from app.tenant.findings.service import build_input_snapshot, set_run_input_snapshot
from app.tenant.regulatory.service import (
    load_legal_evidence,
    resolve_requirements_for_manual_scan,
    resolve_requirements_for_trigger,
)
from app.core.config import get_settings


def retrieve_requirements(state: TenantAgentState) -> dict:
    product = state["product_context"]
    trigger = state.get("regulation_trigger") or state.get("manual_scan")
    if product is None or trigger is None or state.get("run_id") is None:
        raise RuntimeError("Tenant Agent context is incomplete before requirement retrieval")
    with SessionLocal() as db:
        if get_settings().runtime_mode == "local" and state.get("regulation_trigger") is not None:
            from app.local_regulations.cache import LocalRegulationCache
            from app.local_regulations.gateway import LocalRegulationGateway
            gateway=LocalRegulationGateway(LocalRegulationCache(get_settings().local_regulation_cache_path))
            requirements=gateway.requirement_contexts_for_event(state["regulation_trigger"].event_id)
            evidence=gateway.evidence_for(requirements)
        elif state.get("regulation_trigger") is not None:
            requirements = resolve_requirements_for_trigger(db, state["regulation_trigger"])
            evidence = load_legal_evidence(db, requirements)
        else:
            requirements = resolve_requirements_for_manual_scan(db, state["manual_scan"])
            evidence = load_legal_evidence(db, requirements)
        snapshot = build_input_snapshot(product, trigger, requirements, evidence)
        set_run_input_snapshot(db, state["run_id"], snapshot)
    return {"requirements": requirements, "legal_evidence": evidence}
