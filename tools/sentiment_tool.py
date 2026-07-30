"""Müşteri memnuniyetsizliğini tek LLM çağrısıyla tespit eder — devir tetikleyici #4."""
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


class SentimentResult(BaseModel):
    sentiment: Literal["neutral", "confused", "frustrated"]


@netmera_tool
def detect_sentiment(message: str) -> ToolResult:
    """Müşteri mesajının duygu durumunu (neutral/confused/frustrated) tespit eder."""
    structured_llm = get_llm(temperature=0).with_structured_output(SentimentResult)
    result = structured_llm.invoke(SENTIMENT_PROMPT.format(message=message))
    return ToolResult(
        ok=True,
        data={"sentiment": result.sentiment},
        summary=result.sentiment,
        sources=[],
    )
