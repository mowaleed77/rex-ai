
from pathlib import Path

from rex.agents.orchestrator import Orchestrator


def test_curriculum_agent_is_registered():
    orchestrator = Orchestrator()

    result = orchestrator.dispatch("curriculum", {
        "curriculum": [
            {
                "course": "Python Basics",
                "topics": ["Variables", "Loops"]
            }
        ]
    })

    assert result.ok
    assert result.agent == "curriculum"


def test_document_agent_is_registered(tmp_path):
    orchestrator = Orchestrator()

    result = orchestrator.dispatch("document", {
        "document_type": "course_description",
        "title": "Python Basics",
        "content": ["Introduction to Python"],
        "output_dir": str(tmp_path)
    })

    assert result.ok
    assert Path(result.output["file_path"]).exists()


def test_unknown_agent():
    result = Orchestrator().dispatch("unknown", {})

    assert not result.ok
    assert "Unknown agent" in result.message
