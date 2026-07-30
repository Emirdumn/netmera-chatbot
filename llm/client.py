"""Tek LLM giriş noktası — proje genelinde LLM'e sadece buradan erişilir.

LLM_PROVIDER ayarına göre Gemini (dogrudan) veya OpenRouter (OpenAI-uyumlu
API) kullanilir. Gemini'nin ucretsiz kota limiti (gunluk 20 istek) hizli
tukendigi icin varsayilan olarak OpenRouter'a gecilebilir; embedding hala
lokal (sentence-transformers) oldugu icin bu secim sadece sohbet cagrilarini
etkiler."""
from config.settings import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LLM_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
)


def get_llm(temperature: float = 0.2):
    if LLM_PROVIDER == "openrouter":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=OPENROUTER_MODEL,
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=temperature,
        )

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GEMINI_API_KEY,
        temperature=temperature,
    )


def extract_text(message) -> str:
    """Gemini bazen content'i duz string yerine [{'type':'text',...}] blok
    listesi olarak dondurur (ozellikle dusunme/imza verisiyle). Ham .content
    kullanan her yer bu fonksiyondan gecmeli."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)
