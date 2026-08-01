"""Fast RAG domain guard davranis testleri.

Bu testler LLM'e ya da Chroma'ya gitmez; semantic probe ve LLM karar/cevap
fonksiyonlari monkey-patch edilir. Amac graph'in basina eklenen gate'in
sozlesmesini korumak.
"""
import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import domain_guard
from graph.nodes import domain_guard_node
from tools.base import ToolResult


def _probe(similarity=0.72, source="website"):
    return ToolResult(
        ok=True,
        data=[
            {
                "text": "Netmera is an omnichannel customer engagement platform.",
                "similarity": similarity,
                "heading_path": "About Netmera",
                "url": "https://netmera.com/",
                "source": source,
            }
        ],
        summary=f"en iyi benzerlik: {similarity}",
        sources=["https://netmera.com/"],
    )


class _Answer:
    answer = "Netmera, omnichannel müşteri etkileşim platformudur."
    can_answer = True


def test_high_semantic_match_answers_without_domain_llm():
    calls = {"domain": 0}
    original_probe = domain_guard.semantic_probe
    original_answer = domain_guard._answer_from_context
    original_decide = domain_guard._decide_domain
    original_cache_get = domain_guard.cache_get
    original_cache_set = domain_guard.cache_set
    try:
        domain_guard.semantic_probe = lambda *_, **__: _probe(0.73)
        domain_guard._answer_from_context = lambda *_: _Answer()

        def fail_decide(*_):
            calls["domain"] += 1
            raise AssertionError("domain LLM yüksek semantik eşleşmede çağrılmamalı")

        domain_guard._decide_domain = fail_decide
        domain_guard.cache_get = lambda *_: None
        domain_guard.cache_set = lambda *_: None

        result = domain_guard.try_fast_rag_answer({
            "messages": [{"role": "user", "content": "Netmera nedir?"}]
        })

        assert result is not None and result.handled
        assert result.mode == "semantic_direct"
        assert result.sources == ["https://netmera.com/"]
        assert calls["domain"] == 0
        print("PASS: guclu semantik eslesmede domain LLM atlandi")
    finally:
        domain_guard.semantic_probe = original_probe
        domain_guard._answer_from_context = original_answer
        domain_guard._decide_domain = original_decide
        domain_guard.cache_get = original_cache_get
        domain_guard.cache_set = original_cache_set


def test_low_match_off_topic_is_rejected_without_handoff():
    original_probe = domain_guard.semantic_probe
    original_decide = domain_guard._decide_domain
    original_cache_get = domain_guard.cache_get
    original_cache_set = domain_guard.cache_set
    try:
        domain_guard.semantic_probe = lambda *_, **__: _probe(0.12)
        domain_guard._decide_domain = lambda *_: domain_guard.DomainDecision(
            is_netmera_related=False,
            source="all",
            search_query="weather today",
            reason="Hava durumu Netmera alanı değil.",
        )
        domain_guard.cache_get = lambda *_: None
        domain_guard.cache_set = lambda *_: None

        result = domain_guard.try_fast_rag_answer({
            "messages": [{"role": "user", "content": "Bugün hava nasıl?"}]
        })

        assert result is not None and result.handled
        assert result.mode == "off_topic"
        assert "sadece Netmera" in result.answer
        assert result.agent_name == "domain_guard"
        print("PASS: alakasiz soru kapsam disi cevapla kapandi")
    finally:
        domain_guard.semantic_probe = original_probe
        domain_guard._decide_domain = original_decide
        domain_guard.cache_get = original_cache_get
        domain_guard.cache_set = original_cache_set


def test_handoff_request_bypasses_gate():
    result = domain_guard.try_fast_rag_answer({
        "messages": [{"role": "user", "content": "Bir temsilciye bağlanmak istiyorum"}]
    })
    assert result is None
    print("PASS: acik temsilci talebi eski escalation akisina birakildi")


def test_greeting_gets_friendly_reply_without_rag():
    original_probe = domain_guard.semantic_probe
    try:
        def fail_probe(*_):
            raise AssertionError("selamlama semantic_probe cagirmamali")

        domain_guard.semantic_probe = fail_probe
        result = domain_guard.try_fast_rag_answer({
            "messages": [{"role": "user", "content": "Merhaba!"}]
        })
        assert result is not None and result.handled
        assert result.mode == "greeting"
        assert "Netmera" in result.answer
        print("PASS: selamlama dostca kisa yolla cevaplandi")
    finally:
        domain_guard.semantic_probe = original_probe


def test_sales_keywords_bypass_gate():
    # Agglutinated Turkish forms must still bypass (fiyatlandirma, paketleri).
    for text in (
        "Netmera fiyatlandirma paketleri nedir?",
        "Demo almak istiyorum",
        "Fiyat nedir?",
        "Push kampanyası ücreti ne kadar?",
    ):
        result = domain_guard.try_fast_rag_answer({
            "messages": [{"role": "user", "content": text}]
        })
        assert result is None, text
    print("PASS: satis/fiyat sorusu slot akisina birakildi")


