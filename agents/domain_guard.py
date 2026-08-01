"""Fast RAG gate + domain guard.

Amaç:
1. Netmera dokumanlariyla guclu semantik eslesmede agir orkestrator zincirine
   girmeden kaynakli cevap uretmek.
2. Eslesme zayifsa LLM'e yalnizca "Netmera alani mi?" kararini verdirmek.
3. Tamamen alakasiz sorulari insana devretmeden kapsam disi diye yanitlamak.

Bu katman mevcut satis/devir/slot akislarini devralmaz; riskli durumlarda
graf eski yola devam eder.
"""
import json
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from cache.qa_cache import cache_get, cache_set
from config.settings import (
    FAST_RAG_DIRECT_THRESHOLD,
    FAST_RAG_ENABLED,
    FAST_RAG_REWRITE_THRESHOLD,
    QA_CACHE_TTL_SECONDS,
    TOP_K,
)
from llm.client import get_llm
from tools.rag_search_tool import semantic_probe

OFF_TOPIC_MESSAGE = (
    "Ben sadece Netmera ürünleri, kullanıcı/developer dokümantasyonu ve "
    "Netmera'nın web sitesindeki konular hakkında yardımcı olabiliyorum. "
    "Netmera ile ilgili bir soru sorarsanız hemen yardımcı olayım."
)

GREETING_MESSAGE = (
    "Merhaba! Netmera hakkında size yardımcı olabilirim — kullanıcı paneli, "
    "SDK/entegrasyon, kampanya/segment veya ürün özellikleri. Ne öğrenmek "
    "istersiniz?"
)

THANKS_MESSAGE = (
    "Rica ederim! Başka bir Netmera sorunuz olursa buradayım."
)

