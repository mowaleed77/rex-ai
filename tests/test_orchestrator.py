from pathlib import Path

from rex.agents.base import Agent, AgentResult
from rex.agents.orchestrator import Orchestrator


def test_curriculum_agent_is_registered():
    orchestrator = Orchestrator()

    result = orchestrator.dispatch("curriculum", {
        "curriculum": [
            {"course": "Python Basics", "topics": ["Variables", "Loops"]}
        ]
    })

    # The curriculum agent defaults to validation; this legacy test task is
    # intentionally retained to protect the original registration contract.
    assert result.ok
    assert result.agent == "curriculum"


def test_document_agent_is_registered(tmp_path):
    orchestrator = Orchestrator()

    result = orchestrator.dispatch("document", {
        "document_type": "course_description",
        "title": "Python Basics",
        "content": ["Introduction to Python"],
        "output_dir": str(tmp_path),
    })

    assert result.ok
    assert Path(result.output["file_path"]).exists()


def test_unknown_agent():
    result = Orchestrator().dispatch("unknown", {})

    assert not result.ok
    assert "Unknown agent" in result.message


def test_course_launch_runs_three_agents_and_keeps_marketing_pending(tmp_path):
    orchestrator = Orchestrator()

    result = orchestrator.run_workflow("course_launch", {
        "course": "Python Basics",
        "level": "Beginner",
        "learning_outcomes": ["Use variables", "Write loops"],
        "duration_hours": 12,
        "description": "An introductory Python course.",
        "target_audience": "new programmers",
        "price": 2500,
        "output_dir": str(tmp_path),
    })

    assert result.ok
    assert result.agent == "orchestrator"
    assert set(result.output["stages"]) == {"curriculum", "document", "marketing"}
    assert Path(result.output["document"]["file_path"]).exists()
    assert result.output["marketing"]["status"] == "pending_admin_approval"
    assert result.output["marketing"]["approved"] is False
    assert result.output["marketing"]["published"] is False
    assert "admin approval" in result.message.lower()


def test_course_launch_stops_if_curriculum_fails(tmp_path):
    result = Orchestrator().run_workflow("course_launch", {
        "course": "Python Basics",
        "learning_outcomes": [],
        "output_dir": str(tmp_path),
    })

    assert not result.ok
    assert "curriculum" in result.output["stages"]
    assert "document" not in result.output["stages"]
    assert "marketing" not in result.output["stages"]


def test_course_launch_reports_downstream_failure(tmp_path):
    class FailingDocumentAgent(Agent):
        name = "document"

        def run(self, task):
            return AgentResult(self.name, False, message="simulated PDF failure")

    orchestrator = Orchestrator()
    orchestrator.register(FailingDocumentAgent())
    result = orchestrator.run_workflow("course_launch", {
        "course": "Python Basics",
        "learning_outcomes": ["Use variables"],
        "output_dir": str(tmp_path),
    })

    assert not result.ok
    assert result.output["stages"]["document"]["ok"] is False
    # Marketing is independent of PDF rendering and should still be generated.
    assert result.output["stages"]["marketing"]["ok"] is True


def test_unknown_workflow_is_rejected():
    result = Orchestrator().run_workflow("unknown", {})

    assert not result.ok
    assert "Unknown workflow" in result.message
