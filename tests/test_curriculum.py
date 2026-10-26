
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

def test_generate_curriculum():
    from rex.agents.curriculum import CurriculumAgent

    result = CurriculumAgent().run({
        "action": "generate",
        "course": "Python Basics",
        "level": "Beginner",
        "learning_outcomes": [
            "Understand variables",
            "Use loops",
            "Create functions"
        ],
        "duration_hours": 12
    })

    assert result.ok
    assert len(result.output["modules"]) == 3
    assert result.output["duration_hours"] == 12


def test_gap_analysis():
    from rex.agents.curriculum import CurriculumAgent

    result = CurriculumAgent().run({
        "action": "gap_analysis",
        "required_topics": ["Variables", "Loops", "Functions"],
        "curriculum": [
            {"course": "Python Basics", "topics": ["Variables", "Loops"]}
        ]
    })

    assert result.ok
    assert result.output["missing_topics"] == ["Functions"]
    assert result.output["coverage_percentage"] == 66.67


def test_generate_curriculum_requires_outcomes():
    from rex.agents.curriculum import CurriculumAgent

    result = CurriculumAgent().run({
        "action": "generate",
        "course": "Python Basics",
        "learning_outcomes": []
    })

    assert not result.ok
