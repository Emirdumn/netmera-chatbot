"""Bağlam farkındalığı olan yönlendirme — router_agent'ın yerini alır.

CONTROL once karar verir. Sadece dusuk guven / celiskili sinyal / invalid
cikti durumlarinda BRAIN ikinci bakisi yapar. BRAIN hata verirse
llm/client worker fallback'i devreye girer.
"""
import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from agents.domain_guard import _looks_like_sales_flow
from llm.client import get_llm

SYSTEM_PROMPT = """Sen bir musteri destek konusmasini yoneten orkestratorsun.
Musterinin son mesajini, konusma gecmisini ve biriken musteri profilini
degerlendirerek asagidaki karari ver:

- is_answer_to_pending_question: Musteri, botun bir onceki turda sordugu
  soruyu mu cevapliyor? (ör. bot isim/sirket/e-posta sorduysa ve musteri
  bunlari verdiyse TRUE). Musteri sadece istenen bilgileri siraladiysa
  (isim, sirket, hata detayi vb.) ve konuyu degistirmediyse bu HER ZAMAN
  TRUE olmalidir — boyle bir mesaj asla yeni bir genel bilgi sorusu degildir.
- topic_changed: Musteri tamamen farkli, ilgisiz bir konuya mi gecti?
- action:
    continue  → ayni agent'ta devam (varsayilan, konu degismediyse bunu sec)
    switch    → farkli bir agent'a gec (konu gercekten degistiyse)
    escalate  → musteri ACIKCA bir insanla/yetkiliyle/temsilciyle gorusmek
                istedigini soyluyor
    clarify   → musteri kafasi karisik/anlasilmaz bir tepki verdi — devir
                ACMA, botun sordugu soruyu daha basit ifade ederek tekrar sor
- target_agent: sales | support | technical | general
- language: tr | en
- urgency: low | normal | high
- confidence: 0.0-1.0 arasi, bu karara ne kadar eminsen
- needs_brain_review: Karar belirsiz/celiskiliyse TRUE (pahali modele sorulacak)
- reasoning: kisa (tek cumle) neden bu karari verdigini acikla — arayuzde
  gosterilecek, ozet ve net yaz.

ONCELIK SIRASI (yukaridan asagiye kontrol et, ilk uyan kurali uygula):
1. Musterinin mesaji "anlamadim", "ne demek istedin", "ne istedin benden",
   "bunu neden soruyorsun", "kastettigini anlamadim" gibi AÇIKÇA kafasi
   karistigini belirten bir ifadeyse → action=clarify. Bu kural
   is_answer_to_pending_question veya topic_changed degerinden BAGIMSIZ
   olarak HER ZAMAN once kontrol edilir ve escalate'ten ONCELIKLIDIR.
2. Musteri acikca insanla gorusmek istiyorsa → action=escalate.
3. Musteri botun sordugu soruyu cevapliyorsa (isim/sirket/e-posta/hata
   detayi gibi istenen bilgileri veriyorsa) → action=continue,
   is_answer_to_pending_question=true.
4. Konu gercekten degistiyse → action=switch.
5. Digerlerinde → action=continue.
"""

_TECH_SIGNAL_RE = re.compile(
    r"\b(ios|android|flutter|react\s*native|sdk|api|push\s*token|"
    r"fcm|apns|gradle|cocoapods|xcode|webhook|rest\s*api|"
    r"entegrasyon|integration|exception|stack\s*trace)\b",
    re.IGNORECASE,
)

BRAIN_CONFIDENCE_THRESHOLD = 0.55


class OrchestratorDecision(BaseModel):
    is_answer_to_pending_question: bool
    topic_changed: bool
    action: Literal["continue", "switch", "escalate", "clarify"]
    target_agent: Literal["sales", "support", "technical", "general"]
    language: Literal["tr", "en"]
    urgency: Literal["low", "normal", "high"]
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    needs_brain_review: bool = False
    reasoning: str


DEPARTMENT_FOR_AGENT = {
    "sales": "sales",
    "support": "customer_success",
    "technical": "engineering",
    "general": "customer_success",
}


