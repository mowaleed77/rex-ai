
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
