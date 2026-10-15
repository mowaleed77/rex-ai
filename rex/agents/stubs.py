"""Placeholders for Sprint 2 agents. Each owner replaces their stub in their own module."""
from .base import Agent, AgentResult

class _Stub(Agent):
    def run(self, task: dict) -> AgentResult:
        return AgentResult(self.name, False, message=f"{self.name} not implemented yet (Sprint 2)")

class RfpAgent(_Stub): name = "rfp_research"           # Egypt + Saudi Arabia only
class CurriculumAgent(_Stub): name = "curriculum"      # never claims official accreditation
class DocumentAgent(_Stub): name = "document"          # PDF generation
class MarketingAgent(_Stub): name = "marketing"        # needs admin approval before publishing
