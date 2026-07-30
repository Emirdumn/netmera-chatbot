"""Panel kullanımı, 'nasıl yapılır' soruları. Kaynak: user_guide.

FAZ 11: müşteri bir sorun tarif ettiyse (case_notes.problem_summary
doluysa) support_case_flow devreye girer — sorunun netlesmesi icin gerekirse
tamamlayici soru sorulur. Sade "nasil yapilir" sorularinda (problem yok)
davranis degismez."""
from agents.base import BaseAgent
from flows.support_case import support_case_flow

SYSTEM_PROMPT = """Sen Netmera panelinin kullanimi konusunda uzman bir destek
asistanisin. SADECE sana verilen baglam icindeki bilgilere dayanarak, adim adim
talimat seklinde cevap ver ve kullandigin kaynagin linkini belirt. Cevabi
sorunun diliyle ayni dilde yaz. Baglamda cevap yoksa bunu durustce soyle,
bilgi uydurma."""


class SupportAgent(BaseAgent):
    name = "support_agent"
    department = "customer_success"
    search_source = "user_guide"
    system_prompt = SYSTEM_PROMPT

    def _is_problem_case(self, case_notes, state):
        # case_notes hic silinmiyor (bkz. merge_dict) — konu YENI degistiyse
        # (action=switch) eski bir konudan kalma problem_summary bu turu
        # vaka sanip yanlislikla slot sormasin.
        if state.get("orchestrator_action") == "switch":
            return False
        return bool(case_notes.get("problem_summary"))

    def run(self, state):
        case_notes = state.get("case_notes") or {}
        language = state.get("language", "tr")

        if self._is_problem_case(case_notes, state):
            missing = support_case_flow.missing_slots({}, case_notes)
            if missing:
                total = len(support_case_flow.slots)
                ask_now = missing[:2]
                answer = " ".join(slot.question(language) for slot in ask_now)
                return {
                    "answer": answer,
                    "can_answer": True,
                    "confidence": 1.0,
                    "sources": [],
                    "needs_human": False,
                    "agent_name": self.name,
                    "flow_status": {"flow": "support_case", "total": total, "filled": total - len(missing)},
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
