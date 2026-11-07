"""The orchestrator understands a request, calls the right agents in order and passes data between them."""
from pathlib import Path

import pytest

from rex.agents.orchestrator import Orchestrator, detect_intent


@pytest.fixture
def orch(tmp_path):
    return Orchestrator(docs_dir=tmp_path / "docs")


@pytest.mark.parametrize("text,intent", [
    ("launch the Excel for Business Analysis course", "course_launch"),
    ("make a curriculum and a campaign for Cybersecurity Essentials", "course_launch"),
    ("write an instagram campaign for Digital Marketing Fundamentals", "campaign"),
    ("create a curriculum for Python for Data Analysis", "curriculum"),
    ("generate a PDF for Python for Data Analysis", "documents"),
    ("find training tenders in Egypt", "rfp"),
    ("أطلق دورة أساسيات تعلم الآلة", "course_launch"),
    ("ابحث عن مناقصات تدريب في السعودية", "rfp"),
    ("what is the price of the python course", "chat"),
])
def test_intent_detection(text, intent):
    assert detect_intent(text) == intent


def test_launch_stops_for_human_approval_before_marketing(orch):
    res = orch.handle("Launch the Excel for Business Analysis course")
    assert res.ok and res.awaiting == "curriculum_approval"
    assert "campaign" not in res.artifacts                           # marketing has NOT run yet
    assert [s["agent"] for s in res.steps] == ["curriculum", "document", "document"]
    assert res.artifacts["curriculum"]["status_code"] == "draft"
    assert all(Path(p).is_file() for p in res.artifacts["pdfs"].values())


def test_launch_continues_after_a_human_approves(orch):
    first = orch.handle("Launch the Excel for Business Analysis course")
    done = orch.handle("Launch the Excel for Business Analysis course", first.context, approved_by="Dr. Sara")
    assert done.ok and done.awaiting == "campaign_review"
    assert [s["agent"] for s in done.steps][0] == "curriculum"
    assert done.steps[-1]["agent"] == "marketing"
    camp = done.artifacts["campaign"]
    assert camp["status"] == "pending_admin_approval" and camp["published"] is False   # orchestrator never approves it
    assert done.artifacts["curriculum"]["approved_by"] == "Dr. Sara"
    # the campaign was written from the approved curriculum's facts
    assert any("24 training hours" in i["text"] for items in camp["content"].values() for i in items)


def test_arabic_request_gives_arabic_documents_and_copy(orch):
    res = orch.handle("أطلق دورة أساسيات تعلم الآلة بالعربي", approved_by="admin")
    assert res.ok and res.artifacts["curriculum"]["language"] == "ar"
    assert "أساسيات تعلم الآلة" in res.artifacts["campaign"]["content"]["instagram"][0]["text"]
    assert all(Path(p).is_file() for p in res.artifacts["pdfs"].values())


def test_unknown_course_asks_for_what_is_missing(orch):
    res = orch.handle("create a curriculum for the course 'Underwater Basket Weaving'")
    assert not res.ok and "learning_outcomes" in res.needs_input


def test_campaign_workflow_alone(orch):
    res = orch.handle("write a linkedin and whatsapp campaign for Digital Marketing Fundamentals")
    assert res.ok and res.awaiting == "campaign_review"
    assert set(res.artifacts["campaign"]["content"]) == {"linkedin", "whatsapp"}


def test_rfp_workflow_filters_countries_and_previews_email(orch):
    items = [
        {"title": "IT Training Program", "country": "Egypt", "organization": "MCIT",
         "deadline": "2030-12-20", "source_url": "https://example.com/eg"},
        {"title": "Corporate Learning Services", "country": "KSA", "deadline": "2030-11-20",
         "source_url": "https://example.com/sa"},
        {"title": "Training Tender", "country": "United States", "source_url": "https://example.com/us"},
    ]
    res = orch.handle("find training tenders and email them to team@academy.com", discover=False,
                      opportunities=items)
    assert res.ok
    rfp = res.artifacts["rfp"]
    assert rfp["count"] == 2 and rfp["rejected_count"] == 1
    assert rfp["flagged_for_immediate_review"] == ["IT Training Program"]
    assert res.artifacts["email"]["status"] == "previewed"          # not sent without explicit confirmation


def test_every_step_is_traced_and_reported_to_the_hook(tmp_path):
    seen = []
    o = Orchestrator(docs_dir=tmp_path, on_event=seen.append)
    o.handle("create a curriculum for Python for Data Analysis")
    assert seen and {e["agent"] for e in seen} >= {"curriculum", "document"}
    assert o.trace == seen


def test_a_failing_agent_does_not_crash_the_workflow(orch):
    class Boom:
        name = "marketing"
        def run(self, task):
            raise RuntimeError("boom")
    orch.register(Boom())
    res = orch.handle("write a campaign for Python for Data Analysis")
    assert not res.ok and "boom" in res.message


def test_empty_request_and_help(orch):
    assert not orch.handle("   ").ok
    assert orch.handle("what can you do?").intent == "help"
