"""Tek LLM giris noktasi — proje genelinde LLM'e sadece buradan erisilir.

LLM_PROVIDER ayarina gore Gemini (dogrudan) veya OpenRouter (OpenAI-uyumlu
API) kullanilir. Embedding hala lokal (sentence-transformers).

Tier modeli (CONTROL / WORKER / BRAIN):
  get_llm(tier="control"|"worker"|"brain", call_site="...")
Model isimleri env'den okunur; bos birakilirsa provider varsayilanina duser.
Boylece mimari sabit kalir, model secimi operasyonel ayar olur.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Literal

from config.settings import (
    GEMINI_API_KEY,
    LLM_BRAIN_FALLBACK_TO_WORKER,
    LLM_BRAIN_MODEL,
    LLM_CONTROL_MODEL,
    LLM_PROVIDER,
    LLM_REQUEST_TIMEOUT_SECONDS,
    LLM_TELEMETRY_ENABLED,
    LLM_WORKER_MODEL,
    OPENROUTER_API_KEY,
)

logger = logging.getLogger(__name__)

Tier = Literal["control", "worker", "brain"]

_TIER_MODELS = {
    "control": lambda: LLM_CONTROL_MODEL,
    "worker": lambda: LLM_WORKER_MODEL,
    "brain": lambda: LLM_BRAIN_MODEL,
}


def model_for_tier(tier: Tier = "worker") -> str:
    """Tier icin cozulmus model adini dondurur (test/telemetry icin)."""
    if tier not in _TIER_MODELS:
        raise ValueError(f"Bilinmeyen LLM tier: {tier!r} (control|worker|brain)")
    return _TIER_MODELS[tier]()


def _usage_from_result(result: Any) -> dict:
    """LangChain yanitindan token kullanimini best-effort cikarir."""
    usage: dict = {}
    meta = getattr(result, "response_metadata", None) or {}
    if isinstance(meta, dict):
        raw = meta.get("token_usage") or meta.get("usage") or {}
        if isinstance(raw, dict):
            usage = {
                k: raw.get(k)
                for k in ("prompt_tokens", "completion_tokens", "total_tokens",
                          "input_tokens", "output_tokens")
                if raw.get(k) is not None
            }
    usage_meta = getattr(result, "usage_metadata", None)
    if isinstance(usage_meta, dict) and not usage:
        usage = {
            k: usage_meta.get(k)
            for k in ("input_tokens", "output_tokens", "total_tokens")
            if usage_meta.get(k) is not None
        }
    return usage


def _log_llm_call(
    *,
    tier: str,
    model: str,
    call_site: str,
    latency_ms: float,
    ok: bool,
    error: str | None = None,
    usage: dict | None = None,
    fallback_from: str | None = None,
) -> None:
    if not LLM_TELEMETRY_ENABLED:
        return
    parts = [
        f"tier={tier}",
        f"model={model}",
        f"call_site={call_site or '-'}",
        f"latency_ms={latency_ms:.0f}",
        f"ok={ok}",
    ]
    if fallback_from:
        parts.append(f"fallback_from={fallback_from}")
    if usage:
        parts.append("usage=" + ",".join(f"{k}:{v}" for k, v in usage.items()))
    if error:
        parts.append(f"error={error}")
    line = "LLM_CALL " + " ".join(parts)
    logger.info(line)
    # Tool loglari gibi terminale dusmesi icin (Streamlit/Docker loglari).
    print(f"🧠 {line}", flush=True)


class _TelemetryRunnable:
    """invoke() sarmalayicisi — structured_output runnables dahil."""

    def __init__(
        self,
        runnable: Any,
        *,
        tier: Tier,
        model: str,
        call_site: str,
        fallback_runnable: Any | None = None,
        fallback_model: str | None = None,
    ):
        self._runnable = runnable
        self._tier = tier
        self._model = model
        self._call_site = call_site
        self._fallback_runnable = fallback_runnable
        self._fallback_model = fallback_model

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            result = self._runnable.invoke(*args, **kwargs)
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            _log_llm_call(
                tier=self._tier,
                model=self._model,
                call_site=self._call_site,
                latency_ms=latency_ms,
                ok=False,
                error=f"{type(exc).__name__}:{exc}",
            )
            if (
                self._tier == "brain"
                and LLM_BRAIN_FALLBACK_TO_WORKER
                and self._fallback_runnable is not None
            ):
                return self._invoke_fallback(*args, **kwargs)
            raise

        latency_ms = (time.perf_counter() - started) * 1000
        _log_llm_call(
            tier=self._tier,
            model=self._model,
            call_site=self._call_site,
            latency_ms=latency_ms,
            ok=True,
            usage=_usage_from_result(result),
        )
        return result

    def _invoke_fallback(self, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            result = self._fallback_runnable.invoke(*args, **kwargs)
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            _log_llm_call(
                tier="worker",
                model=self._fallback_model or LLM_WORKER_MODEL,
                call_site=self._call_site,
                latency_ms=latency_ms,
                ok=False,
                error=f"{type(exc).__name__}:{exc}",
                fallback_from=self._tier,
            )
            raise
        latency_ms = (time.perf_counter() - started) * 1000
        _log_llm_call(
            tier="worker",
            model=self._fallback_model or LLM_WORKER_MODEL,
            call_site=self._call_site,
            latency_ms=latency_ms,
            ok=True,
            usage=_usage_from_result(result),
            fallback_from=self._tier,
        )
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._runnable, name)


class TelemetryLLM:
    """Chat model sarmalayicisi: invoke + with_structured_output telemetry'li."""

    def __init__(
        self,
        llm: Any,
        *,
        tier: Tier,
        model: str,
        call_site: str,
        fallback_llm: Any | None = None,
        fallback_model: str | None = None,
    ):
        self._llm = llm
        self.tier = tier
        self.model = model
        self.call_site = call_site
        self._fallback_llm = fallback_llm
        self._fallback_model = fallback_model

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return _TelemetryRunnable(
            self._llm,
            tier=self.tier,
            model=self.model,
            call_site=self.call_site,
            fallback_runnable=self._fallback_llm,
            fallback_model=self._fallback_model,
        ).invoke(*args, **kwargs)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> _TelemetryRunnable:
        primary = self._llm.with_structured_output(schema, **kwargs)
        fallback = None
        if self._fallback_llm is not None:
            fallback = self._fallback_llm.with_structured_output(schema, **kwargs)
        return _TelemetryRunnable(
            primary,
            tier=self.tier,
            model=self.model,
            call_site=self.call_site,
            fallback_runnable=fallback,
            fallback_model=self._fallback_model,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._llm, name)


