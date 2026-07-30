"""'Netmera nedir', 'hangi sektorlere hizmet veriyor' gibi genel sorular.
Kaynak: website + glossary.

Not: cevap bulunabildigi surece devir ACILMAZ. RAG hicbir sey bulamazsa iki
durum ayirt edilir:
  - Soru Netmera ile ilgili ama bilgi public degil/eksik (ör. "kac kisilik
    ekip calistiriyorsunuz") -> digger agent'lar gibi devreye girer, bos
    mesaj yerine durustce soyleyip insana baglanma teklif eder.
  - Soru tamamen alakasiz (ör. "bugun hava nasil") -> devir ACILMAZ, nazikce
    kapsam disi oldugu belirtilir (bir insani bosuna mesgul etmemek icin)."""
from pydantic import BaseModel

from agents.base import BaseAgent
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


class _TopicRelevance(BaseModel):
    is_netmera_related: bool


class GeneralAgent(BaseAgent):
    name = "general_agent"
    department = "general"
    search_source = "website"
    system_prompt = SYSTEM_PROMPT

    def _is_on_topic(self, question):
        structured_llm = self.llm.with_structured_output(_TopicRelevance)
        result = structured_llm.invoke(
            "Bu soru Netmera (bir musteri etkilesim/pazarlama platformu) "
            "sirketi/urunu ile ilgili mi, yoksa hava durumu, spor, genel "
            f'sohbet gibi tamamen alakasiz bir konu mu? Soru: "{question}"'
        )
        return result.is_netmera_related

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
