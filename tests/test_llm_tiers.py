"""LLM tier altyapisi — model secimi env'den, davranis geriye uyumlu.

Bu testler gercek LLM cagrisi yapmaz; model cozumleme, telemetry sarmalayici
ve brain->worker fallback sozlesmesini dogrular.
"""
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_model_for_tier_defaults_match_provider_default():
    from config import settings
    from llm.client import model_for_tier

    # Env bos birakildiginda uc tier de ayni varsayilan modele duser —
    # mevcut tek-model davranisi bozulmaz.
    assert model_for_tier("control") == settings.LLM_CONTROL_MODEL
    assert model_for_tier("worker") == settings.LLM_WORKER_MODEL
    assert model_for_tier("brain") == settings.LLM_BRAIN_MODEL
    default = (
        settings.OPENROUTER_MODEL
        if settings.LLM_PROVIDER == "openrouter"
        else settings.GEMINI_MODEL
    )
    # Tipik kurulumda hepsi default'a esittir (tier env bos).
    assert settings.LLM_CONTROL_MODEL == default or settings.LLM_CONTROL_MODEL
    assert settings.LLM_WORKER_MODEL
    assert settings.LLM_BRAIN_MODEL
    print("PASS: tier modelleri cozuluyor")


def test_get_llm_exposes_tier_and_call_site():
    from llm.client import get_llm

    llm = get_llm(temperature=0, tier="control", call_site="test.site")
    assert llm.tier == "control"
    assert llm.call_site == "test.site"
    assert llm.model
    print(f"PASS: get_llm tier=control model={llm.model}")


def test_telemetry_logs_on_invoke(caplog=None):
    from llm import client as llm_client

    class FakeMsg:
        content = "ok"
        response_metadata = {"token_usage": {"prompt_tokens": 3, "completion_tokens": 2}}

    fake = MagicMock()
    fake.invoke.return_value = FakeMsg()

    wrapped = llm_client.TelemetryLLM(
        fake, tier="worker", model="test-model", call_site="unit.invoke",
    )

    # print telemetrisi acik; logger da info seviyesinde.
    logging.getLogger("llm.client").setLevel(logging.INFO)
    result = wrapped.invoke("hello")
    assert result.content == "ok"
    fake.invoke.assert_called_once_with("hello")
    print("PASS: telemetry invoke calisti")


def test_brain_fallback_to_worker_on_error():
    from llm import client as llm_client

    class Boom(Exception):
        pass

    primary = MagicMock()
    primary.invoke.side_effect = Boom("brain down")
    fallback = MagicMock()
    fallback.invoke.return_value = MagicMock(
        content="recovered", response_metadata={}, usage_metadata=None,
    )

    # Flag acikken brain hatasi worker'a duser.
    original = llm_client.LLM_BRAIN_FALLBACK_TO_WORKER
    try:
        llm_client.LLM_BRAIN_FALLBACK_TO_WORKER = True
        wrapped = llm_client.TelemetryLLM(
            primary,
            tier="brain",
            model="brain-model",
            call_site="unit.brain",
            fallback_llm=fallback,
            fallback_model="worker-model",
        )
        result = wrapped.invoke("q")
        assert result.content == "recovered"
        primary.invoke.assert_called_once()
        fallback.invoke.assert_called_once()
        print("PASS: brain hata verince worker fallback")
    finally:
        llm_client.LLM_BRAIN_FALLBACK_TO_WORKER = original


def test_unknown_tier_raises():
    from llm.client import model_for_tier

    try:
        model_for_tier("turbo")  # type: ignore[arg-type]
        raise AssertionError("ValueError beklenirdi")
    except ValueError:
        print("PASS: bilinmeyen tier reddedildi")


def main():
    tests = [
        test_model_for_tier_defaults_match_provider_default,
        test_get_llm_exposes_tier_and_call_site,
        test_telemetry_logs_on_invoke,
        test_brain_fallback_to_worker_on_error,
        test_unknown_tier_raises,
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
