"""Servis katmaninin dondurdugu bicimler.

Bunlar UI'a da widget_api'ye de ayni sekilde gider; hicbiri Streamlit'e
ya da HTTP'ye bagli degildir.
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ConversationState:
    """Bir oturumun o anki tam gorunumu — UI'in ekrani cizmek icin
    ihtiyaci olan HER SEY burada; UI ayrica graph/DB'ye sormaz."""

    session_id: int
    messages: list[dict] = field(default_factory=list)
    status: str = "bot"
    #: Musteri bir insana aktarilmayi bekliyor (bot devrede degil).
    is_waiting: bool = False
    #: Bekleyen LangGraph interrupt'inin sebebi (varsa).
    pending_reason: Optional[str] = None
    #: Ad/e-posta formu gosterilmeli mi.
    needs_contact_form: bool = False


@dataclass
class TurnResult:
    """send_message() sonucu."""

    #: Bot bu turda bir insana devretti mi.
    escalated: bool = False
    #: Bot cevap uretmedi (musteri zaten insan bekliyordu) — mesaj sadece
    #: personel konsoluna dustu.
    bot_skipped: bool = False
    #: Sunum katmani icin ham orkestratör kararlari (kenar cubugu panelleri).
    orchestrator: dict[str, Any] = field(default_factory=dict)
