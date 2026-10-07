"""Explicit Tenant Intelligence state machine."""

from functools import lru_cache

from langgraph.graph import END, StateGraph

from app.tenant.agent.nodes.applicability import analyze_applicability
from app.tenant.agent.nodes.context_check import check_context_sufficiency
from app.tenant.agent.nodes.finding import build_findings
from app.tenant.agent.nodes.gap_analysis import analyze_gaps
from app.tenant.agent.nodes.load_context import load_tenant_context
from app.tenant.agent.nodes.load_trigger import load_trigger
from app.tenant.agent.nodes.persist import persist, start_run
from app.tenant.agent.nodes.retrieve_requirements import retrieve_requirements
from app.tenant.agent.state import TenantAgentState


def build_tenant_graph():
    builder = StateGraph(TenantAgentState)
    builder.add_node("create_run", start_run)
    builder.add_node("load_context", load_tenant_context)
    builder.add_node("load_trigger", load_trigger)
    builder.add_node("retrieve_requirements", retrieve_requirements)
    builder.add_node("check_context_sufficiency", check_context_sufficiency)
    builder.add_node("applicability", analyze_applicability)
    builder.add_node("gap_analysis", analyze_gaps)
    builder.add_node("build_findings", build_findings)
    builder.add_node("persist", persist)
    builder.set_entry_point("create_run")
    builder.add_edge("create_run", "load_context")
    builder.add_edge("load_context", "load_trigger")
    builder.add_edge("load_trigger", "retrieve_requirements")
    builder.add_edge("retrieve_requirements", "check_context_sufficiency")
    builder.add_edge("check_context_sufficiency", "applicability")
    builder.add_edge("applicability", "gap_analysis")
    builder.add_edge("gap_analysis", "build_findings")
    builder.add_edge("build_findings", "persist")
    builder.add_edge("persist", END)
    return builder.compile()


@lru_cache
def get_tenant_graph():
    return build_tenant_graph()
