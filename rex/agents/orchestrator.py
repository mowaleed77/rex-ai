"""Router: sends a task to the right agent. Sprint 3 adds multi-agent workflows."""
from .base import Agent, AgentResult
from .stubs import RfpAgent, CurriculumAgent, DocumentAgent, MarketingAgent

class Orchestrator:
    def __init__(self):
        self.agents: dict[str, Agent] = {a.name: a for a in (RfpAgent(), CurriculumAgent(), DocumentAgent(), MarketingAgent())}

    def register(self, agent: Agent): self.agents[agent.name] = agent

    def dispatch(self, agent_name: str, task: dict) -> AgentResult:
        agent = self.agents.get(agent_name)
        if not agent: return AgentResult(agent_name, False, message=f"Unknown agent '{agent_name}'")
        try: return agent.run(task)
        except Exception as e:  # logging/error-handling requirement
            return AgentResult(agent_name, False, message=f"Agent error: {e}")
