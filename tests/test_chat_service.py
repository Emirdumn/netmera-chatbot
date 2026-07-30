"""app_services/chat_service.py davranis testleri (Faz 1).

Bu testler REFACTOR'IN DAVRANISI DEGISTIRMEDIGINI dogrular. Gercek LLM'e
ve gercek SQLite'a vurur (projedeki mevcut test kalibi boyle), bu yuzden
biraz yavastir.

Calistirma:
    venv/bin/python tests/test_chat_service.py
"""
import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app_services import chat_service, handoff_service
from storage import repository as repo

ESCALATE_MESSAGE = "beni musteri temsilcisine baglayin"


def _assistant_messages(session_id):
    return [m for m in repo.get_messages(session_id) if m["role"] == "assistant"]


def test_normal_bot_answer_is_persisted():
    """Normal bot cevabi DB'ye yaziliyor."""
    session_id = chat_service.create_session("tr")
    result = chat_service.send_message(session_id, "Netmera nedir?")

    messages = repo.get_messages(session_id)
    assert messages[0]["role"] == "user", "kullanici mesaji kaydedilmeli"
    assistants = _assistant_messages(session_id)
    assert len(assistants) == 1, f"tam 1 bot cevabi beklenir, bulundu: {len(assistants)}"
    assert assistants[0]["content"].strip(), "bot cevabi bos olmamali"
    assert not result.bot_skipped
    print("PASS: normal bot cevabi persist ediliyor")


def test_escalation_answer_written_once():
    """Escalation interrupt cevabi TEK KEZ yaziliyor.

    Regresyon: contact form resume edildiginde escalation mesaji ikinci kez
    yazilirsa sohbette ayni metin iki kere gorunur.
    """
    session_id = chat_service.create_session("tr")
    result = chat_service.send_message(session_id, ESCALATE_MESSAGE)
    assert result.escalated, "acik devir talebi escalation tetiklemeli"

    after_send = _assistant_messages(session_id)
    assert len(after_send) == 1, f"escalation sonrasi 1 mesaj beklenir, bulundu: {len(after_send)}"

    state = chat_service.load_conversation(session_id)
    assert state.needs_contact_form, "ad/e-posta formu beklenir"

    chat_service.submit_contact(session_id, "Test Kullanici", "test@example.com")

    after_contact = _assistant_messages(session_id)
    assert len(after_contact) == 1, (
        f"contact form sonrasi HALA 1 mesaj olmali (ikiye katlanmamali), "
        f"bulundu: {len(after_contact)}"
    )

    notes = repo.get_notes(session_id)
    assert notes["profile"].get("email") == "test@example.com", "e-posta profile yazilmali"
    print("PASS: escalation cevabi tek kez yaziliyor, iletisim bilgisi kaydediliyor")


def test_empty_resume_creates_no_empty_message():
    """Bos resume bos bir assistant mesaji uretmiyor.

    Regresyon: human_wait_node bos resume'da {} donmezse graph state'ine
    kalici bos mesaj yazilir ve sonraki her LLM cagrisinda baglam israf olur.
    """
    session_id = chat_service.create_session("tr")
    chat_service.send_message(session_id, ESCALATE_MESSAGE)
    chat_service.resume_bot(session_id)

    for m in repo.get_messages(session_id):
        assert m["content"].strip(), f"bos icerikli mesaj olusmus: {m}"

    # Graph state'inde de bos mesaj olmamali.
    graph = chat_service._get_graph()  # noqa: SLF001 — test icin bilincli
    values = graph.get_state(chat_service._thread_config(session_id)).values
    for m in values.get("messages", []):
        content = m.content if hasattr(m, "content") else m.get("content", "")
        assert content.strip(), "graph state'ine bos mesaj yazilmis"
    print("PASS: bos resume bos mesaj uretmiyor")


def test_resume_bot_returns_session_to_bot_mode():
    """'Bot ile devam et' oturumu bot moduna aliyor, TALEBI KAPATMIYOR."""
    session_id = chat_service.create_session("tr")
    chat_service.send_message(session_id, ESCALATE_MESSAGE)

    handoff_before = repo.get_handoff_for_session(session_id)
    assert handoff_before is not None, "escalation bir talep olusturmali"

    chat_service.resume_bot(session_id)

    state = chat_service.load_conversation(session_id)
    assert not state.is_waiting, "oturum artik beklemede olmamali"
    assert state.status == "bot", f"durum 'bot' olmali, bulundu: {state.status}"
    assert state.pending_reason is None, "bekleyen interrupt kalmamali"

    handoff_after = repo.get_handoff(handoff_before["id"])
    assert handoff_after["status"] == "pending", (
        "talep ACIK kalmali (personel yine yanitlayabilsin)"
    )
    print("PASS: bot ile devam et session'i bot moduna aliyor, talep acik kaliyor")


def test_staff_reply_resumes_graph_when_waiting():
    """Personel yaniti, graph bekliyorsa resume ediyor; beklemiyorsa etmiyor."""
    # (a) Graph gercekten bekliyor -> resume edilmeli
    session_id = chat_service.create_session("tr")
    chat_service.send_message(session_id, ESCALATE_MESSAGE)
    chat_service.submit_contact(session_id, "Ali Veli", "ali@example.com")

    assert chat_service.get_pending_reason(session_id) == "waiting_for_human"
    resumed = handoff_service.send_reply(session_id, "Ayşe Kaya", "Merhaba, yardimci olayim.")
    assert resumed, "graph beklerken resume edilmeliydi"

    human_msgs = [m for m in repo.get_messages(session_id) if m["role"] == "human_agent"]
    assert len(human_msgs) == 1, "personel yaniti kaydedilmeli"

    # (b) Musteri once "bot ile devam et" dediyse -> resume EDILMEMELI
    other_id = chat_service.create_session("tr")
    chat_service.send_message(other_id, ESCALATE_MESSAGE)
    chat_service.resume_bot(other_id)

    resumed2 = handoff_service.send_reply(other_id, "Ayşe Kaya", "Gec kalmis yanit.")
    assert not resumed2, "bekleyen interrupt yokken resume denenmemeli"

    human_msgs2 = [m for m in repo.get_messages(other_id) if m["role"] == "human_agent"]
    assert len(human_msgs2) == 1, "yanit yine de kaydedilmeli (musteri gorebilmeli)"
    print("PASS: personel yaniti yalnizca graph beklerken resume ediyor")


def main():
    repo.init_db()
    tests = [
        test_normal_bot_answer_is_persisted,
        test_escalation_answer_written_once,
        test_empty_resume_creates_no_empty_message,
        test_resume_bot_returns_session_to_bot_mode,
        test_staff_reply_resumes_graph_when_waiting,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL: {t.__name__} — {exc}")
    print()
    print("TUM TESTLER GECTI" if not failed else f"{failed} TEST BASARISIZ")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
