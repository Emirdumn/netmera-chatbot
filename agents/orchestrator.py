"""Bağlam farkındalığı olan yönlendirme — router_agent'ın yerini alır
(bkz. v2_legacy/router_agent.py — karşılaştırma için korunuyor).

Girdisi router'dan farklı olarak sadece son mesaj değil: son N mesaj,
customer_profile, case_notes, active_agent (şu an kim konuşuyordu) ve
pending_question (bot en son ne sormuştu). Yapışkanlık kuralı — müşteri
botun bekledigi soruyu cevapliyorsa aynı agent'ta kalınması — kod
seviyesinde zorunlu kılınır, LLM'e bırakılmaz.
"""
import json
from typing import Literal

from pydantic import BaseModel

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
- reasoning: kisa (tek cumle) neden bu karari verdigini acikla — arayuzde
  gosterilecek, ozet ve net yaz.

ONCELIK SIRASI (yukaridan asagiya kontrol et, ilk uyan kurali uygula):
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


class OrchestratorDecision(BaseModel):
    is_answer_to_pending_question: bool
    topic_changed: bool
    action: Literal["continue", "switch", "escalate", "clarify"]
    target_agent: Literal["sales", "support", "technical", "general"]
    language: Literal["tr", "en"]
    urgency: Literal["low", "normal", "high"]
    reasoning: str


DEPARTMENT_FOR_AGENT = {
    "sales": "sales",
    "support": "customer_success",
    "technical": "engineering",
    # config/departments.py'de ayri bir "general" departmani yok (sadece
    # sales/customer_success/engineering) — genel sorular devredilince
    # dogal karsilik olan musteri basari ekibine gider.
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


class Orchestrator:
    name = "orchestrator"

    def __init__(self):
        self.structured_llm = get_llm(temperature=0).with_structured_output(OrchestratorDecision)

    def decide(self, state) -> OrchestratorDecision:
        history = _format_history(state.get("messages", []))
        profile = state.get("customer_profile", {}) or {}
        case_notes = state.get("case_notes", {}) or {}
        active_agent = state.get("active_agent") or ""
        pending_question = state.get("pending_question") or ""

        prompt = f"""{SYSTEM_PROMPT}

Son konusma:
{history}

Musteri profili: {json.dumps(profile, ensure_ascii=False)}
Vaka notlari: {json.dumps(case_notes, ensure_ascii=False)}
Su an aktif agent: {active_agent or "yok"}
Botun bekledigi cevap: {pending_question or "yok"}"""

        decision = self.structured_llm.invoke(prompt)

        # Yapışkanlık kuralı — LLM'e bırakılmaz, kod seviyesinde zorunlu kılınır.
        # ÖNEMLİ: "evet, bir temsilciyle görüşmek istiyorum" gibi bir cevap HEM
        # botun sorusuna cevaptır HEM açık bir devir talebidir — escalate kararı
        # bu durumda ASLA continue'ya çevrilmemeli (once bu yuzden musteri
        # "baglanmak istiyorum" dedigi halde baglanamiyordu).
        if decision.is_answer_to_pending_question and active_agent and decision.action != "escalate":
            decision.action = "continue"
            decision.target_agent = active_agent

        return decision

    def run(self, state):
        decision = self.decide(state)
        return {
            "intent": decision.target_agent,
            "language": decision.language,
            "department": DEPARTMENT_FOR_AGENT.get(decision.target_agent, "customer_success"),
            "urgency": decision.urgency,
            "orchestrator_action": decision.action,
            "orchestrator_reasoning": decision.reasoning,
            "orchestrator_is_answer": decision.is_answer_to_pending_question,
            "orchestrator_topic_changed": decision.topic_changed,
            "active_agent": decision.target_agent,
        }