def _format_history(messages, limit=6):
    lines = []
    for m in messages[-limit:]:
        if isinstance(m, dict):
            role, content = m.get("role", "?"), m.get("content", "")
        else:
            role = getattr(m, "type", None) or m.__class__.__name__
            content = getattr(m, "content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines) or "(henüz mesaj yok)"


def _last_user_text(state) -> str:
    messages = state.get("messages") or []
    if not messages:
        return ""
    message = messages[-1]
    if isinstance(message, dict):
        return message.get("content", "") or ""
    return getattr(message, "content", "") or ""


def needs_brain_review(decision: OrchestratorDecision, state, last_user: str) -> bool:
    if decision.needs_brain_review:
        return True
    if decision.confidence < BRAIN_CONFIDENCE_THRESHOLD:
        return True

    active_agent = state.get("active_agent") or ""
    pending_question = (state.get("pending_question") or "").strip()

    if decision.topic_changed and pending_question and decision.is_answer_to_pending_question:
        return True
    if decision.topic_changed and active_agent and decision.action == "continue":
        return True
    if decision.target_agent == "general":
        # Alakasiz "Bitcoin fiyatı" gibi sorularda BRAIN tetikleme;
        # gercek satis/urun fiyat sinyali _looks_like_sales_flow ile ayrilir.
        if _TECH_SIGNAL_RE.search(last_user) or _looks_like_sales_flow(last_user):
            return True
    return False


def _apply_sticky_rule(decision: OrchestratorDecision, state) -> OrchestratorDecision:
    active_agent = state.get("active_agent") or ""
    if decision.is_answer_to_pending_question and active_agent and decision.action != "escalate":
        decision.action = "continue"
        decision.target_agent = active_agent
    return decision


class Orchestrator:
    name = "orchestrator"

    def __init__(self):
        self._control = get_llm(
            temperature=0, tier="control", call_site="orchestrator.decide",
        ).with_structured_output(OrchestratorDecision)
        self._brain = get_llm(
            temperature=0, tier="brain", call_site="orchestrator.brain_review",
        ).with_structured_output(OrchestratorDecision)

    def _build_prompt(self, state) -> str:
        history = _format_history(state.get("messages", []))
        profile = state.get("customer_profile", {}) or {}
        case_notes = state.get("case_notes", {}) or {}
        active_agent = state.get("active_agent") or ""
        pending_question = state.get("pending_question") or ""
        return f"""{SYSTEM_PROMPT}

Son konusma:
{history}

Musteri profili: {json.dumps(profile, ensure_ascii=False)}
Vaka notlari: {json.dumps(case_notes, ensure_ascii=False)}
Su an aktif agent: {active_agent or "yok"}
Botun bekledigi cevap: {pending_question or "yok"}"""

    def decide(self, state) -> tuple[OrchestratorDecision, bool]:
        prompt = self._build_prompt(state)
        last_user = _last_user_text(state)
        control_decision = None
        brain_used = False

        try:
            control_decision = self._control.invoke(prompt)
        except Exception:
            decision = self._brain.invoke(prompt)
            brain_used = True
            return _apply_sticky_rule(decision, state), brain_used

        if needs_brain_review(control_decision, state, last_user):
            try:
                brain_prompt = (
                    prompt
                    + "\n\nCONTROL modelinin onceki (belirsiz) karari:\n"
                    + f"{control_decision.model_dump_json()}\n"
                    + "Bu karari gozden gecir; celiskileri coz ve nihai karari ver."
                )
                decision = self._brain.invoke(brain_prompt)
                brain_used = True
            except Exception:
                decision = control_decision
        else:
            decision = control_decision

        return _apply_sticky_rule(decision, state), brain_used

    def run(self, state):
        decision, brain_used = self.decide(state)
        reasoning = decision.reasoning
        if brain_used:
            reasoning = f"[brain] {reasoning}"
        return {
            "intent": decision.target_agent,
            "language": decision.language,
            "department": DEPARTMENT_FOR_AGENT.get(decision.target_agent, "customer_success"),
            "urgency": decision.urgency,
            "orchestrator_action": decision.action,
            "orchestrator_reasoning": reasoning,
            "orchestrator_is_answer": decision.is_answer_to_pending_question,
            "orchestrator_topic_changed": decision.topic_changed,
            "active_agent": decision.target_agent,
            "orchestrator_brain_reviewed": brain_used,
            "confidence": decision.confidence,
        }
