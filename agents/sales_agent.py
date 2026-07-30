"""Fiyat, paket, demo, satın alma soruları. Kaynak: website.

Özel kural: Netmera fiyat listesini public yayınlamıyor -> agent fiyat
sorusunda uydurmaz, lead bilgisi toplayıp satışa yönlendirir.

FAZ 11: lead toplama artık slot-farkındalıklı (flows/sales_lead.py).
customer_profile'da zaten bilinen alan tekrar sorulmaz; eksik slotlardan
en fazla 2 tanesi birden sorulur. Tüm slotlar tamamlanınca lead_capture_tool
çağrılır — bu yüzden agent, doldurulmuş lead bilgisini bir RAG sorgusu
sanıp devir açmaz (bkz. PLAN_ORCHESTRATOR.md, kök neden #5).
"""
from agents.base import BaseAgent
from flows.sales_lead import sales_lead_flow
from storage import repository as repo

SYSTEM_PROMPT = """Sen Netmera satis asistanisin. SADECE sana verilen baglam
icindeki bilgilere dayanarak paket/ozellik/demo sorularini cevapla. Cevabi
sorunun diliyle ayni dilde yaz. Baglamda cevap yoksa bunu durustce soyle,
bilgi uydurma."""

PRICE_KEYWORDS = ["fiyat", "ücret", "ucret", "paket", "ne kadar", "kaç para",
                   "kac para", "price", "pricing", "cost", "quote"]

LEAD_COMPLETE_MESSAGE = (
    "Teşekkürler! Bilgilerinizi satış ekibimize ilettim, en kısa sürede "
    "sizinle iletişime geçecekler. Hemen bir temsilcimize bağlanmak ister "
    "misiniz?"
)


class SalesAgent(BaseAgent):
    name = "sales_agent"
    department = "sales"
    search_source = "website"
    system_prompt = SYSTEM_PROMPT

    def _lead_in_progress(self, profile):
        slot_names = [s.name for s in sales_lead_flow.slots]
        return any(profile.get(name) for name in slot_names)

    def _lead_flow_response(self, profile, case_notes, language, session_id):
        missing = sales_lead_flow.missing_slots(profile, case_notes)
        total = len(sales_lead_flow.slots)
        filled = total - len(missing)

        if not missing:
            lead_tool = self._find_tool("lead_capture_tool")
            if lead_tool:
                lead_tool.invoke({
                    "name": profile.get("person_name") or "",
                    "company": profile.get("company") or "",
                    "email": profile.get("email") or "",
                    "app_type": profile.get("app_name") or "",
                    "estimated_users": profile.get("user_scale") or "",
                })
            # Lead tamamlandi — gercekten satis ekibinin panelde gorecegi
            # bir kayit olustur. pause_session=False: musteri canli bir
            # insan yaniti beklemiyor, botla sohbete devam edebilir.
            if session_id:
                summary = (
                    f"Satis lead'i — {profile.get('person_name', '')} "
                    f"({profile.get('company', '')}), e-posta: {profile.get('email', '')}, "
                    f"uygulama: {profile.get('app_name', '')}, "
                    f"tahmini kullanici: {profile.get('user_scale', '')}"
                )
                repo.create_handoff(
                    session_id, "sales", "sales_lead", summary, "low", pause_session=False,
                )
            answer = LEAD_COMPLETE_MESSAGE
        else:
            ask_now = missing[:2]  # ayni anda en fazla 2 eksik slot sor
            answer = " ".join(slot.question(language) for slot in ask_now)

        return {
            "answer": answer,
            "can_answer": True,
            "confidence": 1.0,
            "sources": [],
            "needs_human": False,
            "agent_name": self.name,
            "flow_status": {"flow": "sales_lead", "total": total, "filled": filled},
        }

    def run(self, state):
        question = self._extract_question(state)
        is_price_question = any(k in question.lower() for k in PRICE_KEYWORDS)
        profile = state.get("customer_profile") or {}
        case_notes = state.get("case_notes") or {}
        language = state.get("language", "tr")

        if is_price_question or self._lead_in_progress(profile):
            return self._lead_flow_response(profile, case_notes, language, state.get("session_id"))

        response = self.answer(state)
        return {
            "answer": response.answer,
            "can_answer": response.can_answer,
            "confidence": response.confidence,
            "sources": response.sources,
            "needs_human": not response.can_answer,
            "agent_name": self.name,
            "reasoning_trace": response.reasoning_trace,
            "flow_status": {},
        }
