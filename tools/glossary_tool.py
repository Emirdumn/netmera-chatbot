"""Netmera terim sözlüğü — data/website/glossary_* sayfalarından terim tanımı arar.
Genel/pazarlama sorularında (churn rate, LTV, deep linking...) rag_search'ten
daha keskin, doğrudan tanım döndürür."""
import re
from functools import lru_cache

from config.settings import WEBSITE_DIR
from tools.base import ToolResult, netmera_tool

GLOSSARY_PREFIX = "netmera.com_glossary_"
MIN_LINE_CHARS = 60  # kisa nav/menu satirlarini elemek icin esik


def _term_from_filename(stem):
    slug = stem[len(GLOSSARY_PREFIX):]
    return slug.replace("-", " ").title()


def _extract_definition(body):
    lines = [ln.strip() for ln in body.splitlines()]
    meaningful = [ln for ln in lines if len(ln) >= MIN_LINE_CHARS]
    return " ".join(meaningful)[:800].strip()


@lru_cache(maxsize=1)
def _load_glossary():
    entries = []
    for f in sorted(WEBSITE_DIR.glob(f"{GLOSSARY_PREFIX}*.txt")):
        raw = f.read_text(encoding="utf-8")
        first_line, _, body = raw.partition("\n\n")
        url = first_line.replace("URL: ", "").strip()
        definition = _extract_definition(body)
        if definition:
            entries.append({
                "term": _term_from_filename(f.stem),
                "url": url,
                "definition": definition,
            })
    return entries


@netmera_tool
def glossary_search(query: str) -> ToolResult:
    """Netmera pazarlama/terim sözlüğünde arama yapar (churn rate, LTV, deep linking...)."""
    entries = _load_glossary()
    q = query.lower().strip()
    matches = [e for e in entries if q in e["term"].lower() or e["term"].lower() in q]
    if not matches:
        q_words = set(re.findall(r"[a-z]+", q))
        matches = [
            e for e in entries
            if q_words & set(re.findall(r"[a-z]+", e["term"].lower()))
        ]
    if not matches:
        return ToolResult(ok=False, data=[], summary="Terim bulunamadi", sources=[])
    return ToolResult(
        ok=True,
        data=matches[:3],
        summary=matches[0]["definition"][:200],
        sources=[m["url"] for m in matches[:3]],
    )