_HUMAN_REQUEST_RE = re.compile(
    r"\b(temsilci\w*|yetkili\w*|insan\w*|canli destek|canlı destek|"
    r"musteri temsilcisi|müşteri temsilcisi|uzman\w*|baglan\w*|bağlan\w*)\b",
    re.IGNORECASE,
)
# Guclu satis sinyali — her zaman sales/slot akisina birak.
_STRONG_SALES_RE = re.compile(
    r"\b(demo\w*|satin\s*al\w*|satın\s*al\w*|paket\w*|pricing|quote\w*|"
    r"teklif\w*|lisans\w*|price\s*list)\b",
    re.IGNORECASE,
)
# Zayif fiyat kelimeleri — yalnizca Netmera urun ipucu veya kisa
# "Fiyat nedir?" tarzı sorularda bypass. "Bitcoin fiyatı ne kadar?" gibi
# alakasiz fiyat sorularini domain_guard'a birakmak icin ayri tutulur.
_WEAK_PRICE_RE = re.compile(
    r"\b(fiyat\w*|ucret\w*|ücret\w*|ne kadar|kac para|kaç para|"
    r"price\w*|cost\w*)\b",
    re.IGNORECASE,
)
_NETMERA_PRODUCT_CUE_RE = re.compile(
    r"\b(netmera|push|sms|kampanya|segment|journey|sdk|panel|"
    r"in-?app|geofence|omnichannel|ab\s*test|iys|web\s*push)\b",
    re.IGNORECASE,
)
_PRICE_ONLY_RE = re.compile(
    r"^(fiyat\w*|ucret\w*|ücret\w*|pricing|price\w*|cost\w*)"
    r"(\s+(nedir|ne\s*kadar|kaç|kac|bilgisi\w*|hakkında|hakkinda))?"
    r"[\s!.?]*$",
    re.IGNORECASE,
)
# Geriye donuk alias — testler / dis kullanim icin birlesik desen.
_SALES_FLOW_RE = re.compile(
    r"\b(fiyat\w*|ucret\w*|ücret\w*|paket\w*|ne kadar|kac para|kaç para|"
    r"demo\w*|satin al\w*|satın al\w*|price\w*|pricing|cost\w*|quote\w*)\b",
    re.IGNORECASE,
)
_PROBLEM_CASE_RE = re.compile(
    r"\b(calismiyor|çalışmıyor|bozuk|hata\w*|error\w*|exception\w*|gitmiyor|"
    r"alamiyorum|alamıyorum|gelmiyor|takildi|takıldı|patliyor|patlıyor|"
    r"401|403|500)\b",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_GREETING_RE = re.compile(
    r"^(merhaba|selam|selamlar|hey|hi|hello|günaydın|gunaydin|"
    r"iyi\s*günler|iyi\s*gunler|iyi\s*akşamlar|iyi\s*aksamlar|"
    r"good\s*morning|good\s*evening|good\s*afternoon)"
    r"[\s!.?]*$",
    re.IGNORECASE,
)
_THANKS_RE = re.compile(
    r"^(teşekkürler|tesekkurler|teşekkür\s*ederim|tesekkur\s*ederim|"
    r"sağ\s*ol|sag\s*ol|sağol|sagol|thanks|thank\s*you|eyvallah|"
    r"ok|okay|tamam|anladım|anladim|süper|super|harika)"
    r"[\s!.?]*$",
    re.IGNORECASE,
)


class DomainDecision(BaseModel):
    is_netmera_related: bool
    source: Literal["user_guide", "dev_guide", "website", "all"] = "all"
    search_query: str = ""
    reason: str = ""


class DomainRelevance(BaseModel):
    """Sadece alakalilik — general_agent ve diger paylasimli kontrol icin."""
    is_netmera_related: bool
    reason: str = ""


class GroundedAnswer(BaseModel):
    answer: str
    can_answer: bool


# Proses-ici cache — Redis yokken bile ayni turda ikinci LLM'i engeller.
_DOMAIN_RELATED_MEMO: dict[str, bool] = {}


@dataclass
class FastRagResult:
    handled: bool
    answer: str
    confidence: float
    sources: list[str]
    agent_name: str
    mode: str
    trace: list[dict]


DOMAIN_PROMPT = """Musterinin son mesajinin Netmera alaniyla ilgili olup
olmadigina karar ver.

Netmera alani sayilanlar:
- Netmera urunu, sirketi, web sitesindeki pazarlama/urun sayfalari
- Netmera User Guide: panel kullanimi, kampanya, segment, journey, rapor,
  push, email, SMS, web personalization, permission/IYS gibi konular
- Netmera Developer Guide: SDK, API, iOS/Android/Flutter/React Native/Web,
  push token, event, entegrasyon, hata ayiklama
- Netmera glossary/web sitesi kapsamindaki pazarlama/engagement terimleri
  (churn, LTV, cohort, A/B testing, omnichannel vb.)

Alakasiz sayilanlar:
- hava durumu, spor, yemek, genel sohbet, siyaset, Netmera disi kodlama
  sorulari, baska urun/sirket destek talepleri

Ilgiliyse en uygun source'u sec ve dokumanda aramak icin kisa, bagimsiz,
tercihen Ingilizce bir search_query yaz. Son mesaj takip sorusuysa konusma
gecmisini sadece eksik baglami tamamlamak icin kullan.

Konusma:
{history}

Son mesaj: "{question}"
"""

ANSWER_PROMPT = """Sen Netmera dokumantasyonuna dayali bir destek asistanisin.
SADECE verilen baglamdaki bilgileri kullan. Baglam soruya cevap vermiyorsa
can_answer=false don. Bilgi uydurma.

Cevabi kullanicinin diliyle ayni dilde yaz. Turkce soruya Turkce cevap ver.
Kisa ama ise yarar cevap ver; gerekiyorsa maddeler kullan.

Baglam:
{context}

Soru: {question}
"""


def _last_user_text(state) -> str:
    message = state.get("messages", [])[-1]
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", str(message))


def _format_history(state, limit: int = 6) -> str:
    lines = []
    for message in state.get("messages", [])[-limit:]:
        if isinstance(message, dict):
            role, content = message.get("role", "?"), message.get("content", "")
        else:
            role = getattr(message, "type", None) or message.__class__.__name__
            content = getattr(message, "content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _social_reply(question: str) -> FastRagResult | None:
    """Selamlasma/tesekkur gibi kisa sosyal mesajlari LLM/RAG'e sokmadan yanitla.

    Aksi halde dusuk semantik eslesme + domain LLM 'alakasiz' diyebilir ve
    'Merhaba'ya kapsam-disi cevabi doner — profesyonel degil.
    """
    text = question.strip()
    if _GREETING_RE.match(text):
        return _make_result(
            answer=GREETING_MESSAGE,
            confidence=1.0,
            sources=[],
            mode="greeting",
            trace=[{"step": "social_short_circuit", "kind": "greeting"}],
            agent_name="fast_rag",
        )
    if _THANKS_RE.match(text):
        return _make_result(
            answer=THANKS_MESSAGE,
            confidence=1.0,
            sources=[],
            mode="thanks",
            trace=[{"step": "social_short_circuit", "kind": "thanks"}],
            agent_name="fast_rag",
        )
    return None


def _looks_like_sales_flow(question: str) -> bool:
    """Sales/slot akisina birakilacak mi?

    "Demo almak istiyorum" / "Netmera fiyatlandirma" / "Fiyat nedir?" → True
    "Bitcoin fiyatı ne kadar?" → False (domain_guard off-topic yapsin)
    """
    text = (question or "").strip()
    if not text:
        return False
    if _STRONG_SALES_RE.search(text):
        return True
    if not _WEAK_PRICE_RE.search(text):
        return False
    if _NETMERA_PRODUCT_CUE_RE.search(text):
        return True
    if _PRICE_ONLY_RE.match(text):
        return True
    return False


def _should_bypass(state, question: str) -> bool:
    if not FAST_RAG_ENABLED:
        return True
    if state.get("pending_question"):
        return True
    if _HUMAN_REQUEST_RE.search(question):
        return True
    if _looks_like_sales_flow(question):
        return True
    if _PROBLEM_CASE_RE.search(question):
        return True
    # Kisisel bilgi cevabi gibi gorunen mesajlari eski akis yonetsin.
    if _EMAIL_RE.search(question):
        return True
    return False


def _context_from_chunks(chunks: list[dict]) -> str:
    return "\n\n---\n\n".join(
        f"[{c.get('source') or 'all'} | {c.get('heading_path') or c.get('url') or 'kaynak'}]\n"
        f"{c.get('text', '')}"
        for c in chunks
    )


def _best_similarity(result) -> float:
    if not result.ok or not result.data:
        return 0.0
    return float(result.data[0].get("similarity") or 0.0)


def _result_cache_key(question: str) -> str:
    normalized = " ".join(question.strip().lower().split())
    return f"fast_rag_answer:v1:{normalized}"


def _normalize_question(question: str) -> str:
    return " ".join(question.strip().lower().split())


def _domain_related_cache_key(question: str) -> str:
    return f"domain_related:v1:{_normalize_question(question)}"


def _cache_allowed(question: str) -> bool:
    return len(question) <= 300 and not _EMAIL_RE.search(question)


def _store_domain_related(question: str, related: bool) -> None:
    key = _normalize_question(question)
    if not key:
        return
    _DOMAIN_RELATED_MEMO[key] = related
    if _cache_allowed(question):
        cache_set(_domain_related_cache_key(question), "1" if related else "0", QA_CACHE_TTL_SECONDS)


def is_netmera_related(question: str, history: str = "") -> bool:
    """Tek CONTROL domain classifier — general_agent dahil her yer burayi kullanir."""
    text = (question or "").strip()
    if not text:
        return False

    memo_key = _normalize_question(text)
    if memo_key in _DOMAIN_RELATED_MEMO:
        return _DOMAIN_RELATED_MEMO[memo_key]

    if _cache_allowed(text):
        cached = cache_get(_domain_related_cache_key(text))
        if cached is not None:
            related = cached == "1"
            _DOMAIN_RELATED_MEMO[memo_key] = related
            return related

    llm = get_llm(
        temperature=0, tier="control", call_site="domain_guard.is_netmera_related",
    ).with_structured_output(DomainRelevance)
    prompt = DOMAIN_PROMPT.format(history=history or "(yok)", question=text)
    decision = llm.invoke(
        prompt + "\n\nSadece is_netmera_related ve kisa reason doldur; "
        "source/search_query gerekmiyor."
    )
    _store_domain_related(text, decision.is_netmera_related)
    return decision.is_netmera_related


def _decide_domain(state, question: str) -> DomainDecision:
    llm = get_llm(
        temperature=0, tier="control", call_site="domain_guard.decide_domain",
    ).with_structured_output(DomainDecision)
    decision = llm.invoke(
        DOMAIN_PROMPT.format(history=_format_history(state), question=question)
    )
    _store_domain_related(question, decision.is_netmera_related)
    return decision


def _answer_from_context(question: str, chunks: list[dict]) -> GroundedAnswer:
    llm = get_llm(
        temperature=0.1, tier="worker", call_site="domain_guard.answer_from_context",
    ).with_structured_output(GroundedAnswer)
    return llm.invoke(ANSWER_PROMPT.format(context=_context_from_chunks(chunks), question=question))


def _dedupe_sources(sources: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for url in sources or []:
        if not url or url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered[:3]


def _make_result(
    *,
    answer: str,
    confidence: float,
    sources: list[str],
    mode: str,
    trace: list[dict],
    agent_name: str = "fast_rag",
) -> FastRagResult:
    return FastRagResult(
        handled=True,
        answer=answer,
        confidence=confidence,
        sources=_dedupe_sources(sources),
        agent_name=agent_name,
        mode=mode,
        trace=trace,
    )


def _answer_with_probe(question: str, probe, mode: str, trace: list[dict]) -> FastRagResult | None:
    chunks = probe.data if probe.ok else []
    if not chunks:
        return None
    answer = _answer_from_context(question, chunks)
    if not answer.can_answer:
        return None
    return _make_result(
        answer=answer.answer,
        confidence=_best_similarity(probe),
        sources=probe.sources,
        mode=mode,
        trace=trace,
    )


def try_fast_rag_answer(state) -> FastRagResult | None:
    question = _last_user_text(state).strip()
    if not question or _should_bypass(state, question):
        return None

    social = _social_reply(question)
    if social is not None:
        return social

    cache_key = _result_cache_key(question)
    if _cache_allowed(question):
        cached = cache_get(cache_key)
        if cached:
            payload = json.loads(cached)
            return FastRagResult(**payload)

    trace: list[dict] = []
    raw_probe = semantic_probe(question, source="all", top_k=TOP_K)
    raw_similarity = _best_similarity(raw_probe)
    trace.append({
        "step": "semantic_probe",
        "query": question,
        "source": "all",
        "similarity": round(raw_similarity, 4),
    })

    if raw_similarity >= FAST_RAG_DIRECT_THRESHOLD:
        result = _answer_with_probe(question, raw_probe, "semantic_direct", trace)
        if result:
            if _cache_allowed(question):
                cache_set(cache_key, json.dumps(result.__dict__, ensure_ascii=False), QA_CACHE_TTL_SECONDS)
            return result

    decision = _decide_domain(state, question)
    trace.append({
        "step": "domain_decision",
        "related": decision.is_netmera_related,
        "source": decision.source,
        "query": decision.search_query,
        "reason": decision.reason,
    })

    if not decision.is_netmera_related:
        result = _make_result(
            answer=OFF_TOPIC_MESSAGE,
            confidence=raw_similarity,
            sources=[],
            mode="off_topic",
            trace=trace,
            agent_name="domain_guard",
        )
        if _cache_allowed(question):
            cache_set(cache_key, json.dumps(result.__dict__, ensure_ascii=False), QA_CACHE_TTL_SECONDS)
        return result

    rewritten_query = decision.search_query.strip() or question
    source = decision.source or "all"
    rewritten_probe = semantic_probe(rewritten_query, source=source, top_k=TOP_K)
    rewritten_similarity = _best_similarity(rewritten_probe)
    trace.append({
        "step": "semantic_probe_rewritten",
        "query": rewritten_query,
        "source": source,
        "similarity": round(rewritten_similarity, 4),
    })

    if rewritten_similarity >= FAST_RAG_REWRITE_THRESHOLD:
        result = _answer_with_probe(question, rewritten_probe, "llm_rewrite", trace)
        if result:
            if _cache_allowed(question):
                cache_set(cache_key, json.dumps(result.__dict__, ensure_ascii=False), QA_CACHE_TTL_SECONDS)
            return result

    # Netmera ile ilgili ama gate guvenli cevap uretmedi: mevcut agent
    # zincirine birak. Orada query_builder/ReAct + devir mantigi devreye girer.
    return None
