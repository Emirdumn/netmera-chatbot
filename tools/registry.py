"""Bir departmana hangi tool'ların verileceğini döndürür."""
from tools.availability_tool import availability_tool
from tools.demo_booking_tool import demo_booking_tool
from tools.glossary_tool import glossary_search
from tools.handoff_tool import handoff_tool
from tools.lead_capture_tool import lead_capture_tool
from tools.query_builder_tool import query_builder_tool
from tools.rag_search_tool import rag_search
from tools.ticket_tool import ticket_tool

DEPARTMENT_TOOLS = {
    "sales": [rag_search, query_builder_tool, glossary_search, lead_capture_tool, demo_booking_tool],
    "customer_success": [rag_search, query_builder_tool],
    "engineering": [rag_search, query_builder_tool],
    "general": [rag_search, query_builder_tool, glossary_search],
    "escalation": [availability_tool, handoff_tool, ticket_tool],
}


def get_tools_for(department):
    return DEPARTMENT_TOOLS.get(department, [rag_search])
