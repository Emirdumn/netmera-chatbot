"""LangGraph state şeması."""
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


def merge_dict(left, right):
    """customer_profile / case_notes icin reducer.

    Yeni deger None, "" veya [] ise eskisi korunur — bilgi asla silinmez.
    Liste alanlari birlestirilir (union, sira + tekillik korunarak).
    Diger degerler (False dahil) doğrudan uzerine yazar.
    """
    left = left or {}
    right = right or {}
    merged = dict(left)
    for key, new_value in right.items():
        if new_value is None or new_value == "" or new_value == []:
            continue
        if isinstance(new_value, list):
            existing = merged.get(key) or []
            combined = list(existing)
            for item in new_value:
                if item not in combined:
                    combined.append(item)
            merged[key] = combined
        else:
            merged[key] = new_value
    return merged


class HelpdeskState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    session_id: int
    language: str
    intent: str
    department: str
    urgency: str
    retrieved: list
    confidence: float
    tool_calls: list
    escalate: bool
    escalation_reason: str
    escalation_summary: str
    escalation_department: str
    escalation_urgency: str
    failed_attempts: int
    handoff_id: int
    lead: dict
    agent_name: str
    sources: list
    # FAZ 9 — çalışan bellek (working memory)
    customer_profile: Annotated[dict, merge_dict]
    case_notes: Annotated[dict, merge_dict]
    active_agent: str
    pending_question: str
    flow_state: dict
    turn_count: int
    # FAZ 10 — orkestratör kararı
    orchestrator_action: str
    orchestrator_reasoning: str
    orchestrator_is_answer: bool
    orchestrator_topic_changed: bool
    orchestrator_brain_reviewed: bool
    # FAZ 12 — ReAct izi ("🧠 agent nasıl düşündü")
    reasoning_trace: list
    # Fast RAG gate — handled ise graph dogrudan END'e gider.
    domain_guard_handled: bool
    domain_guard_mode: str
