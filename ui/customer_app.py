"""Müşteri sohbeti (:8501) — YALNIZCA render/form/polling.

Tum is mantigi `app_services/chat_service.py` icinde: graph calistirma,
interrupt yonetimi (iletisim formu, "bot ile devam et") ve mesaj persist
etme. Bu dosya ne graph'i ne de storage/repository'yi dogrudan bilir.

Mesaj gecmisi tek gercek kaynak olarak SQLite'tan gelir — bu sayede
agent_console'un yazdigi insan cevaplari da ayni ekranda gorunur.

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

from app_services import chat_service

st.set_page_config(page_title="Netmera Yardım", page_icon="💬")

AGENT_LABELS = {
    "general_agent": "🤖 Genel Bilgi Agent",
    "support_agent": "🛠️ Destek Agent",
    "technical_agent": "👨‍💻 Teknik Destek Agent",
    "sales_agent": "💼 Satış Agent",
    "escalation_agent": "🔁 Devir",
    "fast_rag": "⚡ Hızlı Doküman Cevabı",
    "domain_guard": "🛡️ Kapsam Koruma",
}

FIELD_LABELS = {
    "person_name": "Ad", "company": "Şirket", "email": "E-posta", "phone": "Telefon",
    "sector": "Sektör", "app_name": "Uygulama", "platform": "Platform",
    "user_scale": "Kullanıcı sayısı", "is_existing_customer": "Mevcut müşteri",
    "goal": "Amaç", "problem_summary": "Sorun özeti", "error_message": "Hata",
    "sdk_version": "SDK sürümü", "steps_tried": "Denenen adımlar",
}

POLL_SECONDS = 2


def _init_session():
    if "session_id" not in st.session_state:
        st.session_state.session_id = chat_service.create_session("tr")


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
        notes = chat_service.get_notes(session_id)
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


_init_session()
session_id = st.session_state.session_id

st.title("💬 Netmera Yardım Masası")

# Ekrani cizmek icin gereken her sey tek cagrida gelir; bu dosya artik
# ne graph'i ne de DB'yi dogrudan bilir.
conversation = chat_service.load_conversation(session_id)

_render_sidebar(session_id, conversation.messages)

for msg in conversation.messages:
    _render_message(msg)

if conversation.needs_contact_form or conversation.is_waiting:
    if st.button("🤖 Bot ile devam etmek istiyorum"):
        chat_service.resume_bot(session_id)
        st.rerun()

if conversation.needs_contact_form:
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
            chat_service.submit_contact(session_id, name_input, email_input)
            st.rerun()
        else:
            st.error("Lütfen adınızı ve geçerli bir e-posta adresi girin.")
else:
    if conversation.is_waiting:
        st.info("⏳ Bir temsilciye aktarılıyorsunuz, birazdan bağlanacak...")

    user_input = st.chat_input("Mesajınızı yazın...")

    if user_input:
        chat_service.send_message(session_id, user_input)
        st.rerun()

    if conversation.is_waiting:
        time.sleep(POLL_SECONDS)
        st.rerun()
