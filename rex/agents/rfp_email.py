"""RFP e-mail digest: turns the RFP agent's results into a clear alert e-mail (plain text + HTML).

Egypt opportunities are listed first as "immediate review"; Saudi Arabia ones follow as the
"monitored pipeline" (the business rule of the RFP agent).

Task keys:
    rfp_result   : dict        the RFP agent's `output` (or pass `opportunities` directly)
    opportunities: list[dict]
    recipients   : list[str] | "a@x.com, b@y.com"   (falls back to REX_RFP_RECIPIENTS)
    send         : bool        False (default) = preview only; True = send through SMTP
    only_new     : bool        include only opportunities flagged is_new
    language     : "en" | "ar"
    outbox_dir   : str         where .eml copies go when SMTP is not configured

SMTP settings come from the environment / .env:
    SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_SECURITY (starttls | ssl | none)
If SMTP_HOST is missing, "send" saves a ready-to-open .eml file in generated_docs/outbox/ instead,
so the demo works without an e-mail account.
"""
from __future__ import annotations

import os
import re
import smtplib
import ssl
from dataclasses import dataclass
from datetime import date, datetime
from email.message import EmailMessage
from html import escape
from pathlib import Path

from .base import Agent, AgentResult

_EMAIL_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
ROOT = Path(__file__).resolve().parents[2]

TEXT = {
    "en": {
        "subject_urgent": "[Action needed] {n} Egypt RFP(s) for immediate review - {total} opportunities in total",
        "subject": "RFP digest: {total} education & training opportunities",
        "intro": "REX AI found {total} relevant education and training opportunities ({new} new).",
        "egypt": "Egypt - flagged for immediate review",
        "saudi": "Saudi Arabia - monitored pipeline",
        "none": "None in this run.",
        "deadline": "Deadline", "days": "{n} days left", "no_deadline": "not stated",
        "org": "Issuer", "category": "Category", "eligibility": "Eligibility", "link": "Source",
        "new": "NEW", "disclaimer": "Please verify every opportunity and its eligibility requirements against "
                                    "the original source before acting. This e-mail was generated automatically.",
        "dir": "ltr",
    },
    "ar": {
        "subject_urgent": "[مطلوب إجراء] {n} من مناقصات مصر تحتاج مراجعة فورية - إجمالي الفرص {total}",
        "subject": "ملخص المناقصات: {total} فرصة تعليمية وتدريبية",
        "intro": "عثر REX AI على {total} فرصة تعليمية وتدريبية ذات صلة ({new} جديدة).",
        "egypt": "مصر - للمراجعة الفورية",
        "saudi": "المملكة العربية السعودية - ضمن المتابعة",
        "none": "لا توجد فرص في هذه المرة.",
        "deadline": "الموعد النهائي", "days": "متبقٍ {n} يوماً", "no_deadline": "غير محدد",
        "org": "الجهة", "category": "التصنيف", "eligibility": "شروط الأهلية", "link": "المصدر",
        "new": "جديد", "disclaimer": "يرجى التحقق من كل فرصة وشروط أهليتها من المصدر الأصلي قبل اتخاذ أي إجراء. "
                                    "أُنشئت هذه الرسالة تلقائياً.",
        "dir": "rtl",
    },
}


@dataclass
class EmailConfig:
    host: str = ""
    port: int = 587
    user: str = ""
    password: str = ""
    sender: str = ""
    security: str = "starttls"

    @classmethod
    def from_env(cls) -> "EmailConfig":
        try:
            from rex.rag.llm import load_dotenv
            load_dotenv()
        except Exception:
            pass
        env = os.environ
        try:
            port = int(env.get("SMTP_PORT", "587"))
        except ValueError:
            port = 587
        user = env.get("SMTP_USER", "")
        return cls(env.get("SMTP_HOST", ""), port, user, env.get("SMTP_PASSWORD", ""),
                   env.get("SMTP_FROM", user), env.get("SMTP_SECURITY", "starttls").lower())

    @property
    def configured(self) -> bool:
        return bool(self.host and self.sender)


