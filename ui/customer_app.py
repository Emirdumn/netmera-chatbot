"""Müşteri sohbeti (:8501).

Mesaj gecmisi tek gercek kaynak olarak SQLite'tan (storage/repository.py)
render edilir — bu sayede agent_console'un yazdigi insan cevaplari da ayni
ekranda gorunur. Bot yalnizca session durumu 'bot' iken LangGraph grafini
calistirir; devir sirasinda (waiting_human/with_human) musterinin yazdigi
mesajlar dogrudan DB'ye yazilir, personel paneli devralir.

Not: Streamlit her rerun'da tum sayfayi sifirdan cizer (eklemeli degil), bu
yuzden gecmis mesajlar her seferinde DB'den baştan render edilir — "zaten
gosterildi" diye atlama YAPILMAZ, aksi halde bir sonraki rerun'da mesajlar
ekrandan kaybolur.

FAZ 14: kenar cubugunda 📋 Musteri Notu (canli dolan profil), 🧠 Orkestratör
kararı ve 🔄 Akış durumu panelleri — sistemin ic isleyisini şeffaf gösterir.
"""
import sys
import time
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from langgraph.types import Command

from graph.workflow import build_graph
from storage import repository as repo

st.set_page_config(page_title="Netmera Yardım", page_icon="💬")

AGENT_LABELS = {
    "general_agent": "🤖 Genel Bilgi Agent",
    "support_agent": "🛠️ Destek Agent",
    "technical_agent": "👨‍💻 Teknik Destek Agent",
    "sales_agent": "💼 Satış Agent",
    "escalation_agent": "🔁 Devir",
}

FIELD_LABELS = {
    "person_name": "Ad", "company": "Şirket", "email": "E-posta", "phone": "Telefon",
    "sector": "Sektör", "app_name": "Uygulama", "platform": "Platform",
    "user_scale": "Kullanıcı sayısı", "is_existing_customer": "Mevcut müşteri",
    "goal": "Amaç", "problem_summary": "Sorun özeti", "error_message": "Hata",
    "sdk_version": "SDK sürümü", "steps_tried": "Denenen adımlar",
}

POLL_SECONDS = 2


@st.cache_resource
def get_graph():
    repo.init_db()
    return build_graph()


def _extract_text(message):
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", str(message))


def _init_session():
    if "session_id" not in st.session_state:
        st.session_state.session_id = repo.create_session("tr")


def _render_message(msg):
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    elif msg["role"] == "human_agent":
        with st.chat_message("assistant", avatar="👤"):
            st.caption(f"👤 {msg['agent_name'] or 'Temsilci'}")
            st.write(msg["content"])
    else:
        with st.chat_message("assistant"):
            if msg["agent_name"]:
                st.caption(AGENT_LABELS.get(msg["agent_name"], f"🤖 {msg['agent_name']}"))
            st.write(msg["content"])
            _render_tool_badges(msg.get("tool_calls"))
            _render_sources(msg.get("sources"))


def _render_tool_badges(tool_calls):
    if not tool_calls:
        return
    labels = " · ".join(f"🔧 {c['tool']}" for c in tool_calls)
    with st.expander(labels):
        for c in tool_calls:
            st.markdown(f"**{c['tool']}**  \nargümanlar: `{c['args']}`  \nsonuç: {c['summary']}")


def _render_sources(sources):
    if not sources:
        return
    with st.expander("Kaynaklar"):
        for s in sources:
            st.markdown(f"- {s}")


def _render_sidebar(session_id, messages):
    with st.sidebar:
        st.subheader("📋 Müşteri Notu")
        notes = repo.get_notes(session_id)
        profile = notes.get("profile") or {}
        case_notes = notes.get("case_notes") or {}
        merged = {**profile, **case_notes}
        if not merged:
            st.caption("Henüz bilgi toplanmadı.")
        else:
            for key, value in merged.items():
                if not value:
                    continue
                label = FIELD_LABELS.get(key, key)
                display = ", ".join(value) if isinstance(value, list) else str(value)
                st.markdown(f"**{label}:** {display}")

        last_assistant = next(
            (m for m in reversed(messages) if m["role"] == "assistant"), None
        )

        st.divider()
        st.subheader("🧠 Orkestratör Kararı")
        orch = (last_assistant or {}).get("orchestrator")
        if orch:
            st.markdown(f"**Aksiyon:** `{orch.get('action')}`  →  **Agent:** `{orch.get('target_agent')}`")
            st.caption(orch.get("reasoning", ""))
            st.markdown(
                f"- Bekleyen soruya cevap mı: {'✅' if orch.get('is_answer') else '—'}\n"
                f"- Konu değişti mi: {'✅' if orch.get('topic_changed') else '—'}"
            )
        else:
            st.caption("Henüz karar yok.")

        flow = (last_assistant or {}).get("flow_status")
        if flow:
            st.divider()
            st.subheader("🔄 Akış Durumu")
            st.markdown(f"**{flow['flow']}** — {flow['total']} slottan {flow['filled']}'i dolu")
            st.progress(flow["filled"] / flow["total"] if flow["total"] else 0)


