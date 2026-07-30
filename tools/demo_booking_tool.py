"""Demo talebi kaydı (tarih tercihi + iletişim)."""
from tools.base import ToolResult, netmera_tool


@netmera_tool
def demo_booking_tool(preferred_date: str, contact: str) -> ToolResult:
    """Demo talebini tarih tercihi ve iletişim bilgisiyle kaydeder."""
    summary = f"Demo talebi alindi: {preferred_date} tarihi icin, iletisim: {contact}"
    return ToolResult(
        ok=True,
        data={"preferred_date": preferred_date, "contact": contact},
        summary=summary,
        sources=[],
    )
