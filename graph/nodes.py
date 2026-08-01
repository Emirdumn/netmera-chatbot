"""Her agent'ı bir LangGraph düğüm fonksiyonuna sarar."""
from langgraph.types import interrupt

from agents.domain_guard import try_fast_rag_answer
from agents.escalation_agent import EscalationAgent
from agents.general_agent import GeneralAgent
from agents.memory_agent import (
    CASE_FIELDS,
    PROFILE_FIELDS,
    MemoryAgent,
    should_run_memory_extract,
)
from agents.orchestrator import Orchestrator
from agents.sales_agent import SalesAgent
from agents.support_agent import SupportAgent
from agents.technical_agent import TechnicalAgent
from config.settings import MAX_FAILED_ATTEMPTS
from graph.state import merge_dict
from llm.client import extract_text, get_llm
from storage import repository as repo
from tools.base import clear_tool_calls, get_tool_calls
from tools.sentiment_tool import detect_sentiment

_memory = MemoryAgent()
_orchestrator = Orchestrator()
_general = GeneralAgent()
_support = SupportAgent()
_technical = TechnicalAgent()
_sales = SalesAgent()
_escalation = EscalationAgent()

CLARIFY_PROMPT = """Musteri onceki soruyu anlamadi ve ne istedigini tekrar
sordu. Asagidaki soruyu, kisa bir ozur ile birlikte, daha basit ve acik bir
sekilde tekrar sor (en fazla 2 cumle). Sorunun ozunu DEGISTIRME, sadece daha
anlasilir ifade et. Musteriyle ayni dilde yaz.

Onceki soru: "{pending_question}\""""


def _extract_last_user_text(state):
    message = state["messages"][-1]
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", str(message))


def domain_guard_node(state):
    """Dokumanla guclu eslesmede hizli RAG cevabi; alakasizda kapsam disi.

    Sonuc uretilemezse graph eski memory -> orchestrator -> specialist
    zincirine aynen devam eder.
    """
    result = try_fast_rag_answer(state)
    if result is None:
        # Onceki turdan kalan gate bayraklarini temizle; aksi halde
        # checkpoint'te sticky True kalabilir.
        return {
            "domain_guard_handled": False,
            "domain_guard_mode": "",
        }
    return {
        "messages": [{"role": "assistant", "content": result.answer}],
        "agent_name": result.agent_name,
        "sources": result.sources,
        "confidence": result.confidence,
        "reasoning_trace": result.trace,
        "flow_state": {"flow": "fast_rag_gate", "mode": result.mode},
        "domain_guard_handled": True,
        "domain_guard_mode": result.mode,
        "escalate": False,
        "pending_question": "",
    }


def memory_node(state):
    """FAZ 9 — yapisal bilgi cikarir; saf dokuman sorularinda LLM'i atlar.

    pending_question veya slot/devir sinyali varken ASLA skip edilmez.
    """
    user_text = _extract_last_user_text(state)
    pending = state.get("pending_question", "") or ""

    if not should_run_memory_extract(user_text, pending):
        return {"turn_count": state.get("turn_count", 0) + 1}

    facts = _memory.extract(user_text, pending).model_dump()
    profile_update = {k: facts.get(k) for k in PROFILE_FIELDS}
    case_update = {k: facts.get(k) for k in CASE_FIELDS}

    merged_profile = merge_dict(state.get("customer_profile"), profile_update)
    merged_case = merge_dict(state.get("case_notes"), case_update)

    session_id = state.get("session_id")
    if session_id:
        repo.upsert_notes(session_id, merged_profile, merged_case)

    return {
        "customer_profile": profile_update,
        "case_notes": case_update,
        "turn_count": state.get("turn_count", 0) + 1,
    }


def orchestrator_node(state):
    clear_tool_calls()
    return _orchestrator.run(state)


def clarify_node(state):
    """FAZ 10-f — musteri kafasi karisti (action=clarify). Devir ACMAZ,
    botun bekledigi soruyu daha basit ifade ederek tekrar sorar."""
    pending_question = state.get("pending_question") or ""
    if pending_question:
        llm = get_llm(temperature=0.3, tier="worker", call_site="clarify_node")
        message = extract_text(llm.invoke(CLARIFY_PROMPT.format(pending_question=pending_question)))
    else:
        message = "Özür dilerim, ne konuda yardımcı olabileceğimi tam anlayamadım. Biraz daha detay verir misiniz?"
    return {
        "messages": [{"role": "assistant", "content": message}],
        "agent_name": "clarify",
        "sources": [],
        "pending_question": message,
    }