graph = get_graph()
_init_session()
session_id = st.session_state.session_id
thread_config = {"configurable": {"thread_id": f"session-{session_id}"}}

st.title("💬 Netmera Yardım Masası")

messages = repo.get_messages(session_id)
_render_sidebar(session_id, messages)

for msg in messages:
    _render_message(msg)

snapshot = graph.get_state(thread_config)
pending_reason = snapshot.interrupts[0].value.get("reason") if snapshot.interrupts else None
needs_contact_form = pending_reason == "need_contact_info"

session = repo.get_session(session_id)
is_waiting = bool(session) and session["status"] in ("waiting_human", "with_human")

if needs_contact_form:
    # escalation_node zaten calisip talebi olusturdu (bu yuzden is_waiting
    # burada da True olabilir) — bu ekran sadece ad/e-posta toplayip
    # profili zenginlestirir, doldurulmasi beklenen bir insan yaniti
    # olmadigi icin normal chat_input/polling donguleri devre disi kalir.
    st.info("Sizi ilgili ekibimize aktarabilmemiz için birkaç bilgiye ihtiyacımız var.")
    with st.form("contact_form"):
        name_input = st.text_input("Ad Soyad")
        email_input = st.text_input("E-posta")
        submitted = st.form_submit_button("Gönder")
    if submitted:
        if name_input.strip() and "@" in email_input:
            graph.invoke(
                Command(resume={"name": name_input.strip(), "email": email_input.strip()}),
                config=thread_config,
            )
            # contact_form_node/human_wait_node yeni bir mesaj eklemez —
            # escalation_node'un mesaji ilk invoke'ta zaten persist edildi,
            # burada tekrar yazmiyoruz (aksi halde mesaj ikiye katlanir).
            st.rerun()
        else:
            st.error("Lütfen adınızı ve geçerli bir e-posta adresi girin.")
else:
    if is_waiting:
        st.info("⏳ Bir temsilciye aktarılıyorsunuz, birazdan bağlanacak...")

    user_input = st.chat_input("Mesajınızı yazın...")

    if user_input:
        repo.add_message(session_id, "user", user_input)

        if is_waiting:
            # Bot devrede degil, mesaj sadece personel konsoluna dusuyor.
            st.rerun()
        else:
            result = graph.invoke(
                {"messages": [{"role": "user", "content": user_input}], "session_id": session_id},
                config=thread_config,
            )
            orchestrator_info = {
                "action": result.get("orchestrator_action"),
                "target_agent": result.get("intent"),
                "reasoning": result.get("orchestrator_reasoning"),
                "is_answer": result.get("orchestrator_is_answer"),
                "topic_changed": result.get("orchestrator_topic_changed"),
            }

            if "__interrupt__" in result:
                # escalation_node cevabi (ör. "Sizi ... ekibimize aktariyorum")
                # zaten result["messages"][-1] icinde, DB'ye yazip goster.
                answer_msg = result["messages"][-1] if result.get("messages") else None
                if answer_msg:
                    text = _extract_text(answer_msg)
                    repo.add_message(
                        session_id, "assistant", text, "escalation_agent",
                        orchestrator=orchestrator_info,
                    )
            else:
                answer_msg = result["messages"][-1]
                text = _extract_text(answer_msg)
                agent_name = result.get("agent_name", "")
                repo.add_message(
                    session_id, "assistant", text, agent_name,
                    tool_calls=result.get("tool_calls"), sources=result.get("sources"),
                    orchestrator=orchestrator_info, flow_status=result.get("flow_state"),
                )

            st.rerun()

    if is_waiting:
        time.sleep(POLL_SECONDS)
        st.rerun()
