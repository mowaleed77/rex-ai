
"""Router: sends a task to the right agent. Sprint 3 adds multi-agent workflows."""

from .base import Agent, AgentResult
from .stubs import CurriculumAgent, DocumentAgent, MarketingAgent
from .rfp import RfpAgent


class Orchestrator:
    def __init__(self):
        agents = (
            RfpAgent(),
            CurriculumAgent(),
            DocumentAgent(),
            MarketingAgent()
        )
        self.agents: dict[str, Agent] = {
            agent.name: agent for agent in agents
        }

    def register(self, agent: Agent):
        self.agents[agent.name] = agent

    def dispatch(self, agent_name: str, task: dict) -> AgentResult:
        agent = self.agents.get(agent_name)

        if not agent:
            return AgentResult(
                agent_name,
                False,
                message=f"Unknown agent '{agent_name}'"
            )

        try:
            return agent.run(task)
        except Exception as error:
            return AgentResult(
                agent_name,
                False,
                message=f"Agent error: {error}"
            )

