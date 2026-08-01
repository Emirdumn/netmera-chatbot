"""FAZ 5B — CONTROL karar verir; BRAIN yalnizca celiskili/dusuk-guven durumda."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.orchestrator import Orchestrator, OrchestratorDecision, needs_brain_review


def _decision(**kwargs) -> OrchestratorDecision:
    base = dict(
        is_answer_to_pending_question=False,
        topic_changed=False,
        action="continue",
        target_agent="general",
        language="tr",
        urgency="normal",
        confidence=0.9,
        needs_brain_review=False,
        reasoning="ok",
    )
    base.update(kwargs)
    return OrchestratorDecision(**base)


def test_normal_decision_does_not_need_brain():
    d = _decision(target_agent="support", confidence=0.85)
    assert needs_brain_review(d, {"active_agent": "support"}, "Segment nasıl oluşturulur?") is False
    print("PASS: normal karar brain istemiyor")


def test_low_confidence_needs_brain():
    assert needs_brain_review(_decision(confidence=0.3), {}, "Merhaba") is True
    print("PASS: dusuk confidence brain istiyor")


def test_topic_changed_vs_pending_answer_conflict():
    d = _decision(topic_changed=True, is_answer_to_pending_question=True, confidence=0.9)
    state = {"pending_question": "E-posta adresiniz?", "active_agent": "sales"}
    assert needs_brain_review(d, state, "emir@vmind.com") is True
    print("PASS: topic_changed + pending cevap celiskisi brain istiyor")


def test_general_with_tech_signal_needs_brain():
    d = _decision(target_agent="general", confidence=0.9)
    assert needs_brain_review(d, {}, "iOS SDK push token nasıl alınır?") is True
    print("PASS: general + teknik sinyal brain istiyor")


def test_general_with_real_sales_signal_needs_brain():
    d = _decision(target_agent="general", confidence=0.9)
    assert needs_brain_review(d, {}, "Netmera fiyatlandırma paketleri nedir?") is True
    print("PASS: general + gercek satis sinyali brain istiyor")


def test_general_with_off_topic_price_skips_brain():
    d = _decision(target_agent="general", confidence=0.9)
    assert needs_brain_review(d, {}, "Bitcoin fiyatı ne kadar?") is False
    print("PASS: general + alakasiz fiyat brain istemiyor")


def test_orchestrator_skips_brain_on_confident_control():
    orch = Orchestrator.__new__(Orchestrator)
    orch._control = MagicMock()
    orch._control.invoke.return_value = _decision(target_agent="support", confidence=0.92)
    orch._brain = MagicMock()
    orch._brain.invoke.side_effect = AssertionError("brain cagrilmamali")
    state = {
        "messages": [{"role": "user", "content": "Segment nasıl oluşturulur?"}],
        "active_agent": "support",
        "pending_question": "",
        "customer_profile": {},
        "case_notes": {},
    }
    decision, brain_used = orch.decide(state)
    assert brain_used is False
    assert decision.target_agent == "support"
    print("PASS: emin CONTROL kararinda brain cagrilmadi")


def test_orchestrator_calls_brain_on_conflict():
    orch = Orchestrator.__new__(Orchestrator)
    orch._control = MagicMock()
    orch._control.invoke.return_value = _decision(
        target_agent="general",
        confidence=0.9,
        action="switch",
        topic_changed=True,
        is_answer_to_pending_question=True,
    )
    orch._brain = MagicMock()
    orch._brain.invoke.return_value = _decision(
        target_agent="sales",
        confidence=0.95,
        action="continue",
        is_answer_to_pending_question=True,
        topic_changed=False,
        reasoning="pending cevap, sales'te kal",
    )
    state = {
        "messages": [{"role": "user", "content": "emir@vmind.com"}],
        "active_agent": "sales",
        "pending_question": "E-posta adresiniz nedir?",
        "customer_profile": {},
        "case_notes": {},
    }
    decision, brain_used = orch.decide(state)
    assert brain_used is True
    orch._brain.invoke.assert_called_once()
    assert decision.target_agent == "sales"
    assert decision.action == "continue"
    print("PASS: celiskili CONTROL kararinda brain cagrildi")


def main():
    tests = [
        test_normal_decision_does_not_need_brain,
        test_low_confidence_needs_brain,
        test_topic_changed_vs_pending_answer_conflict,
        test_general_with_tech_signal_needs_brain,
        test_general_with_real_sales_signal_needs_brain,
        test_general_with_off_topic_price_skips_brain,
        test_orchestrator_skips_brain_on_confident_control,
        test_orchestrator_calls_brain_on_conflict,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            failed += 1
            print(f"FAIL: {test.__name__} — {exc}")
    print()
    print("TUM TESTLER GECTI" if not failed else f"{failed} TEST BASARISIZ")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
