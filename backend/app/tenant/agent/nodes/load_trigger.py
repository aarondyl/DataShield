from app.db.session import SessionLocal
from app.tenant.agent.state import TenantAgentState
from app.tenant.regulatory.schemas import ManualScanContext
from app.tenant.regulatory.service import load_regulation_trigger
from app.core.config import get_settings


def load_trigger(state: TenantAgentState) -> dict:
    if state["trigger_type"] == "REGULATION_CHANGE":
        if get_settings().runtime_mode == "local":
            from app.local_regulations.cache import LocalRegulationCache
            from app.local_regulations.gateway import LocalRegulationGateway
            trigger=LocalRegulationGateway(LocalRegulationCache(get_settings().local_regulation_cache_path)).trigger(state.get("trigger_id") or "")
            return {"regulation_trigger": trigger, "manual_scan": None}
        with SessionLocal() as db:
            trigger = load_regulation_trigger(db, state.get("trigger_id") or "")
        return {"regulation_trigger": trigger, "manual_scan": None}
    if state["trigger_type"] in {"MANUAL_SCAN", "FEEDBACK_REANALYSIS"}:
        scan = ManualScanContext(
            regulation_id=state.get("regulation_id"),
            requirement_ids=state.get("requirement_ids", []),
            query=state.get("query", ""),
        )
        return {"regulation_trigger": None, "manual_scan": scan}
    raise ValueError(f"Unsupported Tenant Agent trigger type: {state['trigger_type']}")
