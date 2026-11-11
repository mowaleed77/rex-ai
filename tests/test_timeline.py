from rex.agents.orchestrator import Orchestrator
from rex.utils import timeline

EVENTS = [
    {"at": "10:00:00", "agent": "curriculum", "action": "generate", "ok": True, "message": "done", "ms": 12},
    {"at": "10:00:01", "agent": "document", "action": "curriculum_report", "ok": True, "message": "pdf", "ms": 30},
    {"at": "10:00:02", "agent": "document", "action": "course_description", "ok": False, "message": "<b>x</b>", "ms": 5},
]


def test_flow_collapses_repeats_and_starts_with_orchestrator():
    text = timeline.flow(EVENTS)
    assert text.count("Document Agent") == 1
    assert text.startswith("🧭 Orchestrator") and "Curriculum Agent" in text
    assert "المنسّق" in timeline.flow(EVENTS, arabic=True)


def test_summary_counts():
    s = timeline.summary(EVENTS)
    assert s == {"steps": 3, "failed": 1, "agents": 2, "total_ms": 47}


def test_html_is_escaped_and_marks_failures():
    html = timeline.timeline_html(EVENTS)
    assert "&lt;b&gt;x&lt;/b&gt;" in html and "<b>x</b>" not in html
    assert 'rex-tl-row bad' in html and 'rex-tl-row ok' in html
    assert timeline.timeline_html([]) == ""


def test_orchestrator_records_duration(tmp_path):
    orch = Orchestrator(docs_dir=tmp_path)
    orch.dispatch("curriculum", {"action": "generate", "course_title": "X", "level": "Beginner",
                                 "duration_hours": 10, "learning_outcomes": ["a", "b"]})
    assert orch.trace and isinstance(orch.trace[-1]["ms"], int)
