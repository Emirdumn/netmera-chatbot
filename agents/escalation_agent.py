"""Cevap uretmez, devri yonetir: sohbeti ozetler, departman/aciliyet atar,
availability_tool ile musait personel arar, handoff_tool veya ticket_tool
cagirir."""
from agents.base import BaseAgent
from llm.client import extract_text

SUMMARY_PROMPT = """Asagidaki musteri sohbetini 2-3 cumleyle ozetle. Musterinin
ne istedigini ve botun nereye kadar yardimci olabildigini belirt.

Sohbet:
{transcript}"""

# escalation_reason'a gore mesaja eklenecek kisa on-cumle — musteri neden
# devredildigini anlasin (bkz. graph/nodes.py:_specialist_node icin reason
# degerleri).
REASON_PREFIX = {
    "low_confidence_or_cannot_answer": "Sorunuza tam olarak cevap veremedim, ",
    "frustrated": "Sizi daha iyi anlayabilmesi icin ",
    "max_failed_attempts": "Bu konuda yeterince yardimci olamadim, ",
}


class EscalationAgent(BaseAgent):
    name = "escalation_agent"
    department = "escalation"

    def _summarize(self, transcript):
        if not transcript:
            return ""
        return extract_text(self.llm.invoke(SUMMARY_PROMPT.format(transcript=transcript)))

    def _transcript(self, state):
        lines = []
        for m in state.get("messages", []):
            content = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", str(m))
            lines.append(content)
        return "\n".join(lines)

    def run(self, state):
        summary = self._summarize(self._transcript(state))
        department = state.get("department", "customer_success")
        urgency = state.get("urgency", "normal")
        session_id = state.get("session_id")

        availability_tool = self._find_tool("availability_tool")
        handoff_tool = self._find_tool("handoff_tool")
        ticket_tool = self._find_tool("ticket_tool")

        availability = availability_tool.invoke({"department": department})
        if availability.ok and availability.data:
            result = handoff_tool.invoke({
                "session_id": session_id, "department": department,
                "summary": summary, "urgency": urgency,
            })
        else:
            result = ticket_tool.invoke({
                "session_id": session_id, "department": department,
                "summary": summary, "urgency": urgency,
            })
        prefix = REASON_PREFIX.get(state.get("escalation_reason", ""), "")
        message = prefix + result.summary[0].lower() + result.summary[1:] if prefix else result.summary

        return {
            "answer": message,
            "escalation_summary": summary,
            "escalation_department": department,
            "escalation_urgency": urgency,
            "agent_name": self.name,
        }
