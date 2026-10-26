
from rex.agents.marketing import MarketingAgent
from rex.agents.orchestrator import Orchestrator


def test_marketing_generates_content():
    result = MarketingAgent().run({
        "course": {"title": "Python Basics"},
        "channels": ["instagram", "linkedin"],
        "variations": 2
    })

    assert result.ok
    assert "instagram" in result.output["content"]
    assert "linkedin" in result.output["content"]
    assert len(result.output["content"]["instagram"]) == 2


def test_marketing_requires_course_title():
    result = MarketingAgent().run({"course": {}})

    assert not result.ok
    assert "title is required" in result.message


def test_marketing_requires_admin_approval():
    result = MarketingAgent().run({
        "course": {"title": "Python Basics"}
    })

    assert result.output["status"] == "pending_admin_approval"
    assert result.output["approved"] is False
    assert result.output["published"] is False


def test_marketing_does_not_invent_price():
    result = MarketingAgent().run({
        "course": {"title": "Python Basics"},
        "channels": ["instagram"]
    })

    text = result.output["content"]["instagram"][0]["text"]

    assert "Price:" not in text
    assert "Offer:" not in text


def test_orchestrator_uses_marketing_agent():
    result = Orchestrator().dispatch("marketing", {
        "course": {"title": "Python Basics"},
        "channels": ["whatsapp"]
    })

    assert result.ok
    assert result.agent == "marketing"
