
"""Router: sends tasks to the appropriate agent."""

from .base import Agent, AgentResult
from .stubs import RfpAgent, MarketingAgent
from .curriculum import CurriculumAgent
from .document import DocumentAgent


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
