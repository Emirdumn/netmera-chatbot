"""handoffs tablosuna pending kayıt açar, oturumu waiting_human yapar,
müşteriye gösterilecek bilgilendirme metnini döndürür."""
from config.departments import DEPARTMENTS
from storage.repository import create_handoff
from tools.base import ToolResult, netmera_tool


@netmera_tool
def handoff_tool(session_id: int, department: str, summary: str, urgency: str = "normal") -> ToolResult:
    """Müsait personel varken insana devir kaydı açar (pending)."""
    handoff_id = create_handoff(session_id, department, "bot_escalation", summary, urgency)
    dept_name = DEPARTMENTS.get(department, {}).get("name", department)
    message = f"Sizi {dept_name} ekibimize aktariyorum, birazdan bir yetkili size baglanacak."
    return ToolResult(ok=True, data={"handoff_id": handoff_id}, summary=message, sources=[])
