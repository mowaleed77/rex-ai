
from rex.agents.curriculum import CurriculumAgent


def test_valid_curriculum():
    agent = CurriculumAgent()

    result = agent.run({
        "curriculum": [
            {
                "course": "Python Basics",
                "topics": ["Variables", "Loops", "Functions"]
            }
        ]
    })

    assert result.ok
    assert result.output["course_count"] == 1
    assert result.output["issues"] == []
    assert result.output["accreditation_status"] == "Not assessed"


def test_empty_curriculum():
    result = CurriculumAgent().run({"curriculum": []})

    assert not result.ok


def test_missing_topics():
    result = CurriculumAgent().run({
        "curriculum": [
            {"course": "Python Basics", "topics": []}
        ]
    })

    assert result.ok
    assert len(result.output["issues"]) == 1
