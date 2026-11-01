"""Router: sends a task to the right agent.

Uses a LangGraph workflow when `langgraph` is installed, and falls back to a plain
call otherwise, so the project (and the tests) never depend on it being present.
"""

from typing import Any, TypedDict

from .base import Agent, AgentResult
from .rfp import RfpAgent
from .curriculum import CurriculumAgent
from .document import DocumentAgent
from .marketing import MarketingAgent

try:  # optional dependency
    from langgraph.graph import StateGraph, END
except ImportError:  # pragma: no cover - depends on the environment
    StateGraph = None
    END = None


class WorkflowState(TypedDict, total=False):
    agent_name: str
    task: dict[str, Any]
    result: AgentResult


class Orchestrator:
    def __init__(self):
        agents = (
            RfpAgent(),
            CurriculumAgent(),
            DocumentAgent(),
            MarketingAgent(),
        )
        self.agents: dict[str, Agent] = {
            agent.name: agent for agent in agents
        }

        self.workflow = None
        if StateGraph is not None:
            graph = StateGraph(WorkflowState)
            graph.add_node("dispatch", self._dispatch_node)
            graph.set_entry_point("dispatch")
            graph.add_edge("dispatch", END)
            self.workflow = graph.compile()

    def register(self, agent: Agent):
        self.agents[agent.name] = agent

    def _run_agent(self, agent_name: str, task: dict) -> AgentResult:
        agent = self.agents.get(agent_name)

        if not agent:
            return AgentResult(
                agent_name,
                False,
                message=f"Unknown agent '{agent_name}'",
            )

        try:
            return agent.run(task)
        except Exception as error:
            return AgentResult(
                agent_name,
                False,
                message=f"Agent error: {error}",
            )

    def _dispatch_node(self, state: WorkflowState) -> WorkflowState:
        return {"result": self._run_agent(state["agent_name"], state["task"])}

    def dispatch(self, agent_name: str, task: dict) -> AgentResult:
        if self.workflow is None:
            return self._run_agent(agent_name, task)

        state = self.workflow.invoke({"agent_name": agent_name, "task": task})
        return state["result"]
