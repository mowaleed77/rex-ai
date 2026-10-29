from rex.agents.rfp import RfpAgent
from rex.agents.orchestrator import Orchestrator


def test_rfp_accepts_egypt_and_saudi_arabia():
    result = RfpAgent().run({
        "opportunities": [
            {
                "title": "Egypt Training RFP",
                "country": "Egypt",
                "source_url": "https://example.com/egypt"
            },
            {
                "title": "Saudi Training RFP",
                "country": "Saudi Arabia",
                "source_url": "https://example.com/saudi"
            }
        ]
    })

    assert result.ok
    assert result.output["count"] == 2


def test_rfp_excludes_unsupported_countries():
    result = RfpAgent().run({
        "opportunities": [
            {
                "title": "Other Country RFP",
                "country": "United States",
                "source_url": "https://example.com/other"
            }
        ]
    })

    assert result.ok
    assert result.output["count"] == 0


def test_rfp_skips_missing_title_or_source():
    result = RfpAgent().run({
        "opportunities": [
            {"country": "Egypt", "source_url": "https://example.com/1"},
            {"title": "Missing source", "country": "Egypt"}
        ]
    })

    assert result.output["count"] == 0


def test_rfp_tracks_sources_and_verification_status():
    result = RfpAgent().run({
        "opportunities": [
            {
                "title": "Training RFP",
                "country": "Egypt",
                "source_url": "https://example.com/rfp",
                "deadline": "2026-11-30"
            }
        ]
    })

    opportunity = result.output["opportunities"][0]

    assert result.sources == ["https://example.com/rfp"]
    assert opportunity["status"] == "requires_verification"
    assert opportunity["deadline"] == "2026-11-30"


def test_rfp_rejects_non_list_input():
    result = RfpAgent().run({"opportunities": "invalid"})

    assert not result.ok


def test_orchestrator_uses_rfp_agent():
    result = Orchestrator().dispatch("rfp_research", {
        "opportunities": [
            {
                "title": "Training RFP",
                "country": "Egypt",
                "source_url": "https://example.com/rfp"
            }
        ]
    })

    assert result.ok
    assert result.agent == "rfp_research"


# ---- Sprint 2 upgrade tests ----
TODAY = "2026-10-26"


def _opp(**kw):
    base = {"title": "Training Program", "country": "Egypt",
            "source_url": "https://example.com/a", "organization": "Ministry X"}
    base.update(kw)
    return base


def test_rfp_rejects_expired():
    r = RfpAgent().run({"today": TODAY, "opportunities": [_opp(deadline="2026-10-01")]})
    assert r.output["count"] == 0
    assert "expired" in r.output["rejected"][0]["reason"]


def test_rfp_detects_duplicates():
    r = RfpAgent().run({"today": TODAY, "opportunities": [
        _opp(), _opp(source_url="https://example.com/b")]})  # same title+issuer+country
    assert r.output["count"] == 1
    assert r.output["rejected"][0]["reason"] == "duplicate"


def test_rfp_filters_unrelated_topics():
    r = RfpAgent().run({"today": TODAY, "opportunities": [_opp(title="Road construction tender")]})
    assert r.output["count"] == 0


def test_rfp_routes_egypt_vs_saudi():
    r = RfpAgent().run({"today": TODAY, "opportunities": [
        _opp(title="Saudi Training", country="KSA", source_url="https://example.com/s"),
        _opp(title="Egypt Training", source_url="https://example.com/e")]})
    routes = {o["country"]: o["review_route"] for o in r.output["opportunities"]}
    assert routes == {"Egypt": "flag_for_immediate_review", "Saudi Arabia": "monitored_pipeline"}
    assert r.output["opportunities"][0]["country"] == "Egypt"   # Egypt listed first


def test_rfp_exports_csv(tmp_path):
    p = tmp_path / "rfps.csv"
    RfpAgent().run({"today": TODAY, "csv_path": str(p), "opportunities": [_opp()]})
    assert "Training Program" in p.read_text(encoding="utf-8-sig")