def _specialist_node(agent, label, state):
    result = agent.run(state)

    failed_attempts = state.get("failed_attempts", 0)
    failed_attempts = failed_attempts + 1 if result.get("needs_human") else 0

    # needs_human zaten escalation acacak — sentiment LLM'i bosuna harcama.
    is_frustrated = False
    if not result.get("needs_human"):
        sentiment = detect_sentiment.invoke({"message": _extract_last_user_text(state)})
        is_frustrated = sentiment.ok and sentiment.data.get("sentiment") == "frustrated"

    if result.get("needs_human"):
        reason = "low_confidence_or_cannot_answer"
    elif is_frustrated:
        reason = "frustrated"
    elif failed_attempts >= MAX_FAILED_ATTEMPTS:
        reason = "max_failed_attempts"
    else:
        reason = ""

    escalate = bool(reason)
    answer_text = result.get("answer", "")

    return {
        "messages": [{"role": "assistant", "content": answer_text}],
        "agent_name": result.get("agent_name", ""),
        "sources": result.get("sources", []),
        "confidence": result.get("confidence", 0.0),
        "tool_calls": get_tool_calls(),
        "reasoning_trace": result.get("reasoning_trace", []),
        "flow_state": result.get("flow_status", {}),
        "failed_attempts": failed_attempts,
        "escalate": escalate,
        "escalation_reason": reason,
        "active_agent": label,
        # Basit sezgisel: cevap soru iceriyorsa bot'un bekledigi bir cevap var demektir.
        "pending_question": answer_text if "?" in answer_text else "",
    }


def sales_node(state):
    return _specialist_node(_sales, "sales", state)


def support_node(state):
    return _specialist_node(_support, "support", state)


def technical_node(state):
    return _specialist_node(_technical, "technical", state)


def general_node(state):
    return _specialist_node(_general, "general", state)


def escalation_node(state):
    result = _escalation.run(state)
    return {
        "messages": [{"role": "assistant", "content": result.get("answer", "")}],
        "agent_name": result.get("agent_name", ""),
        "sources": [],
        "pending_question": "",
        "escalation_summary": result.get("escalation_summary", ""),
        "escalation_department": result.get("escalation_department", ""),
        "escalation_urgency": result.get("escalation_urgency", ""),
    }


def contact_form_node(state):
    """FAZ 15 — devir HER ZAMAN escalation_node'da zaten olusturulmus olur
    (musteri formu terk etse bile talep personel panelinde gorunur); bu
    dugum sadece ad/e-posta zaten bilinmiyorsa bunlari sorup profili
    zenginlestirir."""
    profile = state.get("customer_profile") or {}
    if profile.get("person_name") and profile.get("email"):
        return {}

    contact = interrupt({
        "reason": "need_contact_info",
        "message": (
            "Sizi ilgili ekibimize aktarabilmemiz için ad soyad ve "
            "e-posta adresinizi alabilir miyiz?"
        ),
    })
    profile_update = {
        "person_name": (contact or {}).get("name", ""),
        "email": (contact or {}).get("email", ""),
    }

    session_id = state.get("session_id")
    if session_id:
        merged_profile = merge_dict(profile, profile_update)
        repo.upsert_notes(session_id, merged_profile, state.get("case_notes") or {})

    return {"customer_profile": profile_update}


def human_wait_node(state):
    human_reply = interrupt({
        "reason": "waiting_for_human",
        "escalation_summary": state.get("escalation_summary", ""),
        "department": state.get("escalation_department", state.get("department")),
    })
    if not human_reply:
        # Musteri "bot ile devam et" ile bu interrupt'i bos deger vererek
        # drain etti — state'e kalici bos "assistant: " mesaji EKLEME,
        # yoksa bu thread'in geri kalaninda her _format_history cagrisinda
        # bir baglam slotunu bosuna isgal eder.
        return {}
    # LangChain mesaj rolu olarak sadece standart rolleri kabul ediyor;
    # personelin yaniti musteri tarafindan "assistant" gibi gorunur.
    # SQLite mesaj tablosunda ayrimi 'human_agent' rolu + agent_name koruyor.
    return {"messages": [{"role": "assistant", "content": human_reply}]}
