"""Publisher tests - a fake HTTP client stands in for Facebook / Instagram / LinkedIn (no network)."""
from rex.agents.marketing import MarketingAgent
from rex.agents.orchestrator import Orchestrator
from rex.agents.publisher import PublishConfig, PublisherAgent, linkedin_escape

ENV = {"REX_PUBLISH_MODE": "live", "FB_PAGE_ID": "111", "FB_PAGE_ACCESS_TOKEN": "SECRET_FB",
       "IG_BUSINESS_ACCOUNT_ID": "222", "LINKEDIN_ACCESS_TOKEN": "SECRET_LI",
       "LINKEDIN_AUTHOR_URN": "urn:li:organization:5"}


class Resp:
    def __init__(self, status=200, data=None, headers=None):
        self.status_code, self._data, self.headers, self.text = status, data or {}, headers or {}, str(data)

    def json(self):
        return self._data


class FakeHttp:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail or {}

    def _hit(self, method, url, kw):
        self.calls.append((method, url, kw))
        for needle, resp in self.fail.items():
            if needle in url:
                return resp
        if url.endswith("/feed"):
            return Resp(data={"id": "111_999"})
        if url.endswith("/media"):
            return Resp(data={"id": "container1"})
        if url.endswith("/media_publish"):
            return Resp(data={"id": "ig_555"})
        if "container1" in url:
            return Resp(data={"status_code": "FINISHED"})
        if "linkedin.com" in url:
            return Resp(201, headers={"x-restli-id": "urn:li:share:77"})
        return Resp()

    def post(self, url, **kw):
        return self._hit("POST", url, kw)

    def get(self, url, **kw):
        return self._hit("GET", url, kw)


def approved_campaign(channels=("facebook", "instagram", "linkedin", "whatsapp")):
    c = MarketingAgent().run({"course": {"title": "Python Basics"}, "channels": list(channels)}).output
    c["status"], c["approved"] = "approved", True
    return c


def agent(http=None, env=None):
    return PublisherAgent(config=PublishConfig(ENV if env is None else env), http=http or FakeHttp(), sleep=lambda s: None)


def task(c, **extra):
    return {"campaign": c, "reviewer": "Admin", "role": "admin", **extra}


def test_blocks_unapproved_and_non_admin():
    c = MarketingAgent().run({"course": {"title": "Python Basics"}}).output   # pending approval
    assert not agent().run(task(c)).ok
    assert not agent().run({**task(approved_campaign()), "role": "user"}).ok


def test_default_mode_is_dry_run_and_sends_nothing():
    http = FakeHttp()
    res = agent(http, env={}).run(task(approved_campaign()))
    assert http.calls == []
    assert all(r["status"] in ("dry_run", "manual", "failed") for r in res.output["results"])
    assert res.output["campaign"]["published"] is False


def test_live_publish_facebook_and_linkedin():
    http, c = FakeHttp(), approved_campaign(("facebook", "linkedin"))
    res = agent(http).run(task(c))
    assert res.ok
    by = {r["key"]: r for r in res.output["results"]}
    assert by["facebook"]["status"] == "published" and by["facebook"]["url"].endswith("111_999")
    assert by["linkedin"]["id"] == "urn:li:share:77"
    out = res.output["campaign"]
    assert out["published"] is True and out["status"] == "published" and len(out["publish_log"]) == 2
    fb_call = next(k for m, u, k in http.calls if u.endswith("/feed"))
    assert fb_call["data"]["message"] == c["content"]["facebook"][0]["text"]
    li_call = next(k for m, u, k in http.calls if "linkedin.com" in u)
    assert li_call["headers"]["Linkedin-Version"] and li_call["json"]["author"] == "urn:li:organization:5"


def test_no_double_post_unless_forced():
    http, c = FakeHttp(), approved_campaign(("facebook",))
    first = agent(http).run(task(c)).output["campaign"]
    n = len(http.calls)
    again = agent(http).run(task(first))
    assert len(http.calls) == n and again.output["results"][0]["status"] == "skipped"
    assert agent(http).run(task(first, force=True)).output["results"][0]["status"] == "published"


def test_instagram_needs_image_then_two_step_publish():
    c = approved_campaign(("instagram",))
    assert agent().run(task(c)).output["results"][0]["status"] == "failed"
    http = FakeHttp()
    res = agent(http).run(task(c, image_url="https://example.com/a.jpg"))
    assert res.output["results"][0]["id"] == "ig_555"
    assert [u.rsplit("/", 1)[-1] for m, u, k in http.calls if m == "POST"] == ["media", "media_publish"]
    assert not agent().run(task(c, image_url="http://insecure/a.jpg")).ok


def test_failure_is_reported_and_token_never_leaks():
    err = Resp(400, {"error": {"message": "bad token SECRET_FB", "code": 190}})
    res = agent(FakeHttp(fail={"/feed": err})).run(task(approved_campaign(("facebook",))))
    r = res.output["results"][0]
    assert r["status"] == "failed" and "SECRET_FB" not in r["error"] and "190" in r["error"]
    assert res.output["campaign"]["published"] is False


def test_whatsapp_and_ads_are_manual_and_selection_picks_variation():
    c = approved_campaign(("whatsapp", "facebook_ad", "facebook"))
    http = FakeHttp()
    res = agent(http).run(task(c, selection={"facebook": 2}))
    by = {r["key"]: r for r in res.output["results"]}
    assert by["whatsapp"]["status"] == by["facebook_ad"]["status"] == "manual"
    sent = next(k for m, u, k in http.calls if u.endswith("/feed"))["data"]["message"]
    assert sent == c["content"]["facebook"][1]["text"]


def test_length_limit_and_linkedin_escaping():
    c = approved_campaign(("linkedin",))
    c["content"]["linkedin"][0]["text"] = "x" * 3001
    assert agent().run(task(c)).output["results"][0]["status"] == "failed"
    assert linkedin_escape("Python (basics) _fun_") == "Python \\(basics\\) \\_fun\\_"


def test_orchestrator_has_publisher_and_status():
    res = Orchestrator().dispatch("publisher", {"action": "status"})
    assert res.ok and "facebook" in res.output["channels"]
