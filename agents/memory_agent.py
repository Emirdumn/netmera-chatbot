"""Her kullanıcı mesajında çalışan bellek çıkarım agent'ı — tool değil, LLM
agent'ı. Konuşmadan yapısal bilgi çıkarır; sonuç customer_profile/case_notes'a
merge edilir (bkz. graph/state.py:merge_dict).

Kural: emin olunmayan alan None/boş bırakılır, ASLA tahmin edilmez — uydurma
bilgi profile girerse tüm sistemin yönlendirmesi bozulur.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from llm.client import get_llm

SYSTEM_PROMPT = """Sen bir musteri mesajindan yapisal bilgi cikaran bir analiz
agentisin. Asagidaki alanlari SADECE mesajda ACIKCA belirtilmisse doldur.
Emin olmadigin, tahmin ettigin veya mesajda gecmeyen HER alani None (liste
alanlari icin bos liste) birak — ASLA uydurma veya varsayma.

{pending_context}Mesaj: "{message}\""""


class ExtractedFacts(BaseModel):
    person_name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    sector: Optional[str] = None
    app_name: Optional[str] = None
    platform: list[Literal["ios", "android", "web", "flutter", "react-native", "huawei"]] = []
    user_scale: Optional[str] = None
    is_existing_customer: Optional[bool] = None
    goal: Optional[str] = None
    problem_summary: Optional[str] = Field(
        default=None,
        description="SADECE musteri bir SEY CALISMIYOR/BOZUK diye sikayet "
                    "ediyorsa doldur (ör. 'push bildirimleri gitmiyor', "
                    "'giris yapamiyorum'). Asagidaki durumlarda bu alan HER "
                    "ZAMAN None kalmali — bunlarin hicbiri bir urun "
                    "sorunu/sikayeti DEGILDIR: (1) 'X nasil yapilir?', 'X "
                    "nedir?' gibi bilgi/nasil-yapilir sorulari, (2) 'anlamadim',"
                    " 'ne demek istedin', 'ne istedin benden' gibi botun "
                    "kendisiyle ilgili kafa karisikligi/aciklama talepleri.",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Musterinin bahsettigi somut hata/semptom ifadesi — "
                    "hata kodu, exception, 'X null donuyor', '401 aliyorum' "
                    "gibi spesifik bir teknik belirti varsa buraya yaz.",
    )
    sdk_version: Optional[str] = None
    steps_tried: list[str] = []


PROFILE_FIELDS = [
    "person_name", "company", "email", "phone", "sector",
    "app_name", "platform", "user_scale", "is_existing_customer",
]
CASE_FIELDS = ["goal", "problem_summary", "error_message", "sdk_version", "steps_tried"]


class MemoryAgent:
    name = "memory_agent"

    def __init__(self):
        self.structured_llm = get_llm(temperature=0).with_structured_output(ExtractedFacts)

    def extract(self, message: str, pending_question: str = "") -> ExtractedFacts:
        # Botun bir onceki turda sordugu soru verilirse, musterinin cumle
        # icine gomulu/dolayli cevabini (ör. "uygulamamiz bir X uygulamasi"
        # -> app_name) dogru alana baglayabilir — sadece izole mesaja
        # bakildiginda bu baglam kaybolup alan bos birakilabiliyordu.
        pending_context = (
            f'Botun bu mesajdan hemen once sordugu soru: "{pending_question}"\n'
            if pending_question else ""
        )
        return self.structured_llm.invoke(
            SYSTEM_PROMPT.format(pending_context=pending_context, message=message)
        )
