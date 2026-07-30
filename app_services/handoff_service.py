"""Personel tarafi: kuyruk, devralma, yanit ve kapatma.

`chat_service` ile ayni graph ornegini paylasir — personel yaniti bir
LangGraph interrupt'ini surdurmek zorunda oldugu icin bu sart.
"""
from app_services import chat_service
from storage import repository as repo


def list_pending(department: str | None = None) -> list[dict]:
    return repo.list_pending_handoffs(department)


def get_handoff(handoff_id: int) -> dict | None:
    return repo.get_handoff(handoff_id)


def claim(handoff_id: int, staff_name: str, department: str | None = None) -> bool:
    """Talebi devralir. Departman eslesmezse False doner (kuyruk zaten
    filtreli oldugu icin bu yalnizca yaris durumlarinda tetiklenir)."""
    return repo.claim_handoff(handoff_id, staff_name, department)


def send_reply(session_id: int, staff_name: str, text: str) -> bool:
    """Personel yanitini kaydeder; graph bekliyorsa onu da surdurur.

    Donen deger: graph resume EDILDI mi.

    Karar "ilk yanit mi" sezgisiyle DEGIL, gercek interrupt durumuna
    bakilarak verilir — musteri "bot ile devam et" ile thread'i coktan
    bosaltmis olabilir; o durumda resume anlamsizdir.
    """
    reply = text.strip()
    repo.post_human_reply(session_id, staff_name, reply)

    if chat_service.get_pending_reason(session_id) != "waiting_for_human":
        return False

    chat_service.resume_with(session_id, reply)
    return True


def close(handoff_id: int) -> None:
    """Talebi kapatir ve oturumu bot moduna geri alir."""
    repo.close_handoff(handoff_id)


def list_staff(department: str) -> list[dict]:
    return repo.list_staff(department)


def list_all_staff() -> list[dict]:
    return repo.list_all_staff()


def verify_staff_password(staff_id: int, password: str) -> bool:
    return repo.verify_staff_password(staff_id, password)


def set_staff_online(staff_id: int, is_online: bool) -> None:
    repo.set_staff_online(staff_id, is_online)


def get_notes(session_id: int) -> dict:
    return repo.get_notes(session_id)


def get_messages(session_id: int) -> list[dict]:
    return repo.get_messages(session_id)
