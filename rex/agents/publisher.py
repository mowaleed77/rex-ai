"""Publisher Agent - posts an APPROVED marketing campaign to the real platforms.

The Marketing agent writes and the admin approves; this agent is the only code that talks to the outside world.

Safety rules (all enforced in code, not just in the UI):
  * only an admin can publish, and only a campaign whose status is approved / partially_published
  * REX_PUBLISH_MODE defaults to "dry": nothing is sent, you get the exact payloads that *would* be sent.
    Set REX_PUBLISH_MODE=live in .env to really post.
  * a channel that was already published is skipped (no double posts) unless task["force"] is true
  * every attempt (ok / failed / dry run) is appended to campaign["publish_log"]; tokens are never logged

Channels:
  facebook   Facebook Page post via the Graph API         FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN
  instagram  Instagram Business photo post (Graph API)   IG_BUSINESS_ACCOUNT_ID, FB_PAGE_ACCESS_TOKEN + a public https image_url
  linkedin   LinkedIn Page / member post (Posts API)      LINKEDIN_ACCESS_TOKEN, LINKEDIN_AUTHOR_URN
  email      e-mail to an opted-in list via SMTP          SMTP_* (same as the RFP digest) + REX_MARKETING_RECIPIENTS
Not automated: whatsapp (broadcast needs approved templates + opted-in numbers) and *_ad (paid ads need the
Marketing API, a budget and an ad account) - these are reported as "manual".

task:
  action     publish (default) | preview | status
  campaign   the approved campaign dict          reviewer / role   who is publishing (role must be "admin")
  selection  {content_key: variation_number}     which copy to post per channel (default: variation 1 of every key)
  channels   optional list of content keys to restrict the run
  image_url  public https URL of the image (required for Instagram)
  link       optional course URL appended to the text
  dry_run    True / False overrides REX_PUBLISH_MODE
  force      allow re-posting a channel that was already published
"""
from __future__ import annotations

import os
import time
from copy import deepcopy
from datetime import datetime, timezone
from email.message import EmailMessage

from .base import Agent, AgentResult

PUBLISHABLE = ("facebook", "instagram", "linkedin", "email")
MANUAL = {"whatsapp": "WhatsApp broadcasts need Meta-approved templates and opted-in numbers - send it manually or "
                      "through the WhatsApp Business app.",
          "instagram_ad": "Paid ads are created in Meta Ads Manager - copy the approved text there.",
          "facebook_ad": "Paid ads are created in Meta Ads Manager - copy the approved text there."}
LIMITS = {"facebook": 60000, "instagram": 2200, "linkedin": 3000}
PUBLISHED_STATES = ("approved", "partially_published", "published")