def parse_recipients(value) -> tuple[list[str], list[str]]:
    """Return (valid, invalid) addresses from a list or a comma / semicolon separated string."""
    items = value if isinstance(value, (list, tuple)) else re.split(r"[,;\s]+", str(value or ""))
    valid, invalid = [], []
    for item in items:
        item = str(item).strip()
        if not item:
            continue
        (valid if _EMAIL_RE.match(item) else invalid).append(item)
    return list(dict.fromkeys(valid)), invalid


def _safe_link(url: str) -> str:
    url = str(url or "").strip()
    return url if url.lower().startswith(("http://", "https://")) else ""


def build_digest(opportunities: list[dict], lang: str = "en", today: date | None = None) -> dict:
    """Subject, plain text and HTML bodies for a list of accepted RFP opportunities."""
    lang = lang if lang in TEXT else "en"
    t = TEXT[lang]
    egypt = [o for o in opportunities if o.get("country") == "Egypt"]
    saudi = [o for o in opportunities if o.get("country") == "Saudi Arabia"]
    total, new = len(egypt) + len(saudi), sum(1 for o in egypt + saudi if o.get("is_new"))
    subject = (t["subject_urgent"] if egypt else t["subject"]).format(n=len(egypt), total=total)

    def deadline_text(o):
        base = o.get("deadline") or t["no_deadline"]
        if o.get("days_left") is not None:
            base += f" ({t['days'].format(n=o['days_left'])})"
        return base

    text = [t["intro"].format(total=total, new=new), ""]
    html = [f'<div dir="{t["dir"]}" style="font-family:Segoe UI,Arial,sans-serif;max-width:680px;color:#1f2937">',
            '<div style="background:#1F3A5F;color:#fff;padding:14px 18px;border-radius:8px 8px 0 0">'
            '<strong>REX AI</strong> &middot; RFP &amp; Tender Research</div>',
            f'<p style="margin:16px 0">{escape(t["intro"].format(total=total, new=new))}</p>']
    for heading, group, color in ((t["egypt"], egypt, "#B91C1C"), (t["saudi"], saudi, "#1F3A5F")):
        text += [heading.upper(), "=" * len(heading)]
        html.append(f'<h3 style="color:{color};border-bottom:2px solid {color};padding-bottom:4px">'
                    f'{escape(heading)} ({len(group)})</h3>')
        if not group:
            text += [t["none"], ""]
            html.append(f'<p style="color:#6b7280">{escape(t["none"])}</p>')
            continue
        for o in group:
            flag = f" [{t['new']}]" if o.get("is_new") else ""
            text.append(f"* {o.get('title', '')}{flag}")
            rows = [(t["org"], o.get("organization")), (t["deadline"], deadline_text(o)),
                    (t["category"], o.get("category")), (t["eligibility"], o.get("eligibility"))]
            link = _safe_link(o.get("source_url"))
            html.append('<div style="border:1px solid #d1d5db;border-radius:8px;padding:10px 14px;margin:10px 0">'
                        f'<strong>{escape(str(o.get("title", "")))}</strong>'
                        + (f' <span style="background:#DCFCE7;color:#166534;border-radius:10px;padding:1px 8px;'
                           f'font-size:12px">{escape(t["new"])}</span>' if o.get("is_new") else ""))
            if o.get("summary"):
                html.append(f'<div style="margin:4px 0;color:#374151">{escape(str(o["summary"]))}</div>')
            for label, value in rows:
                if value:
                    text.append(f"    {label}: {value}")
                    html.append(f'<div style="font-size:14px"><span style="color:#6b7280">{escape(label)}:</span> '
                                f'{escape(str(value))}</div>')
            if link:
                text.append(f"    {t['link']}: {link}")
                html.append(f'<div style="font-size:14px"><a href="{escape(link, quote=True)}">'
                            f'{escape(t["link"])}</a></div>')
            html.append("</div>")
            text.append("")
    text += [t["disclaimer"]]
    html.append(f'<p style="color:#6b7280;font-size:12px;margin-top:20px">{escape(t["disclaimer"])}</p></div>')
    return {"subject": subject, "text": "\n".join(text), "html": "\n".join(html),
            "egypt_count": len(egypt), "saudi_count": len(saudi), "new_count": new}


