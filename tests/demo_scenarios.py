"""6 demo senaryosunu otomatik oynatır, hangi agent'ın devreye girdiğini ve
hangi tool'ların çalıştığını yazdırır (bkz. PLAN_MULTI_AGENT.md FAZ 8)."""
import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph.workflow import build_graph
from storage import repository as repo

SCENARIOS = [
    {
        "name": "1. Genel bilgi",
        "message": "Netmera nedir, ne işe yarar?",
        "expect_intent": {"general"},
        "expect_escalate": False,
    },
    {
        "name": "2. Panel kullanımı",
        "message": "Kural bazlı segment nasıl oluşturulur?",
        "expect_intent": {"support"},
        "expect_escalate": False,
    },
    {
        "name": "3. Teknik (yeni yetenek)",
        "message": "iOS'ta push izni nasıl isteniyor?",
        "expect_intent": {"technical"},
        "expect_escalate": False,
    },
    {
        "name": "4. Satış -> insana devir",
        "message": "Netmera almak istiyorum, bir satış temsilcisiyle görüşebilir miyim?",
        "expect_intent": {"sales", "handoff_request"},
        "expect_escalate": True,
    },
    {
        "name": "5. Destek -> çözemedi -> devir",
        "message": "Push bildirimlerim 3 gündür gitmiyor, hesabımda bir sorun var",
        "expect_intent": {"support", "technical"},
        "expect_escalate": True,
    },
    {
        "name": "6. Kapsam dışı",
        "message": "Bugün hava nasıl?",
        "expect_intent": {"general"},
        "expect_escalate": False,
    },
]


# FAZ 14-e — PLAN_ORCHESTRATOR.md'nin kendi bug raporundaki 4 adımlık
# konuşma: bilgi kaybı + yanlış yönlendirme + gereksiz devir bir daha
# yaşanmasın diye regresyon testi olarak burada tutulur.
ORCHESTRATOR_REGRESSION_TURNS = [
    ("Fiyatlandırma hakkında bilgi almak istiyorum", "sales", False),
    ("Emir Duman Vmind Bilgi teknolojileri Kahve siparisi uygulamasi 1000 kullanici", "sales", False),
    ("Anlamadım benden ne istedin", "sales", False),
    ("iOS SDK entegrasyonu nasıl yapılır", "technical", False),
]


def _extract_text(message):
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", str(message))


def run_orchestrator_regression():
    repo.init_db()
    session_id = repo.create_session("tr")
    graph = build_graph()
    thread_config = {"configurable": {"thread_id": f"regression-{session_id}"}}

    print("=== FAZ 14-e regresyon: PLAN_ORCHESTRATOR.md bug senaryosu ===")
    all_passed = True
    for i, (message, expected_agent, expect_escalate) in enumerate(ORCHESTRATOR_REGRESSION_TURNS, start=1):
        result = graph.invoke(
            {"messages": [{"role": "user", "content": message}], "session_id": session_id},
            config=thread_config,
        )
        active_agent = result.get("active_agent")
        escalated = "__interrupt__" in result
        passed = active_agent == expected_agent and escalated == expect_escalate
        all_passed = all_passed and passed
        status = "PASS" if passed else "FAIL"
        answer = _extract_text(result["messages"][-1]) if result.get("messages") else ""
        print(f"[{status}] tur {i}: {message!r}")
        print(f"   beklenen_agent={expected_agent} bulunan={active_agent} escalate={escalated}")
        print(f"   cevap: {answer[:150]}")

    print("PASS: regresyon senaryosu tamamen basarili.\n" if all_passed
          else "FAIL: regresyon senaryosunda sapma var.\n")
    return all_passed


def run_scenario(graph, scenario, session_id):
    thread_config = {"configurable": {"thread_id": f"demo-{session_id}"}}
    result = graph.invoke(
        {"messages": [{"role": "user", "content": scenario["message"]}], "session_id": session_id},
        config=thread_config,
    )
    escalated = "__interrupt__" in result
    intent = result.get("intent")
    agent_name = result.get("agent_name", "")
    tool_names = [c["tool"] for c in result.get("tool_calls", [])]
    answer_text = _extract_text(result["messages"][-1]) if result.get("messages") else ""

    passed = intent in scenario["expect_intent"] and escalated == scenario["expect_escalate"]

    return {
        "passed": passed,
        "intent": intent,
        "escalated": escalated,
        "agent_name": agent_name,
        "tool_calls": tool_names,
        "answer_preview": answer_text[:120],
    }


def main():
    repo.init_db()
    graph = build_graph()

    results = []
    for scenario in SCENARIOS:
        session_id = repo.create_session("tr")
        r = run_scenario(graph, scenario, session_id)
        results.append((scenario, r))

        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {scenario['name']}")
        print(f"   Soru: {scenario['message']}")
        print(f"   intent={r['intent']}  escalate={r['escalated']}  agent={r['agent_name']}")
        print(f"   tool_calls: {r['tool_calls']}")
        print(f"   cevap: {r['answer_preview']}")
        print()

    passed_count = sum(1 for _, r in results if r["passed"])
    print(f"Sonuc: {passed_count}/{len(SCENARIOS)} senaryo beklenen sekilde calisti.\n")

    run_orchestrator_regression()


if __name__ == "__main__":
    main()
