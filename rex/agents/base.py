"""Common interface every REX agent implements, so the orchestrator can route to it."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class AgentResult:
    agent: str
    ok: bool
    output: dict = field(default_factory=dict)   # structured payload other agents can reuse
    message: str = ""                            # human-readable text
    sources: list[str] = field(default_factory=list)  # traceability requirement

class Agent(ABC):
    name: str
    @abstractmethod
    def run(self, task: dict) -> AgentResult: ...
