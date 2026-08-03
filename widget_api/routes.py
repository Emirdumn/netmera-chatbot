"""Widget uc noktalari.

Her fonksiyon ince bir sarmalayicidir: HTTP'yi cozer, `app_services`'i
cagirir, sonucu widget'in bekledigi bicime cevirir. Burada IS MANTIGI YOK.
"""
import re
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from app_services import chat_service
from cache.qa_cache import incr_with_ttl
from config.settings import WIDGET_RATE_LIMIT_PER_MIN
from tools.article_lookup import assemble_article, public_doc_url, source_preview
from tools.rag_search_tool import rag_search
from widget_api import session as token_service
from widget_api.schemas import (
    ArticleOut,
    ContactIn,
    ConversationOut,
    MessageOut,
    SendMessageIn,
    SessionResponse,
    SourceOut,
)

router = APIRouter()

_AUTHOR_BY_ROLE = {"user": "user", "assistant": "bot", "human_agent": "staff"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# --------------------------------------------------------------------------
# Yardimcilar
# --------------------------------------------------------------------------

def _title_from_url(url: str) -> str:
    """Dokuman URL'inden okunabilir bir baslik uretir."""
    path = urlparse(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1] if path else ""
    slug = re.sub(r"\.(md|html?|txt)$", "", slug)
    slug = slug.replace("-", " ").replace("_", " ").strip()
    return slug.title() if slug else url


def _to_message_out(row: dict) -> MessageOut:
    """SQLite mesaj satirini widget bicimine cevirir.

    KASITLI OLARAK DISARIDA BIRAKILANLAR: tool_calls, orchestrator ve
    flow_status. Bunlar sistemin ic isleyisi — Streamlit panelinde
    seffaflik icin gosteriliyor ama dis widget'ta sizmamali.
    """
    sources: list[SourceOut] = []
    for url in row.get("sources") or []:
        preview = source_preview(url)
        sources.append(
            SourceOut(
                title=preview["title"],
                url=preview["url"],
                excerpt=preview.get("excerpt") or "",
            )
        )
    return MessageOut(
        id=str(row["id"]),
        author=_AUTHOR_BY_ROLE.get(row["role"], "bot"),
        author_name=row.get("agent_name") or None,
        text=row["content"],
        sent_at=row["created_at"],
        sources=sources,
    )


def _to_conversation_out(state) -> ConversationOut:
    return ConversationOut(
        session_id=state.session_id,
        messages=[_to_message_out(m) for m in state.messages],
        status=state.status,
        is_waiting=state.is_waiting,
        needs_contact_form=state.needs_contact_form,
    )


def require_session(authorization: str = Header(default="")) -> int:
    """Bearer token'i dogrular, session_id doner."""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    session_id = token_service.verify(token)
    if session_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return session_id


def _client_ip(request: Request) -> str:
    """Gercek istemci IP'si.

    Caddy/nginx arkasinda `request.client.host` proxy IP'sidir —
    onu kullansaydik TUM kullanicilar tek bir kovaya duser, rate limit
    anlamsizlasirdi. X-Forwarded-For'un SON elemani guvenilir peer'dir.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> None:
    """IP basina dakikalik yazma siniri.

    Yalnizca LLM/CPU harcatan uc noktalarda kullanilir; okuma (polling)
    ucunda kullanilmaz, yoksa normal kullanim bile bloklanirdi.
    """
    count = incr_with_ttl(f"widget:rl:{_client_ip(request)}", 60)
    if count is not None and count > WIDGET_RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Too many requests")


# --------------------------------------------------------------------------
# Uc noktalar
# --------------------------------------------------------------------------

@router.post("/session", response_model=SessionResponse)
def create_session() -> SessionResponse:
    session_id = chat_service.create_session("tr")
    return SessionResponse(session_id=session_id, token=token_service.issue(session_id))


@router.get("/conversation", response_model=ConversationOut)
def get_conversation(session_id: int = Depends(require_session)) -> ConversationOut:
    """Widget bunu polling ile cagirir (subscribe() bunun uzerine kurulu)."""
    return _to_conversation_out(chat_service.load_conversation(session_id))


@router.post("/messages", response_model=ConversationOut)
def send_message(
    payload: SendMessageIn,
    session_id: int = Depends(require_session),
    _: None = Depends(enforce_rate_limit),
) -> ConversationOut:
    chat_service.send_message(session_id, payload.text)
    return _to_conversation_out(chat_service.load_conversation(session_id))


@router.post("/contact", response_model=ConversationOut)
def submit_contact(
    payload: ContactIn, session_id: int = Depends(require_session)
) -> ConversationOut:
    if not _EMAIL_RE.match(payload.email.strip()):
        raise HTTPException(status_code=422, detail="Invalid email")
    chat_service.submit_contact(session_id, payload.name, payload.email)
    return _to_conversation_out(chat_service.load_conversation(session_id))


@router.post("/resume-bot", response_model=ConversationOut)
def resume_bot(session_id: int = Depends(require_session)) -> ConversationOut:
    chat_service.resume_bot(session_id)
    return _to_conversation_out(chat_service.load_conversation(session_id))


# Yardim sekmesi bosken gosterilen populer konular.
# Her satir: (arama sorgusu, kaynak filtresi). Sonuclar URL bazinda
# tekillestirilir; LLM cagrisi YOKTUR.
_POPULAR_TOPICS = (
    ("What is Netmera omnichannel platform", "website"),
    ("How to create a push notification campaign", "user_guide"),
    ("iOS SDK integration getting started", "dev_guide"),
    ("How to create a segment with rules", "user_guide"),
    ("Android push notification setup", "dev_guide"),
)


def _assembled_to_out(article) -> ArticleOut:
    return ArticleOut(
        id=article.id,
        title=article.title,
        excerpt=article.excerpt,
        url=article.url,
        body=article.body,
        source=article.source,
    )


def _chunk_to_article(index: int, chunk: dict) -> ArticleOut:
    """Liste satiri — mumkunse URL'deki tam makaleyi birlestirir."""
    url = chunk.get("url") or ""
    assembled = assemble_article(url) if url else None
    if assembled:
        # Liste kimligi stabil kalsin diye index'i id olarak tut;
        # url alani tam sayfayi acmak icin kullanilir.
        return ArticleOut(
            id=str(index),
            title=assembled.title,
            excerpt=assembled.excerpt,
            url=assembled.url,
            body=assembled.body,
            source=assembled.source,
        )
    return ArticleOut(
        id=str(index),
        title=chunk.get("heading_path") or _title_from_url(url),
        excerpt=(chunk.get("text") or "")[:180].strip(),
        url=public_doc_url(url),
        body=[chunk.get("text") or ""],
        source=chunk.get("source") or "",
    )


def _popular_articles() -> list[ArticleOut]:
    """Bos aramada gosterilecek populer basliklar (RAG, LLM yok)."""
    seen_urls: set[str] = set()
    articles: list[ArticleOut] = []
    for query, source in _POPULAR_TOPICS:
        result = rag_search.invoke({"query": query, "source": source, "top_k": 1})
        if not result.ok or not result.data:
            continue
        chunk = result.data[0]
        url = public_doc_url(chunk.get("url") or "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        articles.append(_chunk_to_article(len(articles), chunk))
        if len(articles) >= 5:
            break
    return articles


@router.get("/articles", response_model=list[ArticleOut])
def search_articles(
    q: str = "",
    _sid: int = Depends(require_session),
) -> list[ArticleOut]:
    """Yardim sekmesi aramasi — mevcut hibrit RAG aramasini kullanir.

    Bot cevabi URETMEZ (LLM cagrisi yok), yalnizca dokuman parcalari doner.
    `q` bos ise populer Netmera basliklari doner.
    Rate limit YOK — bu uc LLM harcamaz; yazma ucundan ayri tutulur.
    """
    query = q.strip()
    if not query:
        return _popular_articles()
    result = rag_search.invoke({"query": query, "source": "all", "top_k": 5})
    if not result.ok:
        return []
    return [_chunk_to_article(index, chunk) for index, chunk in enumerate(result.data)]


@router.get("/articles/by-url", response_model=ArticleOut)
def get_article_by_url(
    url: str = Query(..., min_length=8),
    _sid: int = Depends(require_session),
) -> ArticleOut:
    """Kaynak URL'sinden tam makale — chat 'Kaynaklar' ve Yardim devam oku.

    Chroma'daki ayni URL chunk'larini birlestirir. LLM yok.
    """
    article = assemble_article(url)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return _assembled_to_out(article)
