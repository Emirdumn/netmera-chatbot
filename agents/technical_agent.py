"""SDK, API, entegrasyon, hata ayıklama soruları. Kaynak: dev_guide.

FAZ 11: müşteri bir hata/sorun tarif ettiyse (case_notes.error_message veya
problem_summary doluysa) technical_case_flow devreye girer — platform/SDK
sürümü gibi eksik bağlam netlik icin en fazla 2 soruyla tamamlanana kadar
istenir. Genel "nasıl yapılır" sorularında (case yok) davranış degismez.

FAZ 12: slotlar tamamlaninca sorgu zenginlestirme artik answer()'in kendi
ReAct dongusundeki query_builder_tool'a birakildi (profil+vaka notlarini
zaten goruyor), burada elle string birlestirmeye gerek yok."""
from agents.base import BaseAgent
from flows.technical_case import technical_case_flow

SYSTEM_PROMPT = """Sen Netmera SDK ve API konusunda uzman bir teknik destek
asistanisin. SADECE sana verilen baglam icindeki bilgilere dayanarak cevap ver.
Baglamdaki kod bloklarini bozmadan, oldugu gibi cevaba dahil et. Cevabi sorunun
diliyle ayni dilde yaz. Baglamda cevap yoksa bunu durustce soyle, bilgi uydurma."""


class TechnicalAgent(BaseAgent):
    name = "technical_agent"
    department = "engineering"
    search_source = "dev_guide"
    system_prompt = SYSTEM_PROMPT

    def _is_debugging_case(self, case_notes, state):
        # case_notes hic silinmiyor (bkz. merge_dict) — konu YENI degistiyse
        # (action=switch) eski bir konudan kalma problem_summary/error_message
        # bu turu vaka sanip yanlislikla slot sormasin.
        if state.get("orchestrator_action") == "switch":
            return False
        return bool(case_notes.get("error_message") or case_notes.get("problem_summary"))

    def run(self, state):
        profile = state.get("customer_profile") or {}
        case_notes = state.get("case_notes") or {}
        language = state.get("language", "tr")

        if self._is_debugging_case(case_notes, state):
            missing = technical_case_flow.missing_slots(profile, case_notes)
            if missing:
                total = len(technical_case_flow.slots)
                ask_now = missing[:2]
                answer = " ".join(slot.question(language) for slot in ask_now)
                return {
                    "answer": answer,
                    "can_answer": True,
                    "confidence": 1.0,
                    "sources": [],
                    "needs_human": False,
                    "agent_name": self.name,
                    "flow_status": {"flow": "technical_case", "total": total, "filled": total - len(missing)},
                }

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
