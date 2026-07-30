"""Tüm uzman agent'ların ortak davranışı.

FAZ 12: answer() artık tek seferlik RAG değil, kısa bir ReAct döngüsü —
query_builder_tool ile konuşma+profilden bağımsız bir arama sorgusu üretilir;
sonuç yetersizse (confidence < CONFIDENCE_THRESHOLD) sorgu yeniden yazılıp
tekrar denenir (en fazla MAX_TOOL_ITERATIONS tur). Böylece agent ilk aramada
zayıf sonuç aldığında hemen pes etmek yerine farklı bir sorguyla tekrar arar,
ve "peki ya android'de?" gibi bağlama bağlı takip soruları da doğru bir
bağımsız sorguya çevrilmiş olur."""
import json

from pydantic import BaseModel

from cache.qa_cache import cache_get, cache_set
from config.settings import CONFIDENCE_THRESHOLD, MAX_TOOL_ITERATIONS, QA_CACHE_TTL_SECONDS, TOP_K
from llm.client import get_llm
from tools.rag_search_tool import rag_search


class _LLMAnswer(BaseModel):
    """LLM'e gonderilen dar sema — reasoning_trace gibi kod-yonetimli alanlar
    kasitli olarak disarida birakilir (OpenAI'nin katı structured-output
    semasi tipsiz/serbest alanlari reddediyor)."""
    answer: str
    can_answer: bool
    needs_human: bool = False


class AgentResponse(BaseModel):
    answer: str
    can_answer: bool
    confidence: float
    sources: list[str] = []
    needs_human: bool = False
    reasoning_trace: list = []


class BaseAgent:
    name = "base_agent"
    department = "general"
    system_prompt = ""
    search_source = "all"

    def __init__(self):
        from tools.registry import get_tools_for
        self.llm = get_llm(temperature=0.2)
        self.tools = get_tools_for(self.department)

    def _extract_question(self, state):
        message = state["messages"][-1]
        if isinstance(message, dict):
            return message.get("content", "")
        return getattr(message, "content", str(message))

    def _find_tool(self, name):
        for t in self.tools:
            if getattr(t, "name", None) == name:
                return t
        return None

    def _format_history(self, state, limit=6):
        lines = []
        for m in state.get("messages", [])[-limit:]:
            if isinstance(m, dict):
                role, content = m.get("role", "?"), m.get("content", "")
            else:
                role = getattr(m, "type", None) or m.__class__.__name__
                content = getattr(m, "content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _profile_context(self, state):
        profile = state.get("customer_profile") or {}
        case_notes = state.get("case_notes") or {}
        parts = []
        if profile:
            parts.append(f"Musteri profili: {json.dumps(profile, ensure_ascii=False)}")
        if case_notes:
            parts.append(f"Vaka notlari: {json.dumps(case_notes, ensure_ascii=False)}")
        return "\n".join(parts)

    def _build_query(self, state, previous_query=""):
        query_builder = self._find_tool("query_builder_tool")
        fallback = self._extract_question(state)
        if not query_builder:
            return fallback
        result = query_builder.invoke({
            "conversation": self._format_history(state),
            "profile_context": self._profile_context(state),
            "previous_query": previous_query,
        })
        if result.ok and result.data.get("query"):
            return result.data["query"]
        return fallback

    def _search_context(self, query):
        result = rag_search.invoke({
            "query": query, "source": self.search_source, "top_k": TOP_K,
        })
        if not result.ok:
            return "", [], 0.0
        context = "\n\n---\n\n".join(
            f"[{c['heading_path'] or c['source']}]\n{c['text']}" for c in result.data
        )
        best_similarity = result.data[0]["similarity"]
        return context, result.sources, best_similarity

    def _answer_cache_key(self, query, language):
        normalized = " ".join(query.strip().lower().split())
        return f"answer:{self.department}:{self.search_source}:{language}:{normalized}"

    def answer(self, state):
        trace = []
        language = state.get("language", "tr")
        query = self._build_query(state, previous_query="")

        cache_key = self._answer_cache_key(query, language)
        cached = cache_get(cache_key)
        if cached:
            return AgentResponse.model_validate_json(cached)

        context, sources, best_similarity = "", [], 0.0

        for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
            if iteration > 1:
                query = self._build_query(state, previous_query=query)
            context, sources, best_similarity = self._search_context(query)
            trace.append({
                "iteration": iteration,
                "query": query,
                "similarity": round(best_similarity, 4),
            })
            if best_similarity >= CONFIDENCE_THRESHOLD:
                break

        if best_similarity < CONFIDENCE_THRESHOLD:
            return AgentResponse(
                answer="", can_answer=False, confidence=best_similarity,
                sources=[], needs_human=True, reasoning_trace=trace,
            )

        prompt = (
            f"{self.system_prompt}\n\n{self._profile_context(state)}\n\n"
            f"Baglam:\n{context}\n\nSoru: {query}"
        )
        structured_llm = self.llm.with_structured_output(_LLMAnswer)
        llm_answer = structured_llm.invoke(prompt)
        response = AgentResponse(
            answer=llm_answer.answer,
            can_answer=llm_answer.can_answer,
            confidence=best_similarity,
            sources=sources[:3],
            needs_human=llm_answer.needs_human,
            reasoning_trace=trace,
        )
        if response.can_answer and not response.needs_human:
            cache_set(cache_key, response.model_dump_json(), QA_CACHE_TTL_SECONDS)
        return response

    def run(self, state):
        raise NotImplementedError
