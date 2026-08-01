"""Müşteri memnuniyetsizliğini tespit eder — devir tetikleyici #4.

Once keyword/regex fast path; sadece belirsiz mesajlarda CONTROL LLM.
"""
import re
from typing import Literal

from pydantic import BaseModel

from llm.client import get_llm
from tools.base import ToolResult, netmera_tool

SENTIMENT_PROMPT = """Asagidaki musteri mesajinin duygu durumunu belirle.
Sadece su uc kategoriden birini sec: neutral, confused, frustrated.
- neutral: sakin, normal soru
- confused: kafasi karismis, ne yapacagini bilmiyor
- frustrated: sinirli, ofkeli, sikayetci

Mesaj: {message}"""

_FRUSTRATED_RE = re.compile(
    r"("
    r"\b(berbat|rezalet|saçma|sacma|kızgınım|kizginim|öfkeli|ofkeli|"
    r"sinir(?:im|liyim)?|bıktım|biktım|bıktim|biktim|"
    r"yeter\s+artık|yeter\s+artik|işe\s+yaram[ıi]yor|ise\s+yaram[ıi]yor|"
    r"rezil|kötü\s+hizmet|kotu\s+hizmet|şikayet|sikayet|şikâyet|"
    r"useless|terrible|awful|horrible|frustrated|angry|worst|"
    r"waste\s+of\s+time)\b"
    r"|[!?]{3,}"
    r")",
    re.IGNORECASE,
)

_CONFUSED_HINT_RE = re.compile(
    r"\b("
    r"anlamadım|anlamadim|anlamıyorum|anlamiyorum|karışık|karisik|"
    r"ne\s+demek|nasıl\s+yani|nasil\s+yani|confused|"
    r"ne\s+yapacağım|ne\s+yapacagim"
    r")\b",
    re.IGNORECASE,
)

_SHORT_NEUTRAL_RE = re.compile(
    r"^(merhaba|selam|teşekkürler|tesekkurler|thanks|ok|okay|tamam|"
    r"anladım|anladim|evet|hayır|hayir|yes|no)[\s!.?]*$",
    re.IGNORECASE,
)


class SentimentResult(BaseModel):
    sentiment: Literal["neutral", "confused", "frustrated"]


def classify_sentiment_fast(message: str) -> str | None:
    """Regex/heuristic sonuc; emin degilse None (LLM'e birak)."""
    text = (message or "").strip()
    if not text:
        return "neutral"
    if _FRUSTRATED_RE.search(text):
        return "frustrated"
    if _SHORT_NEUTRAL_RE.match(text):
        return "neutral"
    if len(text) <= 160 and "?" in text and not _CONFUSED_HINT_RE.search(text):
        if "!!" not in text:
            return "neutral"
    if len(text) <= 80 and not _CONFUSED_HINT_RE.search(text) and "!" not in text:
        return "neutral"
    return None


@netmera_tool
def detect_sentiment(message: str) -> ToolResult:
    """Müşteri mesajının duygu durumunu (neutral/confused/frustrated) tespit eder."""
    fast = classify_sentiment_fast(message)
    if fast is not None:
        return ToolResult(
            ok=True,
            data={"sentiment": fast, "via": "fast_path"},
            summary=fast,
            sources=[],
        )

    structured_llm = get_llm(
        temperature=0, tier="control", call_site="sentiment_tool",
    ).with_structured_output(SentimentResult)
    result = structured_llm.invoke(SENTIMENT_PROMPT.format(message=message))
    return ToolResult(
        ok=True,
        data={"sentiment": result.sentiment, "via": "llm"},
        summary=result.sentiment,
        sources=[],
    )
