"""flows/ mekanizmasının (Slot/Flow) ve sales_agent'ın slot-farkındalıklı
lead akışının doğru çalıştığını doğrular."""
import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.sales_agent import SalesAgent
from flows.sales_lead import sales_lead_flow

ALL_PASS = True


def check(label, condition, detail=""):
    global ALL_PASS
    status = "PASS" if condition else "FAIL"
    ALL_PASS = ALL_PASS and condition
    print(f"[{status}] {label}" + (f" — {detail}" if detail else ""))


def test_missing_slots_mechanics():
    profile = {"company": "Vmind"}
    missing = sales_lead_flow.missing_slots(profile, {})
    missing_names = {s.name for s in missing}
    check(
        "company doluyken missing_slots icinde yok",
        "company" not in missing_names,
        f"missing={missing_names}",
    )
    check(
        "diger 4 slot hala eksik",
        missing_names == {"person_name", "email", "app_name", "user_scale"},
        f"missing={missing_names}",
    )
    check("flow tamamlanmadi (is_complete=False)", not sales_lead_flow.is_complete(profile, {}))

    full_profile = {
        "person_name": "Emir Duman", "company": "Vmind",
        "email": "emir@vmind.com", "app_name": "Kahve Uygulaması",
        "user_scale": "1000",
    }
    check("tum slotlar doluyken is_complete=True", sales_lead_flow.is_complete(full_profile, {}))


def test_sales_agent_does_not_reask_known_slot():
    agent = SalesAgent()
    state = {
        "messages": [{"role": "user", "content": "Fiyat bilgisi almak istiyorum"}],
        "customer_profile": {"company": "Vmind Bilgi Teknolojileri"},
        "case_notes": {},
        "language": "tr",
    }
    result = agent.run(state)
    answer = result["answer"]
    check(
        "sirket zaten biliniyorsa tekrar sorulmuyor",
        "şirket" not in answer.lower(),
        f"answer={answer!r}",
    )
    check("needs_human=False (devir acilmiyor)", not result["needs_human"])
    check("en fazla 2 soru soruluyor", answer.count("?") <= 2, f"answer={answer!r}")


def test_sales_agent_completes_when_all_slots_filled():
    agent = SalesAgent()
    state = {
        "messages": [{"role": "user", "content": "emir@vmind.com.tr"}],
        "customer_profile": {
            "person_name": "Emir Duman", "company": "Vmind Bilgi Teknolojileri",
            "email": "emir@vmind.com.tr", "app_name": "Kahve sipariş uygulaması",
            "user_scale": "1000",
        },
        "case_notes": {},
        "language": "tr",
    }
    result = agent.run(state)
    check(
        "tum slotlar doluyken lead tamamlaniyor (RAG/devir degil)",
        "ilettim" in result["answer"].lower() or "teşekkür" in result["answer"].lower(),
        f"answer={result['answer']!r}",
    )
    check("needs_human=False", not result["needs_human"])


if __name__ == "__main__":
    test_missing_slots_mechanics()
    test_sales_agent_does_not_reask_known_slot()
    test_sales_agent_completes_when_all_slots_filled()
    print("\nTum testler basarili." if ALL_PASS else "\nBAZI TESTLER BASARISIZ.")
