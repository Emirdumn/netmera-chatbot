"""Departmanda çevrimiçi (is_online=1) personel olup olmadığını kontrol eder."""
from storage.repository import list_online_staff
from tools.base import ToolResult, netmera_tool


@netmera_tool
def availability_tool(department: str) -> ToolResult:
    """Departmanda çevrimiçi (müsait) personel olup olmadığını kontrol eder."""
    staff = list_online_staff(department)
    if not staff:
        return ToolResult(ok=False, data=[], summary="Musait personel yok", sources=[])
    names = [s["name"] for s in staff]
    return ToolResult(ok=True, data=staff, summary=f"Musait: {', '.join(names)}", sources=[])