def _build_raw_llm(model: str, temperature: float) -> Any:
    timeout = LLM_REQUEST_TIMEOUT_SECONDS if LLM_REQUEST_TIMEOUT_SECONDS > 0 else None

    if LLM_PROVIDER == "openrouter":
        from langchain_openai import ChatOpenAI

        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": OPENROUTER_API_KEY,
            "base_url": "https://openrouter.ai/api/v1",
            "temperature": temperature,
        }
        if timeout is not None:
            kwargs["timeout"] = timeout
        return ChatOpenAI(**kwargs)

    from langchain_google_genai import ChatGoogleGenerativeAI

    kwargs = {
        "model": model,
        "google_api_key": GEMINI_API_KEY,
        "temperature": temperature,
    }
    # langchain-google-genai surumune gore timeout destegi degisebilir;
    # varsa ilet, yoksa sessizce atla.
    if timeout is not None:
        kwargs["timeout"] = timeout
    try:
        return ChatGoogleGenerativeAI(**kwargs)
    except TypeError:
        kwargs.pop("timeout", None)
        return ChatGoogleGenerativeAI(**kwargs)


def get_llm(
    temperature: float = 0.2,
    *,
    tier: Tier = "worker",
    call_site: str = "",
):
    """Tier'li LLM dondurur.

    Varsayilan tier=worker — eski `get_llm()` cagrilari davranisini korur
    (ayni provider varsayilan modeli).
    """
    model = model_for_tier(tier)
    primary = _build_raw_llm(model, temperature)

    fallback_llm = None
    fallback_model = None
    if tier == "brain" and LLM_BRAIN_FALLBACK_TO_WORKER:
        fallback_model = model_for_tier("worker")
        if fallback_model != model:
            fallback_llm = _build_raw_llm(fallback_model, temperature)
        else:
            # Ayni model — fallback anlamsiz; yine de timeout sonrasi
            # tek retry istemiyoruz, sadece farkli modelde fallback var.
            fallback_llm = None
            fallback_model = None

    return TelemetryLLM(
        primary,
        tier=tier,
        model=model,
        call_site=call_site,
        fallback_llm=fallback_llm,
        fallback_model=fallback_model,
    )


def extract_text(message) -> str:
    """Gemini bazen content'i duz string yerine [{'type':'text',...}] blok
    listesi olarak dondurur (ozellikle dusunme/imza verisiyle). Ham .content
    kullanan her yer bu fonksiyondan gecmeli."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)