class PublishError(Exception):
    """A platform refused the post (message is safe to show: it never contains a token)."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _base(key: str) -> str:
    return key.split(":", 1)[0]


# ---------------------------------------------------------------------------------------- configuration
class PublishConfig:
    """Credentials and mode, read from the environment / .env."""

    def __init__(self, env: dict | None = None):
        if env is None:
            try:
                from rex.rag.llm import load_dotenv
                load_dotenv()
            except Exception:
                pass
            env = os.environ
        g = lambda k, d="": str(env.get(k, d) or "").strip()  # noqa: E731
        self.mode = g("REX_PUBLISH_MODE", "dry").lower()
        self.graph = f"https://graph.facebook.com/{g('GRAPH_API_VERSION', 'v25.0')}"
        self.fb_page_id, self.fb_token = g("FB_PAGE_ID"), g("FB_PAGE_ACCESS_TOKEN")
        self.ig_id = g("IG_BUSINESS_ACCOUNT_ID")
        self.li_token, self.li_author = g("LINKEDIN_ACCESS_TOKEN"), g("LINKEDIN_AUTHOR_URN")
        self.li_version = g("LINKEDIN_API_VERSION", "202607")
        self.recipients = g("REX_MARKETING_RECIPIENTS")
        self._smtp_host, self._smtp_from = g("SMTP_HOST"), g("SMTP_FROM") or g("SMTP_USER")

    @property
    def live(self) -> bool:
        return self.mode == "live"

    def missing(self, channel: str) -> list[str]:
        need = {"facebook": {"FB_PAGE_ID": self.fb_page_id, "FB_PAGE_ACCESS_TOKEN": self.fb_token},
                "instagram": {"IG_BUSINESS_ACCOUNT_ID": self.ig_id, "FB_PAGE_ACCESS_TOKEN": self.fb_token},
                "linkedin": {"LINKEDIN_ACCESS_TOKEN": self.li_token, "LINKEDIN_AUTHOR_URN": self.li_author},
                "email": {"SMTP_HOST": self._smtp_host, "SMTP_FROM": self._smtp_from,
                          "REX_MARKETING_RECIPIENTS": self.recipients}}.get(channel, {})
        return [name for name, value in need.items() if not value]

    def secrets(self) -> list[str]:
        return [s for s in (self.fb_token, self.li_token) if s]


# ---------------------------------------------------------------------------------------- platform calls
def _error_text(resp) -> str:
    try:
        data = resp.json()
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            return f"{err.get('message', '')} (code {err.get('code', '?')})".strip()
        if isinstance(data, dict) and data.get("message"):
            return str(data["message"])
    except Exception:
        pass
    return (getattr(resp, "text", "") or "")[:200]


def _check(resp) -> None:
    if resp.status_code >= 400:
        raise PublishError(f"HTTP {resp.status_code}: {_error_text(resp)}")


def post_facebook(cfg: PublishConfig, http, text: str, image_url: str = "") -> dict:
    if image_url:
        resp = http.post(f"{cfg.graph}/{cfg.fb_page_id}/photos", timeout=30,
                         data={"url": image_url, "caption": text, "access_token": cfg.fb_token})
    else:
        resp = http.post(f"{cfg.graph}/{cfg.fb_page_id}/feed", timeout=30,
                         data={"message": text, "access_token": cfg.fb_token})
    _check(resp)
    data = resp.json()
    post_id = data.get("post_id") or data.get("id") or ""
    return {"id": post_id, "url": f"https://www.facebook.com/{post_id}" if post_id else ""}


def post_instagram(cfg: PublishConfig, http, text: str, image_url: str, sleep=time.sleep) -> dict:
    created = http.post(f"{cfg.graph}/{cfg.ig_id}/media", timeout=30,
                        data={"image_url": image_url, "caption": text, "access_token": cfg.fb_token})
    _check(created)
    container = created.json().get("id")
    if not container:
        raise PublishError("Instagram did not return a media container id.")
    for _ in range(6):                      # wait until Instagram has fetched and processed the image
        status = http.get(f"{cfg.graph}/{container}", timeout=30,
                          params={"fields": "status_code", "access_token": cfg.fb_token})
        _check(status)
        code = status.json().get("status_code", "FINISHED")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise PublishError(f"Instagram could not process the image (status {code}).")
        sleep(3)
    else:
        raise PublishError("Instagram is still processing the image - try again in a minute.")
    published = http.post(f"{cfg.graph}/{cfg.ig_id}/media_publish", timeout=30,
                          data={"creation_id": container, "access_token": cfg.fb_token})
    _check(published)
    media_id = published.json().get("id", "")
    return {"id": media_id, "url": ""}


_LI_RESERVED = "\\|{}@[]()<>*_~"            # LinkedIn "little text" characters that must be escaped


def linkedin_escape(text: str) -> str:
    return "".join("\\" + ch if ch in _LI_RESERVED else ch for ch in text)


def post_linkedin(cfg: PublishConfig, http, text: str) -> dict:
    resp = http.post("https://api.linkedin.com/rest/posts", timeout=30, json={
        "author": cfg.li_author,
        "commentary": linkedin_escape(text),
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }, headers={"Authorization": f"Bearer {cfg.li_token}", "Linkedin-Version": cfg.li_version,
                "X-Restli-Protocol-Version": "2.0.0", "Content-Type": "application/json"})
    _check(resp)
    post_id = resp.headers.get("x-restli-id", "")
    return {"id": post_id, "url": f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else ""}


def send_email(cfg: PublishConfig, text: str, subject: str, transport=None) -> dict:
    from .rfp_email import EmailConfig, deliver, parse_recipients
    valid, invalid = parse_recipients(cfg.recipients)
    if not valid:
        raise PublishError("REX_MARKETING_RECIPIENTS has no valid e-mail address.")
    mail_cfg = EmailConfig.from_env()
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, mail_cfg.sender, mail_cfg.sender   # recipients stay hidden (bcc)
    msg.set_content(text)
    try:
        (transport or deliver)(mail_cfg, msg, valid)
    except Exception as error:
        raise PublishError(f"SMTP error: {error}") from error
    note = f" ({len(invalid)} invalid address(es) skipped)" if invalid else ""
    return {"id": f"{len(valid)} recipient(s){note}", "url": ""}


# ---------------------------------------------------------------------------------------- the agent
class PublisherAgent(Agent):
    name = "publisher"

    def __init__(self, config: PublishConfig | None = None, http=None, mail_transport=None, sleep=time.sleep):
        self._config, self._http, self._mail, self._sleep = config, http, mail_transport, sleep

    def config(self) -> PublishConfig:
        return self._config or PublishConfig()

    def http(self):
        if self._http is None:
            import requests
            self._http = requests
        return self._http

    # ------------------------------------------------------------------ dispatch
    def run(self, task: dict) -> AgentResult:
        action = task.get("action", "publish")
        if action == "status":
            return self.status()
        if action in ("publish", "preview"):
            return self.publish(task, force_dry=(action == "preview"))
        return AgentResult(self.name, False, message="Choose action: publish, preview or status.")

    def status(self) -> AgentResult:
        cfg = self.config()
        channels = {c: {"ready": not cfg.missing(c), "missing": cfg.missing(c)} for c in PUBLISHABLE}
        channels.update({c: {"ready": False, "manual": reason} for c, reason in MANUAL.items()})
        mode = "LIVE - posts are really sent" if cfg.live else "DRY RUN - nothing is sent (set REX_PUBLISH_MODE=live)"
        return AgentResult(self.name, True, output={"mode": cfg.mode, "live": cfg.live, "channels": channels},
                           message=mode)

    # ------------------------------------------------------------------ publish
    def publish(self, task: dict, force_dry: bool = False) -> AgentResult:
        campaign = task.get("campaign")
        if not isinstance(campaign, dict) or not isinstance(campaign.get("content"), dict):
            return AgentResult(self.name, False, message="Provide the approved campaign to publish.")
        if task.get("role") != "admin":
            return AgentResult(self.name, False, message="Only an admin can publish a campaign.")
        reviewer = str(task.get("reviewer") or "").strip()
        if not reviewer:
            return AgentResult(self.name, False, message="The publisher's name is required.")
        if not campaign.get("approved") or campaign.get("status") not in PUBLISHED_STATES:
            return AgentResult(self.name, False, message="Only an approved campaign can be published.")

        cfg = self.config()
        dry = True if force_dry else (bool(task["dry_run"]) if task.get("dry_run") is not None else not cfg.live)
        image_url = str(task.get("image_url") or "").strip()
        if image_url and not image_url.lower().startswith("https://"):
            return AgentResult(self.name, False, message="image_url must be a public https:// link.")
        link = str(task.get("link") or "").strip()
        selection = task.get("selection") or {}
        wanted = task.get("channels")
        keys = [k for k in campaign["content"] if not wanted or k in wanted]
        if not keys:
            return AgentResult(self.name, False, message="No matching channels in this campaign.")

        out = deepcopy(campaign)
        log = out.setdefault("publish_log", [])
        done = {e["key"] for e in log if e.get("status") == "published"}
        results = []
        for key in keys:
            results.append(self._one(cfg, out, key, selection.get(key, 1), image_url, link, dry, reviewer,
                                     done, bool(task.get("force"))))
        for r in results:
            if not r.pop("_log", True):
                continue
            log.append({**r, "by": reviewer, "at": _now()})
        live_ok = [r for r in results if r["status"] == "published"]
        if live_ok:
            out["published"] = True
            published_keys = {e["key"] for e in log if e.get("status") == "published"}
            publishable = [k for k in out["content"] if _base(k) in PUBLISHABLE]
            out["status"] = "published" if publishable and set(publishable) <= published_keys else "partially_published"

        ok = [r for r in results if r["status"] in ("published", "dry_run")]
        bad = [r for r in results if r["status"] == "failed"]
        mode = "DRY RUN" if dry else "LIVE"
        message = (f"[{mode}] {len(ok)} channel(s) {'previewed' if dry else 'published'}, {len(bad)} failed, "
                   f"{sum(r['status'] in ('manual', 'skipped') for r in results)} skipped/manual.")
        message = self._scrub(message, cfg)
        return AgentResult(self.name, bool(ok) or not bad, output={"campaign": out, "results": results, "mode": mode.lower()},
                           message=message)

    def _one(self, cfg, campaign, key, variation, image_url, link, dry, reviewer, done, force) -> dict:
        channel = _base(key)
        res = {"key": key, "channel": channel, "variation": variation, "status": "", "id": "", "url": "", "error": ""}
        if channel in MANUAL:
            return {**res, "status": "manual", "error": MANUAL[channel], "_log": False}
        if channel not in PUBLISHABLE:
            return {**res, "status": "skipped", "error": f"'{channel}' has no publisher.", "_log": False}
        if key in done and not force:
            return {**res, "status": "skipped", "error": "Already published (use force to post again).", "_log": False}
        items = campaign["content"][key]
        item = next((i for i in items if i.get("variation") == variation), None)
        if item is None:
            return {**res, "status": "failed", "error": f"Variation {variation} does not exist for {key}."}
        text = str(item.get("text") or "").strip()
        if link and link not in text:
            text = f"{text}\n\n{link}"
        if not text:
            return {**res, "status": "failed", "error": "The approved text is empty."}
        if channel in LIMITS and len(text) > LIMITS[channel]:
            return {**res, "status": "failed", "error": f"Text is {len(text)} characters; {channel} allows {LIMITS[channel]}."}
        if channel == "instagram" and not image_url:
            return {**res, "status": "failed", "error": "Instagram needs a public https image_url (text-only posts are not allowed)."}
        missing = cfg.missing(channel)
        if missing and not dry:
            return {**res, "status": "failed", "error": f"Missing in .env: {', '.join(missing)}"}
        if dry:
            note = f" (not configured yet: {', '.join(missing)})" if missing else ""
            return {**res, "status": "dry_run", "error": "", "preview": text[:200], "note": note.strip()}
        try:
            if channel == "facebook":
                info = post_facebook(cfg, self.http(), text, image_url)
            elif channel == "instagram":
                info = post_instagram(cfg, self.http(), text, image_url, sleep=self._sleep)
            elif channel == "linkedin":
                info = post_linkedin(cfg, self.http(), text)
            else:
                info = send_email(cfg, text, str(item.get("subject") or item.get("headline") or "Course announcement"),
                                  self._mail)
            return {**res, "status": "published", **info}
        except PublishError as error:
            return {**res, "status": "failed", "error": self._scrub(str(error), cfg)}
        except Exception as error:                      # network problems, bad JSON, ...
            return {**res, "status": "failed", "error": self._scrub(f"{type(error).__name__}: {error}", cfg)}

    @staticmethod
    def _scrub(text: str, cfg: PublishConfig) -> str:
        for secret in cfg.secrets():
            text = text.replace(secret, "***")
        return text
