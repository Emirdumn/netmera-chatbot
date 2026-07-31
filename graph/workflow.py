"""Grafı kurar: memory -> orchestrator -> uzman agent (veya clarify/escalate)
-> (gerekirse) escalation -> contact_form (ad/e-posta eksikse sorar) -> human_wait.

Checkpointer olarak SqliteSaver kullanılır, thread_id = session_id — bu sayede
human_wait_node'daki interrupt() sonrası Command(resume=...) ile aynı oturumdan
devam edilebilir.
"""
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from config.settings import CHECKPOINT_DB_PATH
from graph.nodes import (
    clarify_node,
    contact_form_node,
    domain_guard_node,
    escalation_node,
    general_node,
    human_wait_node,
    memory_node,
    orchestrator_node,
    sales_node,
    support_node,
    technical_node,
)
from graph.state import HelpdeskState

TARGET_AGENT_TO_NODE = {
    "sales": "sales_node",
    "support": "support_node",
    "technical": "technical_node",
    "general": "general_node",
}

ACTION_TO_NODE = {
    "escalate": "escalation_node",
    "clarify": "clarify_node",
}


def _route_after_orchestrator(state):
    action = state.get("orchestrator_action")
    if action in ACTION_TO_NODE:
        return ACTION_TO_NODE[action]
    return TARGET_AGENT_TO_NODE.get(state.get("intent"), "general_node")


def _route_after_domain_guard(state):
    return END if state.get("domain_guard_handled") else "memory_node"


def _should_escalate(state):
    return "escalation_node" if state.get("escalate") else END


def _default_checkpointer():
    # customer_app ve agent_console ayrı süreçler olarak aynı dosyaya
    # yazacağı için WAL modu gerekiyor (bkz. storage/db.py).
    CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return SqliteSaver(conn)


def build_graph(checkpointer=None):
    graph = StateGraph(HelpdeskState)
    graph.add_node("domain_guard_node", domain_guard_node)
    graph.add_node("memory_node", memory_node)
    graph.add_node("orchestrator_node", orchestrator_node)
    graph.add_node("clarify_node", clarify_node)
    graph.add_node("sales_node", sales_node)
    graph.add_node("support_node", support_node)
    graph.add_node("technical_node", technical_node)
    graph.add_node("general_node", general_node)
    graph.add_node("escalation_node", escalation_node)
    graph.add_node("contact_form_node", contact_form_node)
    graph.add_node("human_wait_node", human_wait_node)

    graph.add_edge(START, "domain_guard_node")
    graph.add_conditional_edges(
        "domain_guard_node",
        _route_after_domain_guard,
        {"memory_node": "memory_node", END: END},
    )
    graph.add_edge("memory_node", "orchestrator_node")
    graph.add_conditional_edges(
        "orchestrator_node",
        _route_after_orchestrator,
        {
            "sales_node": "sales_node",
            "support_node": "support_node",
            "technical_node": "technical_node",
            "general_node": "general_node",
            "escalation_node": "escalation_node",
            "clarify_node": "clarify_node",
        },
    )
    for node_name in ("sales_node", "support_node", "technical_node", "general_node"):
        graph.add_conditional_edges(
            node_name, _should_escalate, {"escalation_node": "escalation_node", END: END}
        )
    graph.add_edge("clarify_node", END)
    graph.add_edge("escalation_node", "contact_form_node")
    graph.add_edge("contact_form_node", "human_wait_node")
    graph.add_edge("human_wait_node", END)

    return graph.compile(checkpointer=checkpointer or _default_checkpointer())
