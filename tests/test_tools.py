"""Devir araçlarının uçtan uca testi: müsait personel varken handoff,
yokken ticket açıldığını doğrular."""
import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage import repository as repo
from storage.db import get_connection
from tools.availability_tool import availability_tool
from tools.handoff_tool import handoff_tool
from tools.ticket_tool import ticket_tool


def test_handoff_when_staff_available():
    repo.init_db()
    session_id = repo.create_session("tr")
    # config/departments.py: sales departmaninda en az bir cevrimici personel var
    availability = availability_tool.invoke({"department": "sales"})
    assert availability.ok, "sales departmaninda musait personel bulunamadi"

    result = handoff_tool.invoke({
        "session_id": session_id, "department": "sales",
        "summary": "test ozet", "urgency": "normal",
    })
    assert result.ok
    assert "aktar" in result.summary.lower()
    print("PASS: musait personel varken handoff acildi ->", result.summary)


def test_ticket_when_no_staff_available():
    repo.init_db()
    session_id = repo.create_session("tr")

    # engineering departmanindaki tum personeli gecici olarak cevrimdisi yap
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, is_online FROM staff WHERE department = 'engineering'"
    ).fetchall()
    original_states = [(row["id"], row["is_online"]) for row in rows]
    for staff_id, _ in original_states:
        repo.set_staff_online(staff_id, False)

    try:
        availability = availability_tool.invoke({"department": "engineering"})
        assert not availability.ok, "personel cevrimdisi yapildiktan sonra hala musait gorunuyor"

        result = ticket_tool.invoke({
            "session_id": session_id, "department": "engineering",
            "summary": "test ozet", "urgency": "normal",
        })
        assert result.ok
        assert "TICKET-" in result.summary
        print("PASS: musait personel yokken ticket acildi ->", result.summary)
    finally:
        for staff_id, was_online in original_states:
            repo.set_staff_online(staff_id, was_online)


if __name__ == "__main__":
    test_handoff_when_staff_available()
    test_ticket_when_no_staff_available()
    print("\nTum testler basarili.")
