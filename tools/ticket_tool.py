"""Kimse müsait değilse asenkron kayıt açar, TICKET-XXXX numarası ve
tahmini dönüş süresi bildirir."""
from config.departments import DEPARTMENTS
from storage.repository import create_handoff
from tools.base import ToolResult, netmera_tool


@netmera_tool
def ticket_tool(session_id: int, department: str, summary: str, urgency: str = "normal") -> ToolResult:
    """Müsait personel yokken TICKET-XXXX numaralı asenkron kayıt açar."""
    handoff_id = create_handoff(session_id, department, "no_staff_available", summary, urgency)
    ticket_number = f"TICKET-{handoff_id:04d}"
    dept = DEPARTMENTS.get(department, {})
    dept_name = dept.get("name", department)
    hours = dept.get("working_hours", "09:00-18:00")
    message = (
        f"Su an {dept_name} ekibimizde kimse cevrimici degil. Talebiniz "
        f"{ticket_number} numarasiyla kaydedildi, {hours} arasinda size "
        "donus yapilacak."
    )
    return ToolResult(
        ok=True,
        data={"handoff_id": handoff_id, "ticket_number": ticket_number},
        summary=message,
        sources=[],
    )
