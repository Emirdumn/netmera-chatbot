"""Personel paneli (:8502).

customer_app ile ayni checkpoints.db dosyasini paylasan ayri bir surectir.
Ilk insan cevabinda LangGraph'in interrupt() ile donmus thread'ini
Command(resume=...) ile devam ettirir; sonraki cevaplar dogrudan DB'ye
yazilir (grafin o turu zaten END'e ulasmis olur).
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from langgraph.types import Command

from config.departments import DEPARTMENTS
from graph.workflow import build_graph
from storage import repository as repo

st.set_page_config(page_title="Netmera Personel Paneli", page_icon="🧑‍💼")

FIELD_LABELS = {
    "person_name": "Ad", "company": "Şirket", "email": "E-posta", "phone": "Telefon",
    "sector": "Sektör", "app_name": "Uygulama", "platform": "Platform",
    "user_scale": "Kullanıcı sayısı", "is_existing_customer": "Mevcut müşteri",
    "goal": "Amaç", "problem_summary": "Sorun özeti", "error_message": "Hata",
    "sdk_version": "SDK sürümü", "steps_tried": "Denenen adımlar",
}


@st.cache_resource
def get_graph():
    repo.init_db()
    return build_graph()


def _wait_minutes(created_at):
    created = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return max(0, int((now - created).total_seconds() // 60))


def _render_customer_notes(session_id):
    notes = repo.get_notes(session_id)
    merged = {**(notes.get("profile") or {}), **(notes.get("case_notes") or {})}
    if not merged:
        return
    with st.container(border=True):
        st.markdown("**📋 Müşteri Notu** _(bot'un bu oturumda topladığı bilgiler)_")
        cols = st.columns(2)
        items = [(k, v) for k, v in merged.items() if v]
        for i, (key, value) in enumerate(items):
            label = FIELD_LABELS.get(key, key)
            display = ", ".join(value) if isinstance(value, list) else str(value)
            cols[i % 2].markdown(f"**{label}:** {display}")


graph = get_graph()

st.title("🧑‍💼 Netmera Personel Paneli")

with st.sidebar:
    st.header("Kimlik")
    department = st.selectbox(
        "Departman", list(DEPARTMENTS.keys()),
        format_func=lambda d: DEPARTMENTS[d]["name"],
    )
    staff_list = repo.list_staff(department)
    staff_names = [s["name"] for s in staff_list]
    staff_name = st.selectbox("Personel", staff_names) if staff_names else None

    if staff_name:
        current = next(s for s in staff_list if s["name"] == staff_name)
        online = st.toggle("Çevrimiçi ol", value=bool(current["is_online"]))
        if online != bool(current["is_online"]):
            repo.set_staff_online(current["id"], online)
            st.rerun()

if "active_handoff_id" not in st.session_state:
    st.session_state.active_handoff_id = None

if st.session_state.active_handoff_id is None:
    st.subheader("Bekleyen Devirler")
    pending = repo.list_pending_handoffs()
    if not pending:
        st.caption("Bekleyen talep yok.")
    for h in pending:
        dept_name = DEPARTMENTS.get(h["department"], {}).get("name", h["department"])
        with st.container(border=True):
            st.markdown(
                f"**{dept_name}** · aciliyet: `{h['urgency']}` · "
                f"bekleme: {_wait_minutes(h['created_at'])} dk"
            )
            st.write(h["summary"])
            if st.button("Devral", key=f"claim-{h['id']}", disabled=not staff_name):
                repo.claim_handoff(h["id"], staff_name)
                st.session_state.active_handoff_id = h["id"]
                st.rerun()

    time.sleep(2)
    st.rerun()

else:
    handoff = repo.get_handoff(st.session_state.active_handoff_id)
    if not handoff or handoff["status"] == "closed":
        st.session_state.active_handoff_id = None
        st.rerun()

    session_id = handoff["session_id"]
    thread_config = {"configurable": {"thread_id": f"session-{session_id}"}}

    dept_name = DEPARTMENTS.get(handoff["department"], {}).get("name", handoff["department"])
    st.subheader(f"Oturum #{session_id} — {dept_name}")
    st.caption(f"Özet: {handoff['summary']}")
    _render_customer_notes(session_id)

    messages = repo.get_messages(session_id)
    for msg in messages:
        role = "user" if msg["role"] == "user" else "assistant"
        avatar = "👤" if msg["role"] == "human_agent" else None
        with st.chat_message(role, avatar=avatar):
            label = msg["agent_name"] or ("Müşteri" if msg["role"] == "user" else "")
            if label:
                st.caption(label)
            st.write(msg["content"])

    with st.form("reply_form", clear_on_submit=True):
        reply_text = st.text_area("Yanıtınız")
        submitted = st.form_submit_button("Gönder")
        if submitted and reply_text.strip():
            is_first_reply = not any(m["role"] == "human_agent" for m in messages)
            repo.post_human_reply(session_id, staff_name, reply_text.strip())
            if is_first_reply:
                graph.invoke(Command(resume=reply_text.strip()), config=thread_config)
            st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Kapat"):
            repo.close_handoff(handoff["id"])
            st.session_state.active_handoff_id = None
            st.rerun()
    with col2:
        if st.button("Yenile"):
            st.rerun()
