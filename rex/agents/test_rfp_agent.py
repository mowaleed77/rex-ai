"""Run: python -m pytest -q   (from the folder that contains the agents/ package)"""
import json
from agents.rfp_agent import RfpAgent


class FakeSearch:
    """Mimics Tavily so tests need no internet or API key."""
    available = True

    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, query, include_domains=None, max_results=8):
        self.calls.append((query, include_domains))
        return self.results


RESULTS = [
    {"title": "Training services for IT staff - Ministry of Communications Egypt",
     "url": "https://etenders.gov.eg/t/1",
     "content": "Egypt tender for software training. Closing date: 15/12/2026. Published: 2026-10-20"},
    {"title": "Technical training framework - Saudi Electricity",
     "url": "https://etimad.sa/t/2",
     "content": "Skills development programme in Riyadh. Deadline: 20 January 2027"},
    {"title": "Teacher training tender - Department for Education, London",
     "url": "https://www.gov.uk/t/3",
     "content": "UK training services tender. Deadline: 2026-12-01"},
    {"title": "Old training RFP Egypt", "url": "https://example.eg/old",
     "content": "Egypt training. Deadline: 01/03/2026"},
    {"title": "Audit services Egypt", "url": "https://example.eg/audit",
     "content": "External audit and submit documents in Cairo. Deadline: 2026-12-30"},
    {"title": "Training RFP somewhere", "url": "https://example.com/x",
     "content": "Training tender. Deadline: 2026-12-30"},
]


def test_discovery_filters_everything_correctly(tmp_path):
    agent = RfpAgent(searcher=FakeSearch(RESULTS))
    res = agent.run({"discover": True, "today": "2026-10-29",
                     "store_path": str(tmp_path / "seen.json"),
                     "csv_path": str(tmp_path / "out.csv")})
    assert res.ok
    out = res.output
    titles = [o["title"] for o in out["opportunities"]]
    assert len(titles) == 2 and titles[0].startswith("Training services")  # Egypt first
    reasons = {r["title"]: r["reason"] for r in out["rejected"]}
    assert reasons["Teacher training tender - Department for Education, London"] == \
        "country not stated or not verifiable"
    assert reasons["Old training RFP Egypt"].startswith("expired")
    assert reasons["Audit services Egypt"] == "not education/training related"  # old 'it ' bug
    assert reasons["Training RFP somewhere"] == "country not stated or not verifiable"
    assert out["flagged_for_immediate_review"] and out["monitored_pipeline"]
    assert out["opportunities"][0]["deadline"] == "2026-12-15"  # dd/mm/yyyy parsed
    assert (tmp_path / "out.csv").exists()


def test_second_run_only_reports_new(tmp_path):
    store = str(tmp_path / "seen.json")
    alerts = []
    agent = RfpAgent(searcher=FakeSearch(RESULTS), notifier=alerts.append)
    agent.run({"discover": True, "today": "2026-10-29", "store_path": store})
    res2 = agent.run({"discover": True, "today": "2026-10-29", "store_path": store})
    assert res2.output["new_count"] == 0 and len(alerts) == 1


def test_missing_backend_is_a_clear_error():
    class NoKey:
        available = False
    res = RfpAgent(searcher=NoKey()).run({"discover": True})
    assert not res.ok and "TAVILY_API_KEY" in res.message


def test_manual_list_still_works_and_rejects_usa():
    res = RfpAgent(searcher=FakeSearch([])).run({
        "today": "2026-10-29",
        "opportunities": [
            {"title": "Corporate training", "country": "USA", "source_url": "https://a.com"},
            {"title": "Corporate training", "country": "Cairo, Egypt", "source_url": "https://b.eg"},
        ]})
    assert res.output["count"] == 1
    assert res.output["rejected"][0]["reason"] == "outside Egypt/Saudi Arabia"


def test_groq_extractor_parses_and_ignores_country(monkeypatch):
    from agents import groq_extractor

    class Resp:
        status_code = 200
        headers = {}
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": json.dumps({
                "organization": "Ministry of Communications", "deadline": "2026-12-15",
                "category": "IT training", "eligibility": "", "country": "France"})}}]}

    monkeypatch.setattr(groq_extractor.requests, "post", lambda *a, **k: Resp())
    ex = groq_extractor.GroqExtractor(api_key="test")
    assert ex("text", "u") == {"organization": "Ministry of Communications",
                               "deadline": "2026-12-15", "category": "IT training"}
    res = RfpAgent(searcher=FakeSearch(RESULTS), extractor=ex).run(
        {"discover": True, "today": "2026-10-29"})
    assert res.output["opportunities"][0]["organization"] == "Ministry of Communications"
    assert {o["country"] for o in res.output["opportunities"]} <= {"Egypt", "Saudi Arabia"}
