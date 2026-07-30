"""Tool altyapısı: @netmera_tool decorator + ToolResult sözleşmesi.

Her tool bu decorator ile işaretlenir. Decorator: (1) tool'u global registry'ye
kaydeder, (2) tip ipuçlarından LangChain tool şemasını otomatik üretir,
(3) her çağrıda terminale görünür log basar, (4) çağrıyı tool_calls log'una ekler
— graph/nodes.py bunu her agent adımından sonra state["tool_calls"]'a aktaracak.
"""
import functools
from typing import Any

from langchain_core.tools import tool as _lc_tool
from pydantic import BaseModel

from config.settings import LOG_TOOL_CALLS

TOOL_REGISTRY = {}
_tool_call_log = []


class ToolResult(BaseModel):
    ok: bool
    data: Any = None
    summary: str = ""
    sources: list[str] = []


def get_tool_calls():
    """Su ana kadar loglanan tool cagrilarinin kopyasini dondurur."""
    return list(_tool_call_log)


def clear_tool_calls():
    """Yeni bir istek/oturum basinda log'u sifirlar."""
    _tool_call_log.clear()


def _format_args(kwargs):
    return ", ".join(f"{k}={v!r}" for k, v in kwargs.items())


def netmera_tool(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        summary = getattr(result, "summary", "") if isinstance(result, ToolResult) else ""
        record = {"tool": func.__name__, "args": kwargs, "summary": summary}
        _tool_call_log.append(record)
        if LOG_TOOL_CALLS:
            print(f"🔧 TOOL → {func.__name__}({_format_args(kwargs)})"
                  + (f"  → {summary}" if summary else ""))
        return result

    lc_tool = _lc_tool(wrapper)
    TOOL_REGISTRY[func.__name__] = lc_tool
    return lc_tool