def test_off_topic_price_does_not_bypass_as_sales():
    """Bitcoin/pizza fiyatı sales akisina kacmamali — domain_guard cevaplasin."""
    original_probe = domain_guard.semantic_probe
    original_decide = domain_guard._decide_domain
    original_cache_get = domain_guard.cache_get
    original_cache_set = domain_guard.cache_set
    try:
        domain_guard.semantic_probe = lambda *_, **__: _probe(0.05)
        domain_guard._decide_domain = lambda *_: domain_guard.DomainDecision(
            is_netmera_related=False,
            source="all",
            search_query="bitcoin price",
            reason="Kripto fiyatı Netmera alanı değil.",
        )
        domain_guard.cache_get = lambda *_: None
        domain_guard.cache_set = lambda *_: None

        for text in (
            "Bitcoin fiyatı ne kadar?",
            "Ethereum price today?",
            "Dolar kuru ne kadar?",
        ):
            assert domain_guard._looks_like_sales_flow(text) is False, text
            result = domain_guard.try_fast_rag_answer({
                "messages": [{"role": "user", "content": text}]
            })
            assert result is not None and result.handled, text
            assert result.mode == "off_topic", text
            assert result.agent_name == "domain_guard", text
        print("PASS: alakasiz fiyat sorusu sales bypass etmedi, domain_guard kapatti")
    finally:
        domain_guard.semantic_probe = original_probe
        domain_guard._decide_domain = original_decide
        domain_guard.cache_get = original_cache_get
        domain_guard.cache_set = original_cache_set


def test_rewrite_path_answers_when_raw_similarity_low():
    original_probe = domain_guard.semantic_probe
    original_answer = domain_guard._answer_from_context
    original_decide = domain_guard._decide_domain
    original_cache_get = domain_guard.cache_get
    original_cache_set = domain_guard.cache_set
    calls = {"n": 0}
    try:
        def probe(query, source="all", top_k=5):
            calls["n"] += 1
            if calls["n"] == 1:
                return _probe(0.20)
            return _probe(0.55, source="dev_guide")

        domain_guard.semantic_probe = probe
        domain_guard._answer_from_context = lambda *_: _Answer()
        domain_guard._decide_domain = lambda *_: domain_guard.DomainDecision(
            is_netmera_related=True,
            source="dev_guide",
            search_query="iOS push permission request",
            reason="SDK sorusu",
        )
        domain_guard.cache_get = lambda *_: None
        domain_guard.cache_set = lambda *_: None

        result = domain_guard.try_fast_rag_answer({
            "messages": [{"role": "user", "content": "iOS'ta push izni nasil?"}]
        })
        assert result is not None and result.handled
        assert result.mode == "llm_rewrite"
        assert calls["n"] == 2
        print("PASS: dusuk ham eslesmede rewrite yolu cevap verdi")
    finally:
        domain_guard.semantic_probe = original_probe
        domain_guard._answer_from_context = original_answer
        domain_guard._decide_domain = original_decide
        domain_guard.cache_get = original_cache_get
        domain_guard.cache_set = original_cache_set


def test_cannot_answer_falls_through_to_agents():
    original_probe = domain_guard.semantic_probe
    original_answer = domain_guard._answer_from_context
    original_decide = domain_guard._decide_domain
    original_cache_get = domain_guard.cache_get
    original_cache_set = domain_guard.cache_set

    class _NoAnswer:
        answer = ""
        can_answer = False

    try:
        domain_guard.semantic_probe = lambda *_, **__: _probe(0.80)
        domain_guard._answer_from_context = lambda *_: _NoAnswer()
        domain_guard._decide_domain = lambda *_: domain_guard.DomainDecision(
            is_netmera_related=True,
            source="website",
            search_query="Netmera overview",
            reason="related",
        )
        domain_guard.cache_get = lambda *_: None
        domain_guard.cache_set = lambda *_: None

        # Yuksek benzerlik ama grounded cevap yok → rewrite denemesi de
        # basarisiz olunca None (eski agent zinciri).
        result = domain_guard.try_fast_rag_answer({
            "messages": [{"role": "user", "content": "Netmera ekip buyuklugu?"}]
        })
        assert result is None
        print("PASS: grounded cevap yoksa gate eski agent zincirine birakir")
    finally:
        domain_guard.semantic_probe = original_probe
        domain_guard._answer_from_context = original_answer
        domain_guard._decide_domain = original_decide
        domain_guard.cache_get = original_cache_get
        domain_guard.cache_set = original_cache_set


def test_domain_guard_node_marks_handled_result():
    original_try = domain_guard.try_fast_rag_answer
    # graph.nodes import sirasinda fonksiyon ismi baglandigi icin node modulunu
    # da patch'liyoruz.
    import graph.nodes as nodes

    original_node_try = nodes.try_fast_rag_answer
    try:
        fake = domain_guard.FastRagResult(
            handled=True,
            answer="Cevap",
            confidence=0.8,
            sources=["https://netmera.com/"],
            agent_name="fast_rag",
            mode="semantic_direct",
            trace=[{"step": "test"}],
        )
        domain_guard.try_fast_rag_answer = lambda *_: fake
        nodes.try_fast_rag_answer = lambda *_: fake

        out = domain_guard_node({"messages": [{"role": "user", "content": "Netmera nedir?"}]})
        assert out["domain_guard_handled"] is True
        assert out["messages"][-1]["content"] == "Cevap"
        assert out["sources"] == ["https://netmera.com/"]
        assert out["escalate"] is False
        print("PASS: graph node handled sonucu END icin isaretliyor")
    finally:
        domain_guard.try_fast_rag_answer = original_try
        nodes.try_fast_rag_answer = original_node_try


def main():
    tests = [
        test_high_semantic_match_answers_without_domain_llm,
        test_low_match_off_topic_is_rejected_without_handoff,
        test_handoff_request_bypasses_gate,
        test_greeting_gets_friendly_reply_without_rag,
        test_sales_keywords_bypass_gate,
        test_off_topic_price_does_not_bypass_as_sales,
        test_rewrite_path_answers_when_raw_similarity_low,
        test_cannot_answer_falls_through_to_agents,
        test_domain_guard_node_marks_handled_result,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL: {test.__name__} — {exc}")
    print()
    print("TUM TESTLER GECTI" if not failed else f"{failed} TEST BASARISIZ")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
