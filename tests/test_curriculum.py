
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


# ---- level-aware generation and optional LLM mode -------------------------------

def _gen(level, **extra):
    return CurriculumAgent(**extra.pop("agent_kwargs", {})).run({
        "action": "generate", "course": "Cybersecurity Essentials", "level": level,
        "duration_hours": 24, "learning_outcomes": ["Identify threats", "Secure a network"],
        **extra,
    })


def test_level_changes_content():
    beginner, advanced = _gen("Beginner"), _gen("Advanced")

    assert beginner.ok and advanced.ok
    assert beginner.output["modules"][0]["topics"] != advanced.output["modules"][0]["topics"]
    assert beginner.output["prerequisites"] != advanced.output["prerequisites"]
    assert beginner.output["assessments"] != advanced.output["assessments"]
    assert beginner.output["capstone"] != advanced.output["capstone"]
    # the outcome stays the first topic so gap_analysis can still match it
    assert beginner.output["modules"][0]["topics"][0] == "Identify threats"


def test_llm_mode_uses_llm_reply():
    import json
    reply = json.dumps({
        "objectives": ["Detect threats"], "prerequisites": "Networking basics",
        "modules": [
            {"topics": ["Malware types", "Phishing"], "exercise": "Phishing lab"},
            {"topics": ["Firewalls"], "exercise": "Firewall lab"},
        ],
        "assessments": ["Exam"], "capstone": "Secure a small network",
    })
    result = _gen("Intermediate", use_llm=True,
                  agent_kwargs={"llm": lambda messages: "```json\n" + reply + "\n```"})

    assert result.ok
    assert result.output["generated_by"] == "llm"
    assert result.output["modules"][0]["topics"][0] == "Identify threats"  # outcome re-added
    assert "Phishing" in result.output["modules"][0]["topics"]
    assert result.output["capstone"] == "Secure a small network"


def test_llm_mode_falls_back_on_bad_reply():
    for bad in ("not json", '{"modules": []}'):
        result = _gen("Beginner", use_llm=True, agent_kwargs={"llm": lambda m, b=bad: b})
        assert result.ok
        assert result.output["generated_by"] == "template"
        assert "template" in result.message


def test_llm_not_called_unless_requested():
    def boom(messages):
        raise AssertionError("LLM must not be called")

    assert _gen("Beginner", agent_kwargs={"llm": boom}).ok
