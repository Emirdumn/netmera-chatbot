"""FAZ 5C — tek domain classifier; off-topic icin ikinci LLM yok."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import domain_guard
from agents.general_agent import GeneralAgent


def test_is_netmera_related_cached_second_call_skips_llm():
    domain_guard._DOMAIN_RELATED_MEMO.clear()
    calls = {"n": 0}

    class _Rel:
        is_netmera_related = False
        reason = "hava durumu"

    class _Wrapped:
        def with_structured_output(self, _schema):
            return self

        def invoke(self, _prompt):
            calls["n"] += 1
            return _Rel()

    original = domain_guard.get_llm
    original_cache_get = domain_guard.cache_get
    original_cache_set = domain_guard.cache_set
    try:
        domain_guard.get_llm = lambda **_: _Wrapped()
        domain_guard.cache_get = lambda *_: None
        domain_guard.cache_set = lambda *_: None

        q = "Bugün hava nasıl?"
        assert domain_guard.is_netmera_related(q) is False
        assert domain_guard.is_netmera_related(q) is False
        assert calls["n"] == 1
        print("PASS: ikinci is_netmera_related LLM cagirmadi")
    finally:
        domain_guard.get_llm = original
        domain_guard.cache_get = original_cache_get
        domain_guard.cache_set = original_cache_set
        domain_guard._DOMAIN_RELATED_MEMO.clear()


def test_decide_domain_feeds_cache_for_general_agent():
    domain_guard._DOMAIN_RELATED_MEMO.clear()
    calls = {"decide": 0, "related": 0}

    class _Decision:
        is_netmera_related = False
        source = "all"
        search_query = "weather"
        reason = "off topic"

    class _DecideWrapped:
        def with_structured_output(self, schema):
            self.schema = schema
            return self

        def invoke(self, _prompt):
            if self.schema is domain_guard.DomainDecision:
                calls["decide"] += 1
                return _Decision()
            calls["related"] += 1
            raise AssertionError("is_netmera_related LLM'i cagrilmamali — cache dolu")

    original = domain_guard.get_llm
    original_cache_get = domain_guard.cache_get
    original_cache_set = domain_guard.cache_set
    try:
        domain_guard.get_llm = lambda **_: _DecideWrapped()
        domain_guard.cache_get = lambda *_: None
        domain_guard.cache_set = lambda *_: None

        q = "Bugün maç var mı?"
        decision = domain_guard._decide_domain(
            {"messages": [{"role": "user", "content": q}]}, q
        )
        assert decision.is_netmera_related is False

        agent = GeneralAgent.__new__(GeneralAgent)
        assert agent._is_on_topic(q) is False
        assert calls["decide"] == 1
        assert calls["related"] == 0
        print("PASS: general_agent domain_guard cache'ini kullandi, ikinci LLM yok")
    finally:
        domain_guard.get_llm = original
        domain_guard.cache_get = original_cache_get
        domain_guard.cache_set = original_cache_set
        domain_guard._DOMAIN_RELATED_MEMO.clear()


def test_general_agent_has_no_own_topic_llm_schema():
    import agents.general_agent as ga

    assert not hasattr(ga, "_TopicRelevance")
    assert "get_llm" not in ga.__dict__
    print("PASS: general_agent kendi domain LLM semasini tasimiyor")


def main():
    tests = [
        test_is_netmera_related_cached_second_call_skips_llm,
        test_decide_domain_feeds_cache_for_general_agent,
        test_general_agent_has_no_own_topic_llm_schema,
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
