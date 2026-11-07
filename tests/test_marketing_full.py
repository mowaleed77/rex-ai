"""Marketing agent: channels, languages, grounding in course data, approval workflow."""
from rex.agents.marketing import CHANNELS, MarketingAgent
from rex.utils import catalog as cat


def _course():
    return cat.marketing_view(cat.find_course("Python for Data Analysis"))


def test_all_channels_and_variations():
    res = MarketingAgent().run({"course": _course(), "channels": CHANNELS, "variations": 3})
    assert res.ok
    assert set(res.output["content"]) == set(CHANNELS)
    for items in res.output["content"].values():
        assert [i["variation"] for i in items] == [1, 2, 3]
        assert all(i["text"] and i["headline"] and i["call_to_action"] for i in items)
    assert res.output["content"]["email"][0]["subject"]
    # the three variations of one channel are genuinely different
    texts = {i["text"] for i in res.output["content"]["instagram"]}
    assert len(texts) == 3


def test_course_facts_are_used_and_price_is_formatted():
    res = MarketingAgent().run({"course": _course(), "channels": ["whatsapp"]})
    text = res.output["content"]["whatsapp"][0]["text"]
    assert "EGP 4,500" in text and "40 training hours" in text and "15% off" in text


def test_arabic_and_both_languages():
    ar = MarketingAgent().run({"course": _course(), "language": "ar", "channels": ["linkedin"]})
    assert "بايثون لتحليل البيانات" in ar.output["content"]["linkedin"][0]["text"]
    both = MarketingAgent().run({"course": _course(), "language": "both", "channels": ["email"]})
    assert set(both.output["content"]) == {"email:en", "email:ar"}
    assert both.output["content"]["email:ar"][0]["language"] == "ar"


def test_nothing_is_invented_when_facts_are_missing():
    res = MarketingAgent().run({"course": {"title": "Brand New Course"}, "channels": ["facebook"]})
    text = res.output["content"]["facebook"][0]["text"]
    assert "Price" not in text and "Offer" not in text and "Duration" not in text
    assert any("No price" in w for w in res.output["warnings"])


def test_invalid_input_is_reported():
    agent = MarketingAgent()
    assert not agent.run({"course": {}}).ok
    assert not agent.run({"course": {"title": "X"}, "language": "fr"}).ok
    assert not agent.run({"course": {"title": "X"}, "channels": ["tiktok"]}).ok
    assert not agent.run({"action": "launch"}).ok


def test_llm_copy_is_fact_checked():
    def llm(messages):
        return ('[{"headline":"Win","text":"Guaranteed 99% job rate, officially accredited."},'
                '{"headline":"Good","text":"Learn Python in 40 training hours. Reply to this message to register."}]')
    res = MarketingAgent(llm=llm).run({"course": _course(), "channels": ["whatsapp"], "use_llm": True})
    first, second = res.output["content"]["whatsapp"]
    assert first.get("written_by") != "llm" and "99" not in first["text"]   # rejected: invented number + accreditation
    assert second["written_by"] == "llm"
    assert res.output["generated_by"] == "llm"


def test_llm_failure_falls_back_to_templates():
    def broken(messages):
        raise RuntimeError("offline")
    res = MarketingAgent(llm=broken).run({"course": _course(), "channels": ["email"], "use_llm": True})
    assert res.ok and res.output["generated_by"] == "template" and "template" in res.message


def test_approval_workflow_never_publishes():
    agent = MarketingAgent()
    campaign = agent.run({"course": _course(), "channels": ["instagram"]}).output
    assert campaign["status"] == "pending_admin_approval" and not campaign["approved"] and not campaign["published"]

    assert not agent.run({"action": "approve", "campaign": campaign}).ok                 # reviewer required
    assert not agent.run({"action": "reject", "campaign": campaign, "reviewer": "A"}).ok  # note required
    assert not agent.run({"action": "request_changes", "campaign": campaign, "reviewer": "A"}).ok

    approved = agent.run({"action": "approve", "campaign": campaign, "reviewer": "Admin"}).output
    assert approved["status"] == "approved" and approved["approved"] and approved["published"] is False
    assert campaign["status"] == "pending_admin_approval"                                # caller's copy untouched
    assert approved["history"][-1]["by"] == "Admin"

    changes = agent.run({"action": "request_changes", "campaign": campaign, "reviewer": "A", "note": "shorter"})
    assert changes.output["status"] == "changes_requested" and not changes.output["approved"]


def test_strategy_and_export():
    res = MarketingAgent().run({"course": _course(), "channels": ["instagram", "facebook_ad"], "budget": "EGP 2,000",
                                "objective": "enrollment"})
    strategy = res.output["campaign_strategy"]
    assert strategy["goal"].startswith("Drive registrations")
    assert len(strategy["posting_calendar_7_days"]) == 7 and strategy["kpis"] and strategy["key_messages"]
    assert "facebook_ad" in strategy["budget_note"]
    out = MarketingAgent().run({"action": "export", "campaign": res.output}).output
    assert "Instagram caption" in out["markdown"] and "CAMPAIGN" in out["text"]
