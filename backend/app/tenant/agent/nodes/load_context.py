from app.db.session import SessionLocal
from app.tenant.agent.state import TenantAgentState
from app.tenant.context.service import load_product_context, load_product_context_version


def load_tenant_context(state: TenantAgentState) -> dict:
    with SessionLocal() as db:
        if state.get("trigger_type") == "FEEDBACK_REANALYSIS":
            context = load_product_context_version(db, state["tenant_id"], state["product_id"], state["feedback_twin_version_id"])
        else:
            context = load_product_context(db, state["tenant_id"], state["product_id"])
    return {
        "product_context": context,
        "product_twin_version_id": context.product_twin_version_id,
    }
