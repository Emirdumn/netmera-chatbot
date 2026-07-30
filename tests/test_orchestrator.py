"""Orkestratörün PLAN_ORCHESTRATOR.md'de tarif edilen hata zincirini
düzelttiğini doğrular: yapışkan yönlendirme (sticky routing) + clarify
aksiyonu (gereksiz devir açmama)."""
import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph.workflow import build_graph
from storage import repository as repo


def _extract_text(message):
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", str(message))


def main():
    repo.init_db()
    session_id = repo.create_session("tr")
    graph = build_graph()
    thread_config = {"configurable": {"thread_id": f"orchestrator-test-{session_id}"}}

    turns = [
        ("1. Fiyatlandırma sorusu", "Fiyatlandırma hakkında bilgi almak istiyorum", "sales"),
        ("2. Bilgi verme (yapışkanlık testi ★)", "Emir Duman Vmind Bilgi teknolojileri Kahve siparisi uygulamasi 1000 kullanici", "sales"),
        ("3. Kafa karışıklığı (clarify testi ★)", "Anlamadım benden ne istedin", "sales"),
        ("4. Konu değişimi", "iOS SDK entegrasyonu nasıl yapılır", "technical"),
    ]

    all_passed = True
    for label, message, expected_agent in turns:
        result = graph.invoke(
            {"messages": [{"role": "user", "content": message}], "session_id": session_id},
            config=thread_config,
        )
        active_agent = result.get("active_agent")
        action = result.get("orchestrator_action")
        reasoning = result.get("orchestrator_reasoning", "")
        answer = _extract_text(result["messages"][-1]) if result.get("messages") else ""

        passed = active_agent == expected_agent
        all_passed = all_passed and passed
        status = "PASS" if passed else "FAIL"

        print(f"[{status}] {label}")
        print(f"   Mesaj: {message}")
        print(f"   beklenen_agent={expected_agent}  bulunan_agent={active_agent}  action={action}")
        print(f"   reasoning: {reasoning}")
        print(f"   cevap: {answer[:150]}")
        print(f"   customer_profile: {result.get('customer_profile')}")
        print()

    print("Tum turlar basarili." if all_passed else "BAZI TURLAR BASARISIZ.")


if __name__ == "__main__":
    main()
