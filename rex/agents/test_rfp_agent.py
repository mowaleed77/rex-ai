"""Run: python -m pytest -q   (from the folder that contains the agents/ package)"""
import json
from rex.agents.rfp import RfpAgent


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
    from rex.agents import groq_extractor

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


def test_arabic_country_and_arabic_indic_date_support():
    from rex.agents.rfp import _get_supported_country
    from rex.agents.rfp_sources import infer_country, parse_date

    assert _get_supported_country("القاهرة، مصر") == "Egypt"
    assert _get_supported_country("مصر") == "Egypt"
    assert _get_supported_country("الرياض - السعودية") == "Saudi Arabia"
    assert infer_country("مناقصة تدريب في القاهرة، مصر") == "Egypt"
    assert parse_date("١٥/١٢/٢٠٢٦").isoformat() == "2026-12-15"
    assert parse_date("۱۵/۱۲/۲۰۲۶").isoformat() == "2026-12-15"


def test_topic_is_propagated_to_discovery_queries():
    from rex.agents.rfp_search import search_rfps

    searcher = FakeSearch([])
    result = search_rfps(
        country="Egypt",
        topic="cybersecurity training",
        searcher=searcher,
    )
    assert result["ok"]
    assert searcher.calls
    assert all("cybersecurity training" in query for query, _ in searcher.calls)


def test_partial_search_errors_are_preserved():
    from rex.agents.rfp_search import search_rfps

    class PartiallyFailingSearch(FakeSearch):
        def search(self, query, include_domains=None, max_results=8):
            self.calls.append((query, include_domains))
            if len(self.calls) == 1:
                raise RuntimeError("temporary search outage")
            return [RESULTS[0]]

    result = search_rfps(
        country="Egypt",
        topic="education",
        searcher=PartiallyFailingSearch([]),
    )
    assert result["ok"] is True
    assert result["partial"] is True
    assert result["opportunities"]
    assert any("temporary search outage" in error for error in result["errors"])


def test_extractor_failure_is_reported_without_stopping_discovery():
    from rex.agents.rfp_sources import discover

    class BrokenExtractor:
        def __call__(self, text, url):
            raise RuntimeError("extractor unavailable")

    candidates, errors = discover(
        searcher=FakeSearch([RESULTS[0]]),
        countries=("Egypt",),
        extractor=BrokenExtractor(),
        max_results=1,
        topic="training",
    )
    assert candidates
    assert errors
    assert any("Extractor failed" in error for error in errors)
