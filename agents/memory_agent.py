"""Her kullanıcı mesajında çalışan bellek çıkarım agent'ı — tool değil, LLM
agent'ı. Konuşmadan yapısal bilgi çıkarır; sonuç customer_profile/case_notes'a
merge edilir (bkz. graph/state.py:merge_dict).

Kural: emin olunmayan alan None/boş bırakılır, ASLA tahmin edilmez — uydurma
bilgi profile girerse tüm sistemin yönlendirmesi bozulur.
"""
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from llm.client import get_llm

# pending_question varken veya asagidaki sinyaller varken extract ASLA atlanmaz.
_MEMORY_SIGNAL_RE = re.compile(
    r"("
    r"[^@\s]+@[^@\s]+\.[^@\s]+"
    r"|\b(\+?\d[\d\s\-()]{7,}\d)\b"
    r"|\b(şirket\w*|sirket\w*|company|firma\w*|platform\w*|ios|android|flutter|"
    r"react\s*native|huawei|sdk|exception|stack\s*trace|"
    r"temsilci\w*|canlı\s*destek|canli\s*destek|müşteri\s*temsilci\w*|"
    r"musteri\s*temsilci\w*|fiyat\w*|ücret\w*|ucret\w*|demo\w*|satın\s*al\w*|"
    r"satin\s*al\w*|paket\w*|pricing|quote\w*|hata\w*|error\w*|401|403|500|"
    r"çalışmıyor|calismiyor|bozuk|alamıyorum|alamiyorum)\b"
    r")",
    re.IGNORECASE,
)

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


def should_run_memory_extract(message: str, pending_question: str = "") -> bool:
    """Saf dokuman sorularinda CONTROL extract'i atla; slot/devir sinyallerinde calistir."""
    if (pending_question or "").strip():
        return True
    text = (message or "").strip()
    if not text:
        return False
    if _MEMORY_SIGNAL_RE.search(text):
        return True
    if "?" in text or re.search(
        r"\b(nedir|nasıl|nasil|how|what|where|neden|niye)\b", text, re.IGNORECASE
    ):
        return False
    if len(text) <= 40:
        return False
    return True


class MemoryAgent:
    name = "memory_agent"

    def __init__(self):
        self.structured_llm = get_llm(
            temperature=0, tier="control", call_site="memory_agent.extract",
        ).with_structured_output(ExtractedFacts)

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
