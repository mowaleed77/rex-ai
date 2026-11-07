"""RFP e-mail digest: Egypt first, validation, preview vs send, no-SMTP fallback."""
from email import message_from_bytes

import pytest

from rex.agents.rfp_email import EmailConfig, RfpEmailAgent, build_digest, parse_recipients

ITEMS = [
    {"title": "Saudi Learning Tender", "country": "Saudi Arabia", "organization": "HRDF", "deadline": "2030-11-20",
     "days_left": 100, "source_url": "https://example.com/sa", "is_new": True},
    {"title": "Egypt IT Training", "country": "Egypt", "organization": "MCIT", "deadline": "2030-12-01",
     "days_left": 120, "source_url": "https://example.com/eg", "is_new": True},
]


def test_egypt_is_listed_before_saudi_and_flagged_in_the_subject():
    d = build_digest(ITEMS)
    assert "[Action needed]" in d["subject"]
    assert d["text"].index("Egypt IT Training") < d["text"].index("Saudi Learning Tender")
    assert d["egypt_count"] == 1 and d["saudi_count"] == 1


def test_arabic_digest_is_right_to_left():
    d = build_digest(ITEMS, "ar")
    assert 'dir="rtl"' in d["html"] and "مصر" in d["text"]


def test_html_is_escaped_and_unsafe_links_are_dropped():
    evil = [{"title": "<script>alert(1)</script>", "country": "Egypt", "source_url": "javascript:alert(1)"}]
    html = build_digest(evil)["html"]
    assert "<script>" not in html and "javascript:" not in html


def test_recipient_parsing():
    ok, bad = parse_recipients("a@x.com; b@y.org, nope, a@x.com")
    assert ok == ["a@x.com", "b@y.org"] and bad == ["nope"]


def test_preview_never_sends():
    sent = []
    agent = RfpEmailAgent(config=EmailConfig(host="smtp.test", sender="rex@test.com"),
                          transport=lambda *a: sent.append(a))
    res = agent.run({"opportunities": ITEMS, "recipients": "a@x.com", "send": False})
    assert res.ok and res.output["status"] == "previewed" and not sent


def test_send_uses_transport_with_a_proper_message():
    sent = []
    agent = RfpEmailAgent(config=EmailConfig(host="smtp.test", sender="rex@test.com"),
                          transport=lambda cfg, msg, rcpts: sent.append((msg, rcpts)))
    res = agent.run({"opportunities": ITEMS, "recipients": ["a@x.com", "b@x.com"], "send": True})
    assert res.ok and res.output["status"] == "sent"
    msg, rcpts = sent[0]
    assert rcpts == ["a@x.com", "b@x.com"] and msg["From"] == "rex@test.com"
    assert msg.get_body(preferencelist=("html",)) is not None


def test_failed_send_is_reported_not_raised():
    def refuse(*a):
        raise ConnectionRefusedError("no route")
    agent = RfpEmailAgent(config=EmailConfig(host="smtp.test", sender="rex@test.com"), transport=refuse)
    res = agent.run({"opportunities": ITEMS, "recipients": "a@x.com", "send": True})
    assert not res.ok and res.output["status"] == "failed" and "ConnectionRefusedError" in res.message


def test_without_smtp_the_email_is_saved_as_eml(tmp_path):
    agent = RfpEmailAgent(config=EmailConfig())
    res = agent.run({"opportunities": ITEMS, "recipients": "a@x.com", "send": True, "outbox_dir": str(tmp_path)})
    assert res.ok and res.output["status"] == "saved_to_outbox"
    eml = message_from_bytes(open(res.output["eml_path"], "rb").read())
    assert eml["To"] == "a@x.com" and "Egypt" in eml["Subject"]


def test_validation_errors():
    agent = RfpEmailAgent(config=EmailConfig())
    assert not agent.run({"opportunities": ITEMS, "recipients": "bad-address", "send": True}).ok
    assert not agent.run({"opportunities": ITEMS, "recipients": "", "send": True}).ok
    assert not agent.run({"opportunities": []}).ok
    assert not agent.run({}).ok


def test_only_supported_countries_are_ever_emailed():
    items = ITEMS + [{"title": "US Tender", "country": "United States", "source_url": "https://example.com/us"}]
    res = RfpEmailAgent(config=EmailConfig()).run({"opportunities": items, "recipients": "a@x.com"})
    assert "US Tender" not in res.output["text"]
