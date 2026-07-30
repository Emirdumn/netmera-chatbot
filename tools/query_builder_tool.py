"""Konuşmayı ve müşteri bağlamını tek, bağımsız, İNGİLİZCE bir arama
sorgusuna çevirir (dokümanlar İngilizce). Tek başına anlamsız takip sorularını
("peki ya android'de?") ve TR soru / EN doküman uyumsuzluğunu çözer."""
from pydantic import BaseModel

from llm.client import get_llm
from tools.base import ToolResult, netmera_tool

PROMPT = """Asagidaki konusmayi ve musteri baglamini tek, bagimsiz, INGILIZCE
bir arama sorgusuna cevir. Sorgu dokumantasyonda arama yapmak icin
kullanilacak.

KURALLAR:
1. Sorgu SADECE musterinin EN SON mesajinin ne istedigini yansitmalidir.
   Konusma gecmisi SADECE zamirleri/eksik baglami cozmek icindir (ör. "ya
   android tarafinda?" -> konunun SDK entegrasyonu oldugunu ama PLATFORMUN
   simdi Android'e degistigini anla).
2. Musteri farkli bir platforma/konuya gectiyse (ör. onceki tur iOS'tu, simdi
   "ya android'de?" diyor), sorguda SADECE YENI platformu/konuyu kullan —
   ESKI platformu (iOS) sorguya EKLEME. Iki platformu/konuyu ayni sorguda
   BIRLESTIRME.
   Ornek: onceki tur "iOS SDK integration" idi, yeni mesaj "ya android'de?"
   -> DOGRU sorgu: "Android SDK integration"  |  YANLIS: "iOS Android SDK integration"
3. Konu adlarini (platform, SDK, ozellik) acikca yaz, "it"/"that" gibi zamir
   kullanma.
{previous_note}

Konusma:
{conversation}

Musteri baglami: {profile_context}

Sadece arama sorgusunu yaz, baska hicbir sey ekleme."""


class QueryResult(BaseModel):
    query: str


@netmera_tool
def query_builder_tool(conversation: str, profile_context: str = "", previous_query: str = "") -> ToolResult:
    """Konusma + profilden bagimsiz, Ingilizce bir arama sorgusu uretir."""
    previous_note = ""
    if previous_query:
        previous_note = (
            f'\nOnceki sorgu ("{previous_query}") yeterli sonuc getirmedi, '
            "farkli/daha spesifik kelimelerle yeniden yaz."
        )
    structured_llm = get_llm(temperature=0).with_structured_output(QueryResult)
    result = structured_llm.invoke(PROMPT.format(
        previous_note=previous_note,
        conversation=conversation,
        profile_context=profile_context or "(yok)",
    ))
    return ToolResult(ok=True, data={"query": result.query}, summary=result.query, sources=[])
