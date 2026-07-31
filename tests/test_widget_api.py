"""widget_api davranis testleri (AŞAMA 3).

Flag'i test icinde aciyoruz, bu yuzden config/settings import EDILMEDEN
once ortam degiskenleri kuruluyor.

Calistirma:
    venv/bin/python tests/test_widget_api.py
"""
import os
import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# settings import'undan ONCE kurulmali (modul seviyesinde okunuyor).
os.environ["WIDGET_API_ENABLED"] = "true"
os.environ["WIDGET_TOKEN_SECRET"] = "test-secret-en-az-otuz-iki-karakter-uzunlugunda"
os.environ["WIDGET_ALLOWED_ORIGINS"] = "https://example.com"

from fastapi.testclient import TestClient  # noqa: E402

from widget_api import session as token_service  # noqa: E402
from widget_api.main import app  # noqa: E402

client = TestClient(app)


def test_token_roundtrip_and_forgery():
    token = token_service.issue(42)
    assert token_service.verify(token) == 42, "kendi urettigimiz token dogrulanmali"

    assert token_service.verify("42.deadbeef") is None, "sahte imza reddedilmeli"
    assert token_service.verify("42") is None, "imzasiz token reddedilmeli"
    assert token_service.verify("") is None
    assert token_service.verify("abc.def") is None, "sayisal olmayan id reddedilmeli"

    # Baska bir session'in token'i o session'a ait olmali.
    other = token_service.issue(43)
    assert token_service.verify(other) == 43
    assert other != token
    print("PASS: token imzalama/dogrulama, sahtecilik reddediliyor")


def test_auth_required():
    unauthenticated = [
        client.get("/api/widget/conversation"),
        client.post("/api/widget/messages", json={"text": "merhaba"}),
        client.post("/api/widget/contact", json={"name": "A", "email": "a@b.co"}),
        client.post("/api/widget/resume-bot"),
    ]
    for response in unauthenticated:
        assert response.status_code == 401, (
            f"{response.request.url.path} token'siz 401 dondurmeli, "
            f"{response.status_code} geldi"
        )

    bad = client.get(
        "/api/widget/conversation", headers={"Authorization": "Bearer 1.sahte"}
    )
    assert bad.status_code == 401, "gecersiz token 401 olmali"
    print("PASS: token'siz/gecersiz istekler 401")


def test_session_and_conversation_flow():
    created = client.post("/api/widget/session")
    assert created.status_code == 200
    body = created.json()
    assert body["session_id"] > 0
    assert body["token"].startswith(f"{body['session_id']}.")

    auth = {"Authorization": f"Bearer {body['token']}"}

    convo = client.get("/api/widget/conversation", headers=auth)
    assert convo.status_code == 200
    data = convo.json()
    assert data["session_id"] == body["session_id"]
    assert data["messages"] == []
    assert data["is_waiting"] is False
    assert data["needs_contact_form"] is False
    print("PASS: oturum acildi, bos sohbet dondu")


def test_send_message_and_internal_fields_not_leaked():
    body = client.post("/api/widget/session").json()
    auth = {"Authorization": f"Bearer {body['token']}"}

    response = client.post(
        "/api/widget/messages", json={"text": "Netmera nedir?"}, headers=auth
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert len(data["messages"]) >= 2, "kullanici + bot mesaji beklenir"
    assert data["messages"][0]["author"] == "user"
    bot = [m for m in data["messages"] if m["author"] == "bot"]
    assert bot and bot[-1]["text"].strip(), "bot cevabi bos olmamali"

    # Ic isleyis dis dunyaya SIZMAMALI.
    for message in data["messages"]:
        for leaked in ("tool_calls", "orchestrator", "flow_status", "confidence"):
            assert leaked not in message, f"ic alan sizmis: {leaked}"
    print("PASS: mesaj gonderildi; tool_calls/orchestrator disari sizmiyor")


def test_escalation_contact_and_resume_bot():
    body = client.post("/api/widget/session").json()
    auth = {"Authorization": f"Bearer {body['token']}"}

    escalated = client.post(
        "/api/widget/messages",
        json={"text": "beni musteri temsilcisine baglayin"},
        headers=auth,
    ).json()
    assert escalated["needs_contact_form"], "devir sonrasi iletisim formu beklenir"

    invalid = client.post(
        "/api/widget/contact", json={"name": "Ali", "email": "gecersiz"}, headers=auth
    )
    assert invalid.status_code == 422, "gecersiz e-posta reddedilmeli"

    ok = client.post(
        "/api/widget/contact",
        json={"name": "Ali Veli", "email": "ali@example.com"},
        headers=auth,
    ).json()
    assert not ok["needs_contact_form"], "form gonderildikten sonra kapanmali"
    assert ok["is_waiting"], "artik insan bekleniyor olmali"

    resumed = client.post("/api/widget/resume-bot", headers=auth).json()
    assert not resumed["is_waiting"], "bot ile devam sonrasi beklememeli"
    assert resumed["status"] == "bot"
    print("PASS: devir -> iletisim formu -> bot ile devam akisi calisiyor")


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    print("PASS: health ucu calisiyor")


def main():
    tests = [
        test_token_roundtrip_and_forgery,
        test_auth_required,
        test_health_endpoint,
        test_session_and_conversation_flow,
        test_send_message_and_internal_fields_not_leaked,
        test_escalation_contact_and_resume_bot,
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
