"""Musteri sohbeti icin tek giris noktasi.

Graph invoke, interrupt yonetimi ve mesaj persist etme mantigi burada.
Sunum katmani (Streamlit ya da ileride FastAPI) bu fonksiyonlari cagirir;
kendisi ne `graph.invoke` ne de `repo.add_message` bilir.

TEK GERCEK KAYNAK KURALI
------------------------
Gosterilecek mesajlarin tek kaynagi SQLite `messages` tablosudur
(`repo.get_messages`). LangGraph state'indeki `messages` yalnizca LLM
baglami icindir; ekrana o ASLA basilmaz. Bu ayrim iki kez hataya yol
acti (bkz. graph/nodes.py:human_wait_node ve escalation mesajinin iki kez
yazilmasi), o yuzden burada acikca yaziyor.
"""
from typing import Optional

from langgraph.types import Command

from app_services.schemas import ConversationState, TurnResult
from graph.workflow import build_graph
from storage import repository as repo

_graph = None


def _get_graph():
    """Surec omru boyunca tek graph ornegi.

    Modul seviyesinde tutuluyor — Streamlit her rerun'da scripti bastan
    calistirsa da bu modul bir kez import edilir, yani `st.cache_resource`
    ile ayni etkiyi verir ama Streamlit'e bagimli degildir.
    """
    global _graph
    if _graph is None:
        repo.init_db()
        try:
            from tools.rag_search_tool import warmup_retrieval
            warmup_retrieval()
        except Exception:
            pass
        _graph = build_graph()
    return _graph


def _thread_config(session_id: int) -> dict:
    return {"configurable": {"thread_id": f"session-{session_id}"}}


def _extract_text(message) -> str:
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", str(message))


def get_pending_reason(session_id: int) -> Optional[str]:
    """Thread'de bekleyen interrupt'in sebebi; yoksa None.

    Public — handoff_service de personel yanitindan once buna bakiyor."""
    snapshot = _get_graph().get_state(_thread_config(session_id))
    if not snapshot.interrupts:
        return None
    return snapshot.interrupts[0].value.get("reason")


def resume_with(session_id: int, value) -> None:
    """Bekleyen interrupt'i verilen degerle surdurur.

    Donen sonuc bilerek YOK SAYILIR: resume edilen dugumler (contact_form,
    human_wait) sohbete yeni bir mesaj eklemez; ekleseydi bile gosterimin
    tek kaynagi SQLite oldugu icin oradan okunurdu.
    """
    _get_graph().invoke(Command(resume=value), config=_thread_config(session_id))


# --------------------------------------------------------------------------
# Okuma
# --------------------------------------------------------------------------

def create_session(language: str = "tr") -> int:
    _get_graph()  # DB semasinin hazir oldugundan emin ol
    return repo.create_session(language)


def load_conversation(session_id: int) -> ConversationState:
    """Ekrani cizmek icin gereken her seyi tek seferde toplar."""
    messages = repo.get_messages(session_id)
    session = repo.get_session(session_id)
    status = session["status"] if session else "bot"
    reason = get_pending_reason(session_id)

    return ConversationState(
        session_id=session_id,
        messages=messages,
        status=status,
        is_waiting=status in ("waiting_human", "with_human"),
        pending_reason=reason,
        needs_contact_form=reason == "need_contact_info",
    )


# --------------------------------------------------------------------------
# Yazma
# --------------------------------------------------------------------------

def send_message(session_id: int, text: str) -> TurnResult:
    """Musteri mesajini kaydeder, gerekiyorsa botu calistirir.

    Musteri zaten bir insani bekliyorsa bot CALISTIRILMAZ — mesaj yalnizca
    personel konsoluna duser (bot_skipped=True).
    """
    repo.add_message(session_id, "user", text)

    session = repo.get_session(session_id)
    if session and session["status"] in ("waiting_human", "with_human"):
        return TurnResult(bot_skipped=True)

    result = _get_graph().invoke(
        {"messages": [{"role": "user", "content": text}], "session_id": session_id},
        config=_thread_config(session_id),
    )

    orchestrator = {
        "action": result.get("orchestrator_action"),
        "target_agent": result.get("intent"),
        "reasoning": result.get("orchestrator_reasoning"),
        "is_answer": result.get("orchestrator_is_answer"),
        "topic_changed": result.get("orchestrator_topic_changed"),
    }

    escalated = "__interrupt__" in result

    if escalated:
        # escalation_node'un mesaji ("Sizi ... ekibimize aktariyorum")
        # result["messages"][-1] icinde. Bir kez yazilir; sonraki
        # Command(resume=...) cagrilari YENI mesaj uretmez, bu yuzden
        # onlarin donusu persist EDILMEZ (bkz. submit_contact / resume_bot).
        answer_msg = result["messages"][-1] if result.get("messages") else None
        if answer_msg:
            repo.add_message(
                session_id, "assistant", _extract_text(answer_msg), "escalation_agent",
                orchestrator=orchestrator,
            )
    else:
        answer_msg = result["messages"][-1]
        repo.add_message(
            session_id, "assistant", _extract_text(answer_msg), result.get("agent_name", ""),
            tool_calls=result.get("tool_calls"), sources=result.get("sources"),
            orchestrator=orchestrator, flow_status=result.get("flow_state"),
        )

    return TurnResult(escalated=escalated, orchestrator=orchestrator)


def submit_contact(session_id: int, name: str, email: str) -> None:
    """Ad/e-posta formunu gonderir (contact_form_node interrupt'ini surdurur).

    Donen sonuc PERSIST EDILMEZ: contact_form_node ve human_wait_node yeni
    mesaj eklemez, escalation mesaji zaten send_message() sirasinda
    yazilmisti. Yazilsaydi ayni mesaj sohbette ikiye katlanirdi.
    """
    resume_with(session_id, {"name": name.strip(), "email": email.strip()})


def resume_bot(session_id: int) -> None:
    """Musteri "bot ile devam et" dedi.

    Bekleyen interrupt'lari bos degerle bosaltip oturumu bot moduna alir.
    Bekleyen TALEP (handoff) KAPATILMAZ — personel isterse yine yanitlayabilir.
    """
    # Mevcut grafta en fazla iki ardisik interrupt var (contact_form ->
    # human_wait). Dongu yine de sinirli tutuluyor: her adim ya bir
    # interrupt tuketir ya da cikar.
    for _ in range(5):
        reason = get_pending_reason(session_id)
        if reason == "need_contact_info":
            # Bos ad/e-posta: merge_dict bos degerleri atladigi icin
            # mevcut profil bilgisi BOZULMAZ.
            resume_with(session_id, {"name": "", "email": ""})
        elif reason == "waiting_for_human":
            # Bos yanit: human_wait_node bos resume'da mesaj eklemez.
            resume_with(session_id, "")
        else:
            break

    repo.resume_bot_mode(session_id)


def get_notes(session_id: int) -> dict:
    return repo.get_notes(session_id)
