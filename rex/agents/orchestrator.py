"""LangGraph-based router for the REX AI agents."""

from typing import TypedDict, Any

from langgraph.graph import StateGraph, END

from .base import Agent, AgentResult
from .curriculum import CurriculumAgent
from .document import DocumentAgent
from .marketing import MarketingAgent
from .rfp import RfpAgent


class WorkflowState(TypedDict, total=False):
    agent_name: str
    task: dict[str, Any]
    result: AgentResult


class Orchestrator:
    def __init__(self):
        self.agents: dict[str, Agent] = {
            agent.name: agent
            for agent in (
                RfpAgent(),
                CurriculumAgent(),
                DocumentAgent(),
                MarketingAgent(),
            )
        }

        graph = StateGraph(WorkflowState)
        graph.add_node("dispatch", self._dispatch_node)
        graph.set_entry_point("dispatch")
        graph.add_edge("dispatch", END)
        self.workflow = graph.compile()

    def register(self, agent: Agent):
        self.agents[agent.name] = agent

    def _dispatch_node(self, state: WorkflowState) -> WorkflowState:
        agent_name = state["agent_name"]
        task = state["task"]

        agent = self.agents.get(agent_name)

        if agent is None:
            result = AgentResult(
                agent_name,
                False,
                message=f"Unknown agent '{agent_name}'",
            )
        else:
            try:
                result = agent.run(task)
            except Exception as error:
                result = AgentResult(
                    agent_name,
                    False,
                    message=f"Agent error: {error}",
                )

        return {"result": result}

    def dispatch(self, agent_name: str, task: dict) -> AgentResult:
        state = self.workflow.invoke({
            "agent_name": agent_name,
            "task": task,
        })
        return state["result"]
