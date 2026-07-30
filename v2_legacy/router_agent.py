"""Niyet + dil tespiti — tool kullanmaz, tek LLM çağrısıyla döner."""
from typing import Literal

from pydantic import BaseModel

from llm.client import get_llm

FEW_SHOT = """Ornekler:
Mesaj: "Netmera'nin fiyati nedir, demo alabilir miyim?"
-> intent: sales, language: tr, department: sales, urgency: normal

Mesaj: "Push bildirimi 3 gundur gitmiyor, hesabimda sorun var, cok sinirliyim"
-> intent: support, language: tr, department: customer_success, urgency: high

Mesaj: "Android SDK push token alamiyorum"
-> intent: technical, language: tr, department: engineering, urgency: normal

Mesaj: "Segment olusturamiyorum yardim edin"
-> intent: support, language: tr, department: customer_success, urgency: normal

Mesaj: "Kural bazli segment nasil olusturulur?"
-> intent: support, language: tr, department: customer_success, urgency: normal

Mesaj: "Bir yetkiliyle gorusmek istiyorum"
-> intent: handoff_request, language: tr, department: customer_success, urgency: normal

Mesaj: "Netmera almak istiyorum, bir satis temsilcisiyle gorusebilir miyim?"
-> intent: handoff_request, language: tr, department: sales, urgency: normal

Mesaj: "Netmera nedir, ne ise yarar?"
-> intent: general, language: tr, department: general, urgency: low
"""

SYSTEM_PROMPT = f"""Sen bir musteri mesajini siniflandiran router'sin.
Asagidaki alanlari doldur:
- intent: sales | support | technical | general | handoff_request
- language: tr | en
- department: sales | customer_success | engineering | general
- urgency: low | normal | high

ONEMLI KURALLAR:
1. Mesaj bir konuyla (satis, destek, teknik) ilgili olsa bile, musteri
   acikca bir insanla/yetkiliyle/temsilciyle gorusmek istedigini
   belirtiyorsa (ornek ifadeler: "temsilciyle gorusmek", "yetkiliyle
   gorusmek", "bir insanla konusmak", "canli destek") intent HER ZAMAN
   handoff_request olmali — konu department alanina yansitilir (ör.
   satisla ilgiliyse department=sales).
2. support ile technical arasindaki fark: musteri Netmera PANELINDE
   (arayuzde tiklayarak) bir islemi nasil yapacagini soruyorsa (segment,
   kampanya, otomasyon, panel ayarlari) -> support. Kod yazarak, SDK/API
   entegre ederek veya gelistirici olarak yapilan bir islemi soruyorsa
   (mobil SDK, REST API, kod ornegi, sertifika/anahtar kurulumu) ->
   technical. "Segment nasil olusturulur" gibi panel islemleri her zaman
   support'tur, teknik degildir.

{FEW_SHOT}"""


class RouteResult(BaseModel):
    intent: Literal["sales", "support", "technical", "general", "handoff_request"]
    language: Literal["tr", "en"]
    department: Literal["sales", "customer_success", "engineering", "general"]
    urgency: Literal["low", "normal", "high"]


class RouterAgent:
    name = "router"

    def __init__(self):
        self.structured_llm = get_llm(temperature=0).with_structured_output(RouteResult)

    def classify(self, message: str) -> RouteResult:
        return self.structured_llm.invoke(f'{SYSTEM_PROMPT}\n\nMesaj: "{message}"')

    def run(self, state):
        message = state["messages"][-1]
        content = message.get("content", "") if isinstance(message, dict) else getattr(message, "content", str(message))
        result = self.classify(content)
        return {
            "intent": result.intent,
            "language": result.language,
            "department": result.department,
            "urgency": result.urgency,
        }