def make_message(cfg: EmailConfig, recipients: list[str], digest: dict, attachment: Path | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = " ".join(digest["subject"].split())          # no line breaks in headers
    msg["From"] = cfg.sender or "rex-ai@localhost"
    msg["To"] = ", ".join(recipients)
    msg.set_content(digest["text"])
    msg.add_alternative(digest["html"], subtype="html")
    if attachment and attachment.is_file():
        msg.add_attachment(attachment.read_bytes(), maintype="text", subtype="csv", filename=attachment.name)
    return msg


def deliver(cfg: EmailConfig, msg: EmailMessage, recipients: list[str]) -> None:
    context = ssl.create_default_context()
    if cfg.security == "ssl":
        server = smtplib.SMTP_SSL(cfg.host, cfg.port, context=context, timeout=30)
    else:
        server = smtplib.SMTP(cfg.host, cfg.port, timeout=30)
    with server:
        if cfg.security == "starttls":
            server.starttls(context=context)
        if cfg.user:
            server.login(cfg.user, cfg.password)
        server.send_message(msg, to_addrs=recipients)


class RfpEmailAgent(Agent):
    name = "rfp_email"

    def __init__(self, config: EmailConfig | None = None, transport=None):
        self._config = config
        self._transport = transport or deliver   # tests can replace the real SMTP call

    @property
    def config(self) -> EmailConfig:
        if self._config is None:
            self._config = EmailConfig.from_env()
        return self._config

    def run(self, task: dict) -> AgentResult:
        result = task.get("rfp_result")
        opportunities = (result or {}).get("opportunities") if isinstance(result, dict) else None
        if opportunities is None:
            opportunities = task.get("opportunities")
        if not isinstance(opportunities, list):
            return AgentResult(self.name, False, message="Provide `rfp_result` or `opportunities` from the RFP agent.")
        # defence in depth: the e-mail only ever lists the two supported countries
        opportunities = [o for o in opportunities if isinstance(o, dict)
                         and o.get("country") in ("Egypt", "Saudi Arabia")]
        if task.get("only_new"):
            opportunities = [o for o in opportunities if o.get("is_new")]
        if not opportunities:
            return AgentResult(self.name, False, message="There are no opportunities to e-mail.")

        digest = build_digest(opportunities, str(task.get("language", "en")).lower())
        raw = task.get("recipients") or os.environ.get("REX_RFP_RECIPIENTS", "")
        recipients, invalid = parse_recipients(raw)
        output = {**digest, "recipients": recipients, "invalid_recipients": invalid, "status": "previewed"}
        sources = [o.get("source_url", "") for o in opportunities if o.get("source_url")]

        if invalid:
            return AgentResult(self.name, False, output=output,
                               message="Invalid e-mail address: " + ", ".join(invalid))
        if not task.get("send"):
            return AgentResult(self.name, True, output=output, sources=sources,
                               message="E-mail preview ready. Nothing was sent.")
        if not recipients:
            return AgentResult(self.name, False, output=output, message="Add at least one recipient.")

        cfg = self.config
        attachment = Path(task["attach_csv"]) if task.get("attach_csv") else None
        try:
            message = make_message(cfg, recipients, digest, attachment)
        except ValueError as error:
            return AgentResult(self.name, False, output=output, message=f"Could not build the e-mail: {error}")

        if not cfg.configured:
            outbox = Path(task.get("outbox_dir") or ROOT / "generated_docs" / "outbox")
            outbox.mkdir(parents=True, exist_ok=True)
            path = outbox / f"rfp_digest_{datetime.now().strftime('%Y%m%d-%H%M%S')}.eml"
            path.write_bytes(bytes(message))
            output.update({"status": "saved_to_outbox", "eml_path": str(path.resolve())})
            return AgentResult(
                self.name, True, output=output, sources=sources,
                message="SMTP is not configured (set SMTP_HOST / SMTP_FROM in .env), so the e-mail was saved "
                        f"to {path.name} instead of being sent.")
        try:
            self._transport(cfg, message, recipients)
        except Exception as error:   # network, auth, refused recipients ...
            output["status"] = "failed"
            return AgentResult(self.name, False, output=output,
                               message=f"E-mail could not be sent: {type(error).__name__}: {error}")
        output["status"] = "sent"
        return AgentResult(self.name, True, output=output, sources=sources,
                           message=f"E-mail sent to {len(recipients)} recipient(s).")
