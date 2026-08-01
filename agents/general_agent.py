"""'Netmera nedir', 'hangi sektorlere hizmet veriyor' gibi genel sorular.
Kaynak: website + glossary.
"""
from agents.base import BaseAgent
from agents.domain_guard import is_netmera_related
from tools.glossary_tool import glossary_search

SYSTEM_PROMPT = """Sen Netmera (omnichannel musteri etkilesim platformu) hakkinda
genel bilgi veren bir asistansin. SADECE sana verilen baglam icindeki bilgilere
dayanarak cevap ver. Cevabi sorunun diliyle ayni dilde yaz (Turkce soruya Turkce,
Ingilizce soruya Ingilizce). Baglamda cevap yoksa bunu durustce soyle, bilgi
uydurma."""

CANNOT_ANSWER_MESSAGE = (
    "Bu konuda elimde yeterli bilgi yok, yanlış bilgi vermek istemem. "
    "Sizi ilgili ekibimize bağlayabilirim, ister misiniz?"
)

OFF_TOPIC_MESSAGE = (
    "Ben sadece Netmera hakkındaki sorularda yardımcı olabiliyorum, bu "
    "konuda size destek olamam. Netmera ile ilgili başka bir sorunuz var mı?"
)


class GeneralAgent(BaseAgent):
    name = "general_agent"
    department = "general"
    search_source = "website"
    system_prompt = SYSTEM_PROMPT

    def _is_on_topic(self, question):
        return is_netmera_related(question)

    def run(self, state):
        question = self._extract_question(state)
        response = self.answer(state)

        if not response.can_answer:
            if self._is_on_topic(question):
                return {
                    "answer": CANNOT_ANSWER_MESSAGE,
                    "can_answer": False,
                    "confidence": response.confidence,
                    "sources": [],
                    "needs_human": True,
                    "agent_name": self.name,
                    "reasoning_trace": response.reasoning_trace,
                    "flow_status": {},
                }
            return {
                "answer": OFF_TOPIC_MESSAGE,
                "can_answer": True,
                "confidence": response.confidence,
                "sources": [],
                "needs_human": False,
                "agent_name": self.name,
                "reasoning_trace": response.reasoning_trace,
                "flow_status": {},
            }

        glossary = glossary_search.invoke({"query": question})
        if glossary.ok and not response.sources:
            response.sources = glossary.sources[:3]

        return {
            "answer": response.answer,
            "can_answer": response.can_answer,
            "confidence": response.confidence,
            "sources": response.sources,
            "needs_human": False,
            "agent_name": self.name,
            "reasoning_trace": response.reasoning_trace,
            "flow_status": {},
        }
