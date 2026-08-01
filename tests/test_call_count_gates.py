"""FAZ 5A — call-count azaltma: sentiment fast path + memory skip kurallari."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.memory_agent import should_run_memory_extract
from tools import sentiment_tool


def test_frustrated_keyword_skips_llm():
    original = sentiment_tool.get_llm
    sentiment_tool.get_llm = MagicMock(side_effect=AssertionError("LLM cagrilmamali"))
    try:
        result = sentiment_tool.detect_sentiment.invoke({"message": "Bu berbat, sinirim bozuldu!!!"})
        assert result.ok and result.data["sentiment"] == "frustrated"
        assert result.data.get("via") == "fast_path"
        print("PASS: frustrated keyword LLM atlandi")
    finally:
        sentiment_tool.get_llm = original


def test_calm_doc_question_skips_llm():
    original = sentiment_tool.get_llm
    sentiment_tool.get_llm = MagicMock(side_effect=AssertionError("LLM cagrilmamali"))
    try:
        result = sentiment_tool.detect_sentiment.invoke(
            {"message": "iOS SDK entegrasyonu nasıl yapılır?"}
        )
        assert result.ok and result.data["sentiment"] == "neutral"
        assert result.data.get("via") == "fast_path"
        print("PASS: sakin dokuman sorusu LLM atlandi")
    finally:
        sentiment_tool.get_llm = original


def test_memory_skip_on_pure_doc_question():
    assert should_run_memory_extract("Push kampanyası nasıl oluşturulur?", "") is False
    assert should_run_memory_extract("Netmera nedir?", "") is False
    print("PASS: saf dokuman sorusunda memory skip")


def test_memory_never_skips_with_pending_question():
    assert should_run_memory_extract("Emir", "Adınızı alabilir miyim?") is True
    assert should_run_memory_extract("ok", "E-posta adresiniz nedir?") is True
    print("PASS: pending_question varken memory skip yok")


def test_memory_never_skips_on_slot_or_escalation_signals():
    assert should_run_memory_extract("mailim emir@vmind.com", "") is True
    assert should_run_memory_extract("iOS platformunda hata alıyorum", "") is True
    assert should_run_memory_extract("Bir temsilciye bağlanmak istiyorum", "") is True
    assert should_run_memory_extract("Demo ve fiyat bilgisi isterim", "") is True
    print("PASS: sinyal varken memory skip yok")


def main():
    tests = [
        test_frustrated_keyword_skips_llm,
        test_calm_doc_question_skips_llm,
        test_memory_skip_on_pure_doc_question,
        test_memory_never_skips_with_pending_question,
        test_memory_never_skips_on_slot_or_escalation_signals,
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
