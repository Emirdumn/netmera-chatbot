"""Satış senaryosunda ad, şirket, e-posta, uygulama türü, tahmini kullanıcı
sayısı toplar; eksik alanları agent'ın sorması için missing_fields döndürür."""
from tools.base import ToolResult, netmera_tool

REQUIRED_FIELDS = ["name", "company", "email", "app_type", "estimated_users"]


@netmera_tool
def lead_capture_tool(
    name: str = "",
    company: str = "",
    email: str = "",
    app_type: str = "",
    estimated_users: str = "",
) -> ToolResult:
    """Satış lead bilgilerini toplar, eksik alanları missing_fields olarak döndürür."""
    lead = {
        "name": name,
        "company": company,
        "email": email,
        "app_type": app_type,
        "estimated_users": estimated_users,
    }
    missing_fields = [f for f in REQUIRED_FIELDS if not lead[f]]
    ok = not missing_fields
    summary = "Lead bilgisi tam" if ok else f"Eksik alanlar: {', '.join(missing_fields)}"
    return ToolResult(
        ok=ok,
        data={"lead": lead, "missing_fields": missing_fields},
        summary=summary,
        sources=[],
    )
