"""Dokuman URL'sinden Chroma chunk'larini birlestirip widget makalesi uretir.

RAG cevaplari kaynagi (URL) gosterir; musteri ayni URL'nin tam metnini
widget icinde okuyabilsin diye chunk'lar siralanip birlestirilir.
LLM cagrisi YOKTUR.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from tools.rag_search_tool import _get_collection

_INDEX_BOILERPLATE_RE = re.compile(
    r"complete documentation index|llms\.txt",
    re.IGNORECASE,
)
_GITBOOK_TAG_RE = re.compile(r"\{%\s*[^%]+\s*%\}")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_MD_HEADING_RE = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_TRAILING_INDEX_RE = re.compile(r"-(\d+)$")

# Ayni URL icin tekrar Chroma okumasini engelle (poll / kaynak listesi).
_ARTICLE_MEMO: dict[str, AssembledArticle | None] = {}


@dataclass
class AssembledArticle:
    id: str
    title: str
    excerpt: str
    url: str
    body: list[str]
    source: str = ""


def public_doc_url(url: str) -> str:
    """GitBook .md scrape URL'sini insan sayfasina cevirir."""
    text = (url or "").strip()
    if text.endswith(".md"):
        return text[:-3]
    return text


def url_variants(url: str) -> list[str]:
    text = (url or "").strip()
    if not text:
        return []
    variants = [text]
    if text.endswith(".md"):
        variants.append(text[:-3])
    else:
        variants.append(text + ".md")
    # benzersiz, sirayi koru
    seen: set[str] = set()
    ordered: list[str] = []
    for item in variants:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _chunk_sort_key(chunk_id: str) -> int:
    match = _TRAILING_INDEX_RE.search(chunk_id or "")
    return int(match.group(1)) if match else 0


def _clean_text(text: str) -> str:
    cleaned = _GITBOOK_TAG_RE.sub("", text or "")
    cleaned = _MD_LINK_RE.sub(r"\1", cleaned)
    cleaned = _MD_BOLD_RE.sub(r"\1", cleaned)
    cleaned = _MD_HEADING_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _paragraphs(text: str) -> list[str]:
    cleaned = _clean_text(text)
    if not cleaned:
        return []
    parts = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    return parts or [cleaned]


def _is_boilerplate(text: str, heading_path: str) -> bool:
    if heading_path:
        return False
    return bool(_INDEX_BOILERPLATE_RE.search(text or ""))


def _title_from_url(url: str) -> str:
    from urllib.parse import urlparse

    path = urlparse(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1] if path else ""
    slug = re.sub(r"\.(md|html?|txt)$", "", slug)
    slug = slug.replace("-", " ").replace("_", " ").strip()
    return slug.title() if slug else (url or "Dokuman")


def fetch_chunks_by_url(url: str) -> list[dict]:
    """Ayni URL'ye ait tum chunk'lari index sirasiyla dondurur."""
    col = _get_collection()
    for candidate in url_variants(url):
        data = col.get(
            where={"url": candidate},
            include=["documents", "metadatas"],
        )
        if not data.get("ids"):
            continue
        rows = []
        for chunk_id, doc, meta in zip(
            data["ids"], data["documents"], data["metadatas"]
        ):
            rows.append(
                {
                    "id": chunk_id,
                    "text": doc or "",
                    "url": (meta or {}).get("url") or candidate,
                    "title": (meta or {}).get("title") or "",
                    "heading_path": (meta or {}).get("heading_path") or "",
                    "source": (meta or {}).get("source") or "",
                }
            )
        rows.sort(key=lambda row: _chunk_sort_key(row["id"]))
        return rows
    return []


def assemble_article(url: str) -> AssembledArticle | None:
    key = (url or "").strip()
    if not key:
        return None
    if key in _ARTICLE_MEMO:
        return _ARTICLE_MEMO[key]
    # varyant anahtarlarini da memo'la
    for variant in url_variants(key):
        if variant in _ARTICLE_MEMO:
            _ARTICLE_MEMO[key] = _ARTICLE_MEMO[variant]
            return _ARTICLE_MEMO[key]

    chunks = fetch_chunks_by_url(key)
    if not chunks:
        _ARTICLE_MEMO[key] = None
        return None

    usable = [
        c for c in chunks
        if not _is_boilerplate(c["text"], c.get("heading_path") or "")
    ]
    if not usable:
        usable = chunks

    title = ""
    for chunk in usable:
        heading = (chunk.get("heading_path") or "").strip()
        meta_title = (chunk.get("title") or "").strip()
        if heading and " > " not in heading:
            title = heading
            break
        if meta_title and not meta_title.endswith(".md"):
            title = meta_title
            break
        if heading:
            title = heading.split(" > ")[0].strip()
            break
    if not title:
        title = _title_from_url(chunks[0]["url"])

    body: list[str] = []
    seen: set[str] = set()
    for chunk in usable:
        for paragraph in _paragraphs(chunk["text"]):
            para_key = paragraph[:160].lower()
            if para_key in seen:
                continue
            seen.add(para_key)
            body.append(paragraph)

    if not body:
        _ARTICLE_MEMO[key] = None
        return None

    public_url = public_doc_url(chunks[0]["url"])
    excerpt = body[0][:180].strip()
    article = AssembledArticle(
        id=public_url,
        title=title,
        excerpt=excerpt,
        url=public_url,
        body=body[:40],  # panel boyutu icin makul ust sinir
        source=usable[0].get("source") or "",
    )
    _ARTICLE_MEMO[key] = article
    for variant in url_variants(chunks[0]["url"]):
        _ARTICLE_MEMO[variant] = article
    return article


def source_preview(url: str) -> dict:
    """Chat 'Kaynaklar' satiri icin baslik + kisa ozet."""
    article = assemble_article(url)
    if article:
        return {
            "title": article.title,
            "url": article.url,
            "excerpt": article.excerpt,
        }
    return {
        "title": _title_from_url(url),
        "url": public_doc_url(url),
        "excerpt": "",
    }
