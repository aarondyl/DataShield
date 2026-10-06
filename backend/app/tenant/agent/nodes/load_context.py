from app.db.session import SessionLocal
from app.tenant.agent.state import TenantAgentState
from app.tenant.context.service import load_product_context


def load_tenant_context(state: TenantAgentState) -> dict:
    with SessionLocal() as db:
        context = load_product_context(db, state["tenant_id"], state["product_id"])
    return {
        "product_context": context,
        "product_twin_version_id": context.product_twin_version_id,
    }
