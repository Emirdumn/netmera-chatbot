"""Personel paneli (:8502) — YALNIZCA render/form/polling.

Tum is mantigi `app_services/handoff_service.py` icinde: kuyruk, devralma,
personel yaniti (gerekiyorsa LangGraph interrupt'ini surdurme) ve kapatma.
Bu dosya ne graph'i ne de storage/repository'yi dogrudan bilir.
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app_services import handoff_service as svc
from config.departments import DEPARTMENTS

st.set_page_config(page_title="Netmera Personel Paneli", page_icon="🧑‍💼", layout="wide")

FIELD_LABELS = {
    "person_name": "Ad", "company": "Şirket", "email": "E-posta", "phone": "Telefon",
    "sector": "Sektör", "app_name": "Uygulama", "platform": "Platform",
    "user_scale": "Kullanıcı sayısı", "is_existing_customer": "Mevcut müşteri",
    "goal": "Amaç", "problem_summary": "Sorun özeti", "error_message": "Hata",
    "sdk_version": "SDK sürümü", "steps_tried": "Denenen adımlar",
}

QUICK_REPLIES = [
    "Merhaba, ben Netmera destek ekibindenim. Size nasıl yardımcı olabilirim?",
    "Konuyu inceliyorum, kısa süre içinde dönüş yapacağım.",
    "Bu işlem için panelden şu adımları izleyebilirsiniz — detayı yazıyorum.",
    "Gerekli notu aldım. Başka yardımcı olabileceğim bir konu var mı?",
]

POLL_SECONDS = 2
_URGENCY_STYLE = {
    "high": "🔴 yüksek",
    "urgent": "🔴 acil",
    "normal": "🟡 normal",
    "low": "🟢 düşük",
}


def _wait_minutes(created_at):
    created = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return max(0, int((now - created).total_seconds() // 60))


def _urgency_label(urgency: str) -> str:
    key = (urgency or "normal").lower()
    return _URGENCY_STYLE.get(key, f"🟡 {urgency or 'normal'}")


def _render_customer_notes(session_id):
    notes = svc.get_notes(session_id)
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


def _render_messages(messages):
    for msg in messages:
        role = "user" if msg["role"] == "user" else "assistant"
        avatar = "👤" if msg["role"] == "human_agent" else None
        with st.chat_message(role, avatar=avatar):
            if msg["role"] == "user":
                st.caption("Müşteri")
            elif msg["role"] == "human_agent":
                st.caption(f"Temsilci · {msg['agent_name'] or 'Personel'}")
            else:
                label = msg["agent_name"] or "Bot"
                st.caption(f"Bot · {label}")
            st.write(msg["content"])
            sources = msg.get("sources") or []
            if sources:
                st.caption("Kaynaklar: " + " · ".join(sources[:3]))


st.title("🧑‍💼 Netmera Personel Paneli")
st.caption("Canlı destek kuyruğu — widget ve müşteri panelinden gelen devirler burada.")

if "staff_id" not in st.session_state:
    st.session_state.staff_id = None

with st.sidebar:
    st.header("Kimlik")
    if st.session_state.staff_id is None:
        all_staff = svc.list_all_staff()
        options = list(range(len(all_staff)))
        staff_label = lambda i: (
            f"{all_staff[i]['name']} ({DEPARTMENTS.get(all_staff[i]['department'], {}).get('name', all_staff[i]['department'])})"
        )
        selected_idx = st.selectbox("Personel", options, format_func=staff_label) if options else None
        password = st.text_input("Şifre", type="password")
        if st.button("Giriş yap"):
            if selected_idx is None:
                st.error("Personel listesi boş.")
            elif svc.verify_staff_password(all_staff[selected_idx]["id"], password):
                candidate = all_staff[selected_idx]
                st.session_state.staff_id = candidate["id"]
                st.session_state.staff_name = candidate["name"]
                st.session_state.department = candidate["department"]
                svc.set_staff_online(candidate["id"], True)
                st.rerun()
            else:
                st.error("Yanlış şifre.")
    else:
        st.markdown(f"👤 **{st.session_state.staff_name}** — {DEPARTMENTS[st.session_state.department]['name']}")
        online = st.toggle("Çevrimiçi ol", value=True, key="online_toggle")
        svc.set_staff_online(st.session_state.staff_id, online)
        if online:
            st.success("Çevrimiçisiniz — yeni talepler kuyruğa düşer.")
        else:
            st.warning("Çevrimdışısınız — yeni talep alma durur (mevcut sohbet devam eder).")
        if st.button("Çıkış yap"):
            svc.set_staff_online(st.session_state.staff_id, False)
            st.session_state.staff_id = None
            st.session_state.staff_name = None
            st.session_state.department = None
            st.session_state.active_handoff_id = None
            st.session_state.pop("online_toggle", None)
            st.session_state.pop("draft_reply", None)
            st.rerun()

if st.session_state.staff_id is None:
    st.info("Devam etmek için lütfen giriş yapın.")
    st.stop()

department = st.session_state.department
staff_name = st.session_state.staff_name

if "active_handoff_id" not in st.session_state:
    st.session_state.active_handoff_id = None
if "draft_reply" not in st.session_state:
    st.session_state.draft_reply = ""

if st.session_state.active_handoff_id is None:
    pending = svc.list_pending(department)
    max_wait = max((_wait_minutes(h["created_at"]) for h in pending), default=0)

    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.subheader("Bekleyen Devirler")
        st.caption(
            f"{DEPARTMENTS[department]['name']} kuyruğu · "
            f"{len(pending)} bekleyen · en uzun bekleme {max_wait} dk"
        )
    with head_r:
        if st.button("🔄 Yenile kuyruk", use_container_width=True):
            st.rerun()

    if not pending:
        st.info("Şu an bekleyen talep yok. Yeni devir gelince bu liste otomatik güncellenir.")
    for h in pending:
        dept_name = DEPARTMENTS.get(h["department"], {}).get("name", h["department"])
        wait_m = _wait_minutes(h["created_at"])
        with st.container(border=True):
            top = st.columns([4, 1])
            with top[0]:
                st.markdown(
                    f"**#{h['id']} · {dept_name}** · {_urgency_label(h['urgency'])} · "
                    f"bekleme **{wait_m} dk**"
                )
                if h.get("reason"):
                    st.caption(f"Sebep: {h['reason']}")
                st.write(h["summary"])
                preview = h.get("last_user_message") or ""
                if preview:
                    st.markdown(f"> 💬 _{preview}_")
            with top[1]:
                if st.button("Devral", key=f"claim-{h['id']}", type="primary", use_container_width=True):
                    if svc.claim(h["id"], staff_name, department):
                        st.session_state.active_handoff_id = h["id"]
                        st.session_state.draft_reply = ""
                        st.rerun()
                    else:
                        st.error("Bu talep başka bir departmana ait, devralınamadı.")

    time.sleep(POLL_SECONDS)
    st.rerun()

else:
    handoff = svc.get_handoff(st.session_state.active_handoff_id)
    if not handoff or handoff["status"] == "closed":
        st.session_state.active_handoff_id = None
        st.rerun()

    session_id = handoff["session_id"]
    dept_name = DEPARTMENTS.get(handoff["department"], {}).get("name", handoff["department"])
    messages = svc.get_messages(session_id)

    meta_l, meta_r = st.columns([3, 1])
    with meta_l:
        st.subheader(f"Canlı sohbet · Oturum #{session_id}")
        st.caption(
            f"{dept_name} · {_urgency_label(handoff['urgency'])} · "
            f"özet: {handoff['summary']}"
        )
    with meta_r:
        if st.button("← Kuyruğa dön", use_container_width=True):
            st.session_state.active_handoff_id = None
            st.rerun()

    _render_customer_notes(session_id)

    chat_col, action_col = st.columns([2, 1])
    with chat_col:
        st.markdown("**Konuşma**")
        _render_messages(messages)
        st.caption(f"{len(messages)} mesaj · yeni müşteri mesajı için sağdaki yenile’yi kullanın")

    with action_col:
        st.markdown("**Yanıt**")
        if st.button("🔄 Konuşmayı yenile", use_container_width=True):
            st.rerun()
        st.caption("Hızlı yanıt")
        for i, text in enumerate(QUICK_REPLIES):
            if st.button(text[:48] + ("…" if len(text) > 48 else ""), key=f"qr-{i}", use_container_width=True):
                st.session_state.draft_reply = text
                st.rerun()

        with st.form("reply_form", clear_on_submit=True):
            reply_text = st.text_area(
                "Yanıtınız",
                value=st.session_state.draft_reply,
                height=160,
                placeholder="Müşteriye yazın…",
            )
            submitted = st.form_submit_button("Gönder", type="primary", use_container_width=True)
            if submitted and reply_text.strip():
                svc.send_reply(session_id, staff_name, reply_text)
                st.session_state.draft_reply = ""
                st.rerun()

        if st.button("Talebi kapat", use_container_width=True):
            svc.close(handoff["id"])
            st.session_state.active_handoff_id = None
            st.session_state.draft_reply = ""
            st.rerun()

    # Aktif sohbette otomatik poll YOK — form yazisini siler.
    # Yeni musteri mesaji icin "Konuşmayı yenile" kullanin.
