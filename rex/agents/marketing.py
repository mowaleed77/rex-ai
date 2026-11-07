"""Marketing Agent - multi-channel campaigns with a human approval workflow.

Actions (task["action"]):
  generate (default)            build a campaign for one course
  approve | reject | request_changes   reviewer decision (reviewer required; note required to reject / ask changes)
  export                        Markdown + plain-text version of a campaign

`generate` input:
  course      dict   title, title_ar, description(_ar), duration_hours, price, promotion(_ar), level, formats,
                     target_audience(_ar), learning_outcomes(_ar)   (see rex.utils.catalog.marketing_view)
  curriculum  dict   optional Curriculum-agent output; its hours / level / outcomes / prerequisites win
  language    en | ar | both          channels  see CHANNELS           variations  1..5 per channel
  objective   leads | awareness | enrollment | free text      budget, cta, target_audience  optional
  use_llm     True -> the LLM writes the copy; every variation is fact-checked and falls back to a template

Rules: only facts present in the input are used (no invented price, offer, statistic or accreditation claim),
and nothing is ever published - an approved campaign is only *ready for distribution*.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone

from .base import Agent, AgentResult

CHANNELS = ["instagram", "facebook", "instagram_ad", "facebook_ad", "linkedin", "email", "whatsapp"]
DEFAULT_CHANNELS = ["instagram", "facebook", "linkedin", "email", "whatsapp"]
CHANNEL_LABELS = {
    "instagram": "Instagram caption", "facebook": "Facebook post", "instagram_ad": "Instagram ad copy",
    "facebook_ad": "Facebook ad copy", "linkedin": "LinkedIn post", "email": "Email", "whatsapp": "WhatsApp message",
}
LANGS = ("en", "ar")
MAX_VARIATIONS = 5

OBJECTIVES = {
    "leads": {"en": "Generate qualified leads and inquiries", "ar": "جذب استفسارات وعملاء محتملين مؤهلين"},
    "awareness": {"en": "Build awareness of the course", "ar": "رفع الوعي بالدورة"},
    "enrollment": {"en": "Drive registrations for the next intake", "ar": "زيادة التسجيل في الدفعة القادمة"},
}

UI = {
    "en": {
        "audience": "people who want to build new skills", "hours": "{n} training hours", "level": "{v} level",
        "format": "Format: {v}", "price": "Price: {v}", "offer": "Offer: {v}", "prereq": "Prerequisites: {v}",
        "learn": "You will learn: {v}", "cta": "Contact us to learn more.", "cta2": "Register now.",
        "cta3": "Message us to reserve your seat.", "hello": "Hello,", "regards": "Best regards,\nSmart Academy",
        "wa_hello": "Hello! 👋", "wa_close": "Reply to this message to register.",
        "tags": ["#SmartAcademy", "#Learning", "#Training"],
    },
    "ar": {
        "audience": "كل من يرغب في تطوير مهاراته", "hours": "{n} ساعة تدريبية", "level": "المستوى: {v}",
        "format": "نظام الدراسة: {v}", "price": "السعر: {v}", "offer": "العرض: {v}", "prereq": "المتطلبات: {v}",
        "learn": "ماذا ستتعلم: {v}", "cta": "تواصل معنا لمعرفة المزيد.", "cta2": "سجّل الآن.",
        "cta3": "راسلنا الآن لحجز مقعدك.", "hello": "مرحباً،", "regards": "مع أطيب التحيات،\nSmart Academy",
        "wa_hello": "أهلاً بك! 👋", "wa_close": "ردّ على هذه الرسالة للتسجيل.",
        "tags": ["#SmartAcademy", "#تعلّم", "#تدريب"],
    },
}
LEVEL_AR = {"Beginner": "مبتدئ", "Intermediate": "متوسط", "Advanced": "متقدم"}
FORMAT_AR = {"online": "أونلاين", "onsite": "حضوري", "hybrid": "مدمج"}

# Every variation uses a different angle, so the copies are genuinely different, not re-worded.
ANGLES = {
    "en": [
        ("Start with {title}", "Ready to learn something new? Join {title}, designed for {audience}."),
        ("Build real skills", "Turn what you learn into real skills with {title}. Made for {audience}."),
        ("Your next career step", "Take the next step toward your goals with {title} - built for {audience}."),
        ("Learn by doing", "{title}: practical, hands-on learning for {audience}."),
        ("Why wait?", "The best time to start is now. Discover {title}, ideal for {audience}."),
    ],
    "ar": [
        ("ابدأ رحلتك مع {title}", "مستعد لتعلّم شيء جديد؟ انضم إلى {title}، المصممة لـ {audience}."),
        ("اكتسب مهارات حقيقية", "حوّل ما تتعلمه إلى مهارات حقيقية مع {title}. مناسبة لـ {audience}."),
        ("خطوتك المهنية القادمة", "اتخذ الخطوة التالية نحو أهدافك مع {title} - مصممة لـ {audience}."),
        ("تعلّم بالتطبيق العملي", "{title}: تعلّم عملي وتطبيقي لـ {audience}."),
        ("لماذا تنتظر؟", "أفضل وقت للبدء هو الآن. اكتشف {title}، المناسبة لـ {audience}."),
    ],
}

CALENDAR_DAYS = {
    "en": ["Announce the course (awareness post)", "Share the learning outcomes", "Answer common questions",
           "Highlight who the course is for", "Share the offer or registration steps", "Send email / WhatsApp to warm leads",
           "Review results and repeat the best post"],
    "ar": ["الإعلان عن الدورة (منشور توعوي)", "عرض مخرجات التعلم", "الإجابة عن الأسئلة الشائعة",
           "توضيح الفئة المستهدفة", "مشاركة العرض أو خطوات التسجيل", "إرسال بريد / واتساب للعملاء المحتملين",
           "مراجعة النتائج وتكرار أفضل منشور"],
}
KPIS = {
    "en": ["Reach and impressions", "Click-through rate", "Inquiries / messages received", "Registrations"],
    "ar": ["الوصول والظهور", "نسبة النقر", "عدد الاستفسارات والرسائل", "عدد التسجيلات"],
}
CHANNEL_ROLES = {
    "en": {"instagram": "awareness with short visual captions", "facebook": "awareness and community questions",
           "instagram_ad": "paid reach", "facebook_ad": "paid reach", "linkedin": "professionals and corporate teams",
           "email": "warm leads with full details", "whatsapp": "direct, personal conversion"},
    "ar": {"instagram": "الوعي بمنشورات قصيرة", "facebook": "الوعي وأسئلة المجتمع", "instagram_ad": "وصول مدفوع",
           "facebook_ad": "وصول مدفوع", "linkedin": "المهنيون وفرق الشركات", "email": "عملاء محتملون بتفاصيل كاملة",
           "whatsapp": "تحويل مباشر وشخصي"},
}

# claims an AI copywriter must never make unless the course data says so
_RISKY_RE = re.compile(
    r"accredit|certified by|guarantee|100\s?%|#1|best in|number one|ranked|"
    r"معتمد|اعتماد رسمي|مضمون|ضمان|الأفضل في", re.I)
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _money(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"EGP {int(value):,}"
    return str(value).strip()


def _hours(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    return str(int(v)) if v == int(v) else str(v)


class MarketingAgent(Agent):
    name = "marketing"

    def __init__(self, llm=None):
        self._llm = llm

    def _get_llm(self):
        if self._llm is None:
            try:
                from rex.rag.llm import LLMClient
                self._llm = LLMClient.from_env()
            except Exception:
                self._llm = None
        return self._llm

    # ------------------------------------------------------------------ dispatch
    def run(self, task: dict) -> AgentResult:
        action = task.get("action", "generate")
        if action == "generate":
            return self.generate(task)
        if action in ("approve", "reject", "request_changes"):
            return self.review(task, action)
        if action == "export":
            return self.export(task)
        return AgentResult(self.name, False,
                           message="Choose action: generate, approve, reject, request_changes or export.")

    # ------------------------------------------------------------------ generate
    def generate(self, task: dict) -> AgentResult:
        raw = task.get("course")
        if not isinstance(raw, dict):
            return AgentResult(self.name, False, message="Course title is required (course must be an object).")
        facts = self._facts(raw, task.get("curriculum") if isinstance(task.get("curriculum"), dict) else None)
        if not (facts["title"] or facts["title_ar"]):
            return AgentResult(self.name, False, message="Course title is required.")

        language = str(task.get("language", "en")).lower()
        if language not in ("en", "ar", "both"):
            return AgentResult(self.name, False, message="language must be 'en', 'ar' or 'both'.")
        langs = list(LANGS) if language == "both" else [language]

        channels = task.get("channels") or DEFAULT_CHANNELS
        if not isinstance(channels, (list, tuple)):
            return AgentResult(self.name, False, message="channels must be a list.")
        channels = [str(c).lower().strip() for c in channels]
        unknown = [c for c in channels if c not in CHANNELS]
        if unknown or not channels:
            return AgentResult(self.name, False,
                               message=f"Unsupported channel(s): {', '.join(unknown) or 'none given'}. "
                                       f"Choose from: {', '.join(CHANNELS)}.")
        channels = list(dict.fromkeys(channels))

        try:
            variations = max(1, min(int(task.get("variations", 2)), MAX_VARIATIONS))
        except (TypeError, ValueError):
            variations = 2

        warnings = self._warnings(facts, task.get("curriculum"))
        notes: list[str] = []
        content: dict[str, list] = {}
        llm_used = False
        llm = None
        if task.get("use_llm"):
            llm = self._get_llm()
            if llm is None:
                notes.append("AI mode unavailable (no LLM key configured); template copy was used.")

        for lang in langs:
            for channel in channels:
                items = [self._template_item(facts, lang, channel, n, task) for n in range(variations)]
                if llm is not None:
                    items, used, note = self._llm_items(llm, facts, lang, channel, items, task)
                    llm_used = llm_used or used
                    if note:
                        notes.append(note)
                key = f"{channel}:{lang}" if language == "both" else channel
                content[key] = items

        primary = langs[0]
        strategy = self._strategy(facts, primary, channels, task)
        output = {
            "course_title": facts["title_ar"] if primary == "ar" and facts["title_ar"] else (facts["title"] or facts["title_ar"]),
            "language": language,
            "channels": channels,
            "content": content,
            "headlines": self._headlines(facts, langs, variations),
            "call_to_actions": self._ctas(langs, task),
            "hashtags": self._hashtags(facts, langs),
            "campaign_strategy": strategy,
            "warnings": warnings,
            "status": "pending_admin_approval",
            "approved": False,
            "published": False,
            "generated_by": "llm" if llm_used else "template",
            "facts_used": {k: facts[k] for k in ("hours", "level", "price", "promotion") if facts[k]},
            "history": [{"event": "generated", "by": "marketing agent", "at": _now()}],
        }
        message = (f"Generated {sum(len(v) for v in content.values())} pieces of campaign content "
                   f"({'AI copy where it passed the fact check, template otherwise' if llm_used else 'template copy'}). "
                   "Admin approval is required before publishing.")
        if notes:
            message += " " + " ".join(dict.fromkeys(notes))
        return AgentResult(self.name, True, output=output, message=message,
                           sources=[facts["source"]] if facts["source"] else [])

    # --------------------------------------------------------------- facts / text
    @staticmethod
    def _facts(course: dict, curriculum: dict | None) -> dict:
        cur = curriculum or {}
        promo = str(course.get("promotion") or "").strip()
        promo_ar = str(course.get("promotion_ar") or "").strip()
        none_words = ("", "none", "no", "لا يوجد", "لا توجد")
        return {
            "title": str(course.get("title") or course.get("title_en") or cur.get("course") or "").strip(),
            "title_ar": str(course.get("title_ar") or "").strip(),
            "description": str(course.get("description") or "").strip(),
            "description_ar": str(course.get("description_ar") or "").strip(),
            "hours": _hours(cur.get("duration_hours") or course.get("duration_hours")),
            "level": str(cur.get("level") or course.get("level") or "").strip(),
            "formats": [str(f) for f in (course.get("formats") or [])],
            "price": _money(course.get("price") if course.get("price") is not None else course.get("price_egp")),
            "promotion": "" if promo.lower() in none_words else promo,
            "promotion_ar": "" if promo_ar in none_words else promo_ar,
            "prerequisites": str(cur.get("prerequisites") or course.get("prerequisites") or "").strip(),
            "audience": str(course.get("target_audience") or "").strip(),
            "audience_ar": str(course.get("target_audience_ar") or "").strip(),
            "outcomes": list(cur.get("learning_outcomes") or course.get("learning_outcomes") or []),
            "outcomes_ar": list(course.get("learning_outcomes_ar") or []),
            "curriculum_language": cur.get("language"),
            "source": str(course.get("source") or ""),
            "data_source": str(course.get("data_source") or ""),
        }

    def _warnings(self, facts: dict, curriculum) -> list[str]:
        out = []
        if not facts["price"]:
            out.append("No price in the course data - none was mentioned in the copy.")
        if not facts["hours"]:
            out.append("No duration in the course data - none was mentioned in the copy.")
        sample = "SAMPLE" in facts["data_source"].upper()
        if not sample and facts["source"].startswith("data/courses.json#"):
            try:
                from rex.utils import catalog as cat
                entry = cat.find_course(facts["source"].split("#", 1)[1])
                sample = bool(entry) and "SAMPLE" in str(entry.get("data_source", "")).upper()
            except Exception:
                sample = False
        if sample:
            out.append("The course data is marked SAMPLE DATA - replace it with the approved academy catalog before "
                       "publishing.")
        if isinstance(curriculum, dict) and curriculum.get("status_code", "approved") != "approved":
            out.append("The curriculum behind these facts is not approved yet - re-check the copy after approval.")
        return out

    def _title(self, facts: dict, lang: str) -> str:
        return (facts["title_ar"] if lang == "ar" and facts["title_ar"] else facts["title"] or facts["title_ar"])

    def _audience(self, facts: dict, lang: str, task: dict) -> str:
        given = str(task.get("target_audience") or "").strip()
        if given:
            return given
        return (facts["audience_ar"] if lang == "ar" else facts["audience"]) or UI[lang]["audience"]

    def _fact_parts(self, facts: dict, lang: str) -> list[str]:
        ui = UI[lang]
        parts = []
        if facts["hours"]:
            parts.append(ui["hours"].format(n=facts["hours"]))
        if facts["level"]:
            parts.append(ui["level"].format(v=LEVEL_AR.get(facts["level"], facts["level"]) if lang == "ar" else facts["level"]))
        if facts["formats"]:
            fm = [FORMAT_AR.get(f, f) if lang == "ar" else f for f in facts["formats"]]
            parts.append(ui["format"].format(v=" / ".join(fm)))
        if facts["price"]:
            parts.append(ui["price"].format(v=facts["price"]))
        promo = (facts["promotion_ar"] or facts["promotion"]) if lang == "ar" else facts["promotion"]
        if promo:
            parts.append(ui["offer"].format(v=promo))
        return parts

    def _template_item(self, facts: dict, lang: str, channel: str, n: int, task: dict) -> dict:
        ui = UI[lang]
        title = self._title(facts, lang)
        audience = self._audience(facts, lang, task)
        head_t, body_t = ANGLES[lang][n % len(ANGLES[lang])]
        headline = head_t.format(title=title)
        body = body_t.format(title=title, audience=audience)
        parts = self._fact_parts(facts, lang)
        desc = facts["description_ar"] if lang == "ar" else facts["description"]
        outcomes = (facts["outcomes_ar"] if lang == "ar" and facts["outcomes_ar"] else facts["outcomes"])[:3]
        learn = ui["learn"].format(v=("؛ " if lang == "ar" else "; ").join(outcomes)) if outcomes else ""
        custom = str(task.get("cta") or "").strip()
        cta = [custom or ui["cta"], ui["cta2"], ui["cta3"]][n % 3]
        details = " • ".join(parts)
        item = {"variation": n + 1, "language": lang, "headline": headline, "call_to_action": cta,
                "written_by": "template"}

        if channel == "instagram":
            tags = " ".join(self._hashtags(facts, [lang]))
            item["text"] = "\n\n".join(p for p in (body, desc, details, learn, cta, tags) if p)
        elif channel == "facebook":
            item["text"] = "\n\n".join(p for p in (body, desc, details, learn, cta) if p)
        elif channel in ("instagram_ad", "facebook_ad"):
            item["headline"] = _clip(headline, 40)
            item["primary_text"] = _clip(" ".join(p for p in (body, " | ".join(parts)) if p), 300)
            item["description"] = _clip(parts[0] if parts else cta, 30)
            item["text"] = item["primary_text"]
        elif channel == "linkedin":
            item["text"] = "\n\n".join(p for p in (body, learn or desc, details, cta) if p)
        elif channel == "email":
            item["subject"] = headline if n == 0 else f"{headline} | {title}"
            item["text"] = "\n\n".join(p for p in (ui["hello"], body, desc, details, learn, cta, ui["regards"]) if p)
        else:  # whatsapp
            item["text"] = _clip("\n".join(p for p in (ui["wa_hello"], body, details, ui["wa_close"]) if p), 900)
        return item

    @staticmethod
    def _hashtags(facts: dict, langs: list[str]) -> list[str]:
        tags: list[str] = []
        for lang in langs:
            title = facts["title_ar"] if lang == "ar" and facts["title_ar"] else facts["title"] or facts["title_ar"]
            words = re.findall(r"\w+", title)[:3]
            custom = "".join(w.capitalize() if lang == "en" else w for w in words)
            tags += UI[lang]["tags"][:1] + ([f"#{custom}"] if custom else []) + UI[lang]["tags"][1:]
        return list(dict.fromkeys(tags))

    def _headlines(self, facts: dict, langs: list[str], variations: int) -> list[str]:
        out = []
        for lang in langs:
            title = self._title(facts, lang)
            out += [ANGLES[lang][i % len(ANGLES[lang])][0].format(title=title) for i in range(max(variations, 3))]
        return list(dict.fromkeys(out))

    @staticmethod
    def _ctas(langs: list[str], task: dict) -> list[str]:
        out = []
        for lang in langs:
            if task.get("cta"):
                out.append(str(task["cta"]).strip())
            out += [UI[lang]["cta"], UI[lang]["cta2"], UI[lang]["cta3"]]
        return list(dict.fromkeys(out))

    def _strategy(self, facts: dict, lang: str, channels: list[str], task: dict) -> dict:
        objective = str(task.get("objective") or "leads").strip()
        goal = OBJECTIVES.get(objective.lower(), {}).get(lang) or objective
        title = self._title(facts, lang)
        audience = self._audience(facts, lang, task)
        outcomes = (facts["outcomes_ar"] if lang == "ar" and facts["outcomes_ar"] else facts["outcomes"])[:3]
        key_messages = [
            (f"{title} - {audience}" if lang == "en" else f"{title} - {audience}"),
            *(outcomes[:3]),
            *self._fact_parts(facts, lang)[:2],
        ]
        calendar = [{"day": i + 1, "channel": channels[i % len(channels)], "post": CALENDAR_DAYS[lang][i]}
                    for i in range(7)]
        strategy = {
            "goal": goal if goal.lower() != objective.lower() or objective not in OBJECTIVES else goal,
            "target_audience": audience,
            "key_messages": [m for m in key_messages if m],
            "channel_roles": {c: CHANNEL_ROLES[lang].get(c, "") for c in channels},
            "posting_calendar_7_days": calendar,
            "kpis": KPIS[lang],
            "ab_testing": ("Run at least two variations per channel and keep the one with the best response."
                           if lang == "en" else "شغّل نسختين على الأقل لكل قناة واحتفظ بالأفضل استجابة."),
            "recommended_action": calendar[0]["post"],
        }
        budget = str(task.get("budget") or "").strip()
        if budget:
            paid = [c for c in channels if c.endswith("_ad")]
            strategy["budget"] = budget
            if paid:
                strategy["budget_note"] = (
                    f"Put most of {budget} on {', '.join(paid)} and split it between the variations in week 1."
                    if lang == "en" else f"وجّه معظم ميزانية {budget} إلى {', '.join(paid)} وقسّمها بين النسخ في الأسبوع الأول.")
            else:
                strategy["budget_note"] = (
                    f"Add an ad channel (instagram_ad or facebook_ad) to use the {budget} budget on paid reach."
                    if lang == "en" else f"أضف قناة إعلانية (instagram_ad أو facebook_ad) لاستخدام ميزانية {budget}.")
        return strategy

    # ------------------------------------------------------------------ AI copy
    def _llm_items(self, llm, facts, lang, channel, template_items, task):
        """Ask the LLM for the variations of one channel; keep only items that pass the fact check."""
        n = len(template_items)
        title = self._title(facts, lang)
        system = (
            "You are a marketing copywriter for a training academy. Reply with ONE JSON array of exactly "
            f"{n} objects, each {{\"headline\": str, \"text\": str, \"call_to_action\": str"
            + (", \"subject\": str" if channel == "email" else "") + "}. "
            f"Write in {'Arabic' if lang == 'ar' else 'English'} for the channel '{CHANNEL_LABELS[channel]}'. "
            "Each variation must use a different angle. Use ONLY the facts provided. Never invent prices, offers, "
            "dates, numbers, statistics, instructors or accreditation claims. Ad copy: text <= 300 characters, "
            "headline <= 40 characters.")
        user = (f"Course: {title}\nDescription: {(facts['description_ar'] if lang == 'ar' else facts['description'])}\n"
                f"Facts: {json.dumps(self._fact_parts(facts, lang), ensure_ascii=False)}\n"
                f"Learning outcomes: {json.dumps(facts['outcomes_ar'] if lang == 'ar' and facts['outcomes_ar'] else facts['outcomes'], ensure_ascii=False)}\n"
                f"Audience: {self._audience(facts, lang, task)}\nCall to action: {task.get('cta') or UI[lang]['cta']}")
        try:
            raw = llm([{"role": "system", "content": system}, {"role": "user", "content": user}])
            m = re.search(r"\[.*\]", raw or "", re.S)
            data = json.loads(m.group(0)) if m else None
            if not isinstance(data, list):
                raise ValueError("the reply was not a JSON list")
        except Exception as error:
            return template_items, False, f"AI copy failed for {channel} ({error}); template copy was used."

        allowed = self._allowed_numbers(facts, task)
        out, used, rejected = [], False, 0
        for i, base in enumerate(template_items):
            cand = data[i] if i < len(data) and isinstance(data[i], dict) else None
            text = str(cand.get("text", "")).strip() if cand else ""
            if not text or not self._passes_fact_check(text + " " + str(cand.get("headline", "")), allowed):
                out.append(base)
                rejected += bool(cand)
                continue
            item = dict(base)
            item.update({"text": text, "written_by": "llm",
                         "headline": str(cand.get("headline") or base["headline"]).strip(),
                         "call_to_action": str(cand.get("call_to_action") or base["call_to_action"]).strip()})
            if channel == "email":
                item["subject"] = str(cand.get("subject") or item["headline"]).strip()
            if channel.endswith("_ad"):
                item["headline"] = _clip(item["headline"], 40)
                item["primary_text"] = _clip(text, 300)
                item["text"] = item["primary_text"]
                item["description"] = _clip(base.get("description", ""), 30)
            out.append(item)
            used = True
        note = (f"{rejected} AI variation(s) for {channel} were rejected by the fact check and replaced "
                "with template copy.") if rejected else ""
        return out, used, note

    def _allowed_numbers(self, facts: dict, task: dict) -> set[str]:
        blob = " ".join(str(v) for v in (
            facts["title"], facts["title_ar"], facts["description"], facts["description_ar"], facts["hours"],
            facts["price"], facts["promotion"], facts["promotion_ar"], facts["prerequisites"],
            " ".join(facts["outcomes"]), " ".join(facts["outcomes_ar"]), facts["audience"], facts["audience_ar"],
            task.get("budget", ""), task.get("cta", ""), task.get("target_audience", "")))
        return {n.replace(",", "") for n in _NUM_RE.findall(blob.translate(_AR_DIGITS))}

    @staticmethod
    def _passes_fact_check(text: str, allowed: set[str]) -> bool:
        if _RISKY_RE.search(text):
            return False
        found = {n.replace(",", "").rstrip(".") for n in _NUM_RE.findall(text.translate(_AR_DIGITS))}
        return found <= allowed

    # ----------------------------------------------------------- review / export
    def review(self, task: dict, action: str) -> AgentResult:
        campaign = task.get("campaign")
        if not isinstance(campaign, dict) or "status" not in campaign:
            return AgentResult(self.name, False, message="Provide the campaign to review.")
        reviewer = str(task.get("reviewer") or "").strip()
        if not reviewer:
            return AgentResult(self.name, False, message="A reviewer name is required.")
        if task.get("role") not in (None, "admin"):
            return AgentResult(self.name, False, message="Only an admin can review a campaign.")
        note = str(task.get("note") or "").strip()
        if action in ("reject", "request_changes") and not note:
            return AgentResult(self.name, False, message="A note is required to reject or request changes.")
        out = deepcopy(campaign)
        out["status"] = {"approve": "approved", "reject": "rejected", "request_changes": "changes_requested"}[action]
        out["approved"] = action == "approve"
        out["published"] = False  # approval only means "ready for distribution"
        out.setdefault("history", []).append({"event": out["status"], "by": reviewer, "note": note, "at": _now()})
        label = {"approve": "approved - ready for distribution (not published automatically)",
                 "reject": "rejected", "request_changes": "sent back for changes"}[action]
        return AgentResult(self.name, True, output=out, message=f"Campaign {label} by {reviewer}.")

    def export(self, task: dict) -> AgentResult:
        c = task.get("campaign")
        if not isinstance(c, dict) or "content" not in c:
            return AgentResult(self.name, False, message="Provide the campaign to export.")
        md = [f"# Campaign - {c.get('course_title', '')}", "",
              f"**Status:** {c.get('status')} · **Published:** {'yes' if c.get('published') else 'no'}", ""]
        txt = [f"CAMPAIGN - {c.get('course_title', '')}", f"Status: {c.get('status')}", ""]
        strategy = c.get("campaign_strategy") or {}
        if strategy:
            md += ["## Strategy", f"- **Goal:** {strategy.get('goal', '')}",
                   f"- **Audience:** {strategy.get('target_audience', '')}", ""]
            txt += [f"Goal: {strategy.get('goal', '')}", f"Audience: {strategy.get('target_audience', '')}", ""]
        for key, items in c["content"].items():
            channel, _, lang = key.partition(":")
            label = CHANNEL_LABELS.get(channel, channel) + (f" ({lang})" if lang else "")
            md += [f"## {label}", ""]
            txt += [label.upper(), "-" * len(label)]
            for it in items:
                md.append(f"**Variation {it.get('variation')}** - _{it.get('headline', '')}_")
                if it.get("subject"):
                    md.append(f"**Subject:** {it['subject']}")
                md += ["", it.get("text", ""), "", f"CTA: {it.get('call_to_action', '')}", ""]
                txt += [f"[{it.get('variation')}] {it.get('headline', '')}"]
                if it.get("subject"):
                    txt.append(f"Subject: {it['subject']}")
                txt += [it.get("text", ""), f"CTA: {it.get('call_to_action', '')}", ""]
        for w in c.get("warnings", []):
            md.append(f"> Note: {w}")
        return AgentResult(self.name, True, output={"markdown": "\n".join(md), "text": "\n".join(txt)},
                           message="Campaign exported.")
