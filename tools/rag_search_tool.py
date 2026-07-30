"""Hibrit arama (BM25 + vektör, RRF ile birleştirilir) + cross-encoder rerank
+ heading_boost. En önemli tool.

`similarity` alanı HER ZAMAN gerçek vektör kosinüs benzerligidir — bir chunk
sadece BM25/anahtar-kelime eslesmesiyle (vektor top-N'de olmadan) geldiyse
bile, son secilen parçalar için kosinüs benzerligi ayrica hesaplanir (asla
0.0 gibi yanlis-dusuk bir deger rapor edilmez). Boylece sistemin geri
kalaninda (CONFIDENCE_THRESHOLD, escalation tetikleyicileri) kullanilan
esik degerinin anlami degismez; rerank sadece HANGI parçaların
donduruleceginin SIRASINI iyilestirir, benzerlik olceğini degistirmez."""
from typing import Literal

import chromadb
import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer

from cache.qa_cache import cache_get, cache_set
from config.settings import CHROMA_COLLECTION, CHROMA_DIR, EMBED_MODEL, QA_CACHE_TTL_SECONDS, TOP_K
from tools.base import ToolResult, netmera_tool

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CANDIDATE_POOL = 20  # hibrit arama + rerank icin aday havuzu buyuklugu
RRF_K = 60
HEADING_BOOST = 0.03  # sorgu kelimesi heading_path'te gecerse RRF skoruna eklenir

_model = None
_collection = None
_cross_encoder = None
_bm25_index = None
_bm25_corpus = None  # [(id, doc, meta), ...]


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_collection(CHROMA_COLLECTION)
    return _collection


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder(RERANK_MODEL)
    return _cross_encoder


def _get_bm25():
    global _bm25_index, _bm25_corpus
    if _bm25_index is None:
        from rank_bm25 import BM25Okapi

        col = _get_collection()
        data = col.get(include=["documents", "metadatas"])
        _bm25_corpus = list(zip(data["ids"], data["documents"], data["metadatas"]))
        tokenized = [doc.lower().split() for _, doc, _ in _bm25_corpus]
        _bm25_index = BM25Okapi(tokenized)
    return _bm25_index, _bm25_corpus


def _vector_search(query, source, top_n):
    model = _get_model()
    col = _get_collection()
    where = None if source == "all" else {"source": source}
    embedding = model.encode([query]).tolist()
    result = col.query(
        query_embeddings=embedding, n_results=top_n, where=where,
        include=["documents", "metadatas", "distances"],
    )
    ranked = []
    for doc_id, doc, meta, dist in zip(
        result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        ranked.append((doc_id, doc, meta, round(1 - dist, 4)))
    return ranked


def _bm25_search(query, source, top_n):
    index, corpus = _get_bm25()
    tokenized_query = query.lower().split()
    scores = index.get_scores(tokenized_query)
    scored = []
    for (doc_id, doc, meta), score in zip(corpus, scores):
        if source != "all" and meta.get("source") != source:
            continue
        scored.append((doc_id, doc, meta, score))
    scored.sort(key=lambda x: x[3], reverse=True)
    return scored[:top_n]


def _heading_match_count(query, heading_path):
    if not heading_path:
        return 0
    query_words = {w for w in query.lower().split() if len(w) > 2}
    heading_words = set(heading_path.lower().replace(">", " ").split())
    return len(query_words & heading_words)


def _hybrid_candidates(query, source):
    vector_ranked = _vector_search(query, source, CANDIDATE_POOL)
    bm25_ranked = _bm25_search(query, source, CANDIDATE_POOL)

    cosine_by_id = {doc_id: sim for doc_id, _, _, sim in vector_ranked}
    payload_by_id = {}
    fused_scores = {}

    for rank, (doc_id, doc, meta, _) in enumerate(vector_ranked, start=1):
        fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + 1 / (RRF_K + rank)
        payload_by_id[doc_id] = (doc, meta)
    for rank, (doc_id, doc, meta, _) in enumerate(bm25_ranked, start=1):
        fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + 1 / (RRF_K + rank)
        payload_by_id[doc_id] = (doc, meta)

    for doc_id, (doc, meta) in payload_by_id.items():
        matches = _heading_match_count(query, meta.get("heading_path", ""))
        if matches:
            fused_scores[doc_id] += HEADING_BOOST * matches

    fused_ranked = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:CANDIDATE_POOL]
    candidates = []
    for doc_id, _ in fused_ranked:
        doc, meta = payload_by_id[doc_id]
        candidates.append((doc_id, doc, meta, cosine_by_id.get(doc_id, 0.0)))
    return candidates


def _true_cosine_similarities(query, doc_ids):
    """BM25 uzerinden gelip vektor havuzunda hic yer almamis olsa bile, son
    secilen parcalar icin GERCEK kosinus benzerligini hesaplar (stored
    embedding'leri chroma'dan cekip sorgu embedding'iyle karsilastirarak)."""
    model = _get_model()
    col = _get_collection()
    query_vec = np.array(model.encode([query])[0])
    query_norm = np.linalg.norm(query_vec)

    got = col.get(ids=doc_ids, include=["embeddings"])
    similarities = {}
    for doc_id, emb in zip(got["ids"], got["embeddings"]):
        emb_vec = np.array(emb)
        cos = float(np.dot(query_vec, emb_vec) / (query_norm * np.linalg.norm(emb_vec) + 1e-9))
        similarities[doc_id] = cos
    return similarities


def _rerank(query, candidates, top_k):
    if not candidates:
        return []
    ce = _get_cross_encoder()
    pairs = [[query, doc] for _, doc, _, _ in candidates]
    ce_scores = ce.predict(pairs)
    scored = list(zip(candidates, ce_scores))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored[:top_k]]


def _rag_cache_key(query, source, top_k):
    normalized = " ".join(query.strip().lower().split())
    return f"rag:{source}:{top_k}:{normalized}"


@netmera_tool
def rag_search(
    query: str,
    source: Literal["user_guide", "dev_guide", "website", "all"] = "all",
    top_k: int = TOP_K,
) -> ToolResult:
    """Netmera dokümantasyonunda hibrit (BM25 + vektör, RRF) arama yapar,
    cross-encoder ile en iyi top_k sonucu seçer. `source` ile kaynağı
    daraltır: user_guide (panel/kullanım), dev_guide (SDK/API), website
    (genel/pazarlama)."""
    cache_key = _rag_cache_key(query, source, top_k)
    cached = cache_get(cache_key)
    if cached:
        return ToolResult.model_validate_json(cached)

    candidates = _hybrid_candidates(query, source)
    if not candidates:
        return ToolResult(ok=False, data=[], summary="Sonuc bulunamadi", sources=[])

    reranked = _rerank(query, candidates, top_k)
    true_cosines = _true_cosine_similarities(query, [doc_id for doc_id, _, _, _ in reranked])

    chunks = [
        {
            "text": doc,
            "similarity": round(true_cosines.get(doc_id, cosine), 4),
            "heading_path": meta.get("heading_path", ""),
            "url": meta.get("url", ""),
            "source": meta.get("source", ""),
        }
        for doc_id, doc, meta, cosine in reranked
    ]

    result = ToolResult(
        ok=True,
        data=chunks,
        summary=f"en iyi benzerlik: {chunks[0]['similarity']}",
        sources=[c["url"] for c in chunks],
    )
    cache_set(cache_key, result.model_dump_json(), QA_CACHE_TTL_SECONDS)
    return result
