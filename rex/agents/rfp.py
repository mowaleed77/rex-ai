"""RFP & Tender Research Agent (Egypt + Saudi Arabia only).

Pipeline: [online discovery] -> validate -> country filter -> relevance filter
-> expiry filter -> duplicate detection -> summary -> review routing
-> new-opportunity detection + alert -> optional CSV export.
Every rejected item is reported with a reason, so filtering is demonstrable.

Task keys:
  opportunities : list[dict]   pre-collected items (optional)
  discover      : bool         search the web for new items (needs a search backend)
  max_results   : int          results per query (default 8)
  today         : "YYYY-MM-DD" override for tests
  csv_path      : str          export accepted items
  store_path    : str          JSON file remembering seen URLs -> flags new items
"""

import csv
import json
import re
from datetime import date, datetime
from pathlib import Path

from rex.agents.rfp_sources import TavilySearch, parse_date
from .base import Agent, AgentResult
from .rfp_search import search_rfps


COUNTRY_ALIASES = {
    "egypt": "Egypt",
    "eg": "Egypt",
    "saudi arabia": "Saudi Arabia",
    "saudi": "Saudi Arabia",
    "ksa": "Saudi Arabia",
    "kingdom of saudi arabia": "Saudi Arabia",
    "مصر": "Egypt",
    "السعودية": "Saudi Arabia",
    "المملكة العربية السعودية": "Saudi Arabia",
}

_RELEVANT_RE = re.compile(
    r"\b(training|trainers?|education(?:al)?|learning|courses?|curricul\w+|capacity building"
    r"|professional development|digital transformation|information technology"
    r"|it (?:training|skills|services|courses)|software|technical|skills|academy|workshops?)\b"
    r"|تدريب|تعليم|تأهيل|تطوير المهارات"
)

ROUTES = {
    "Egypt": "flag_for_immediate_review",
    "Saudi Arabia": "monitored_pipeline",
}

CSV_FIELDS = [
    "title", "organization", "country", "deadline", "category", "source_url",
    "publication_date", "eligibility", "review_route", "status", "is_new", "summary",
]


def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text or "").casefold()).strip()


def _norm_url(url) -> str:
    return _norm(url).split("#")[0].rstrip("/")


class RfpAgent(Agent):
    name = "rfp_research"

    def __init__(self, *args, searcher=None, extractor=None, notifier=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.searcher = searcher if searcher is not None else TavilySearch()
        self.extractor = extractor
        self.notifier = notifier

    def run(self, task: dict) -> AgentResult:
        opportunities = task.get("opportunities", [])
        if not isinstance(opportunities, list):
            return AgentResult(
                agent=self.name,
                ok=False,
                message="Opportunities must be provided as a list.",
            )

        today = parse_date(task.get("today")) or date.today()
        discovery = {"ran": False, "candidates": 0, "errors": []}

        # ---- ONLINE DISCOVERY ----
        if task.get("discover"):
            discovery["ran"] = True
            try:
                found_all = []
                # Search live for both supported countries
                for country in ["Egypt", "Saudi Arabia"]:
                    res = search_rfps(country=country, topic="education training digital transformation")
                    if isinstance(res, dict):
                        if res.get("ok"):
                            found_all.extend(res.get("opportunities", []))
                        elif res.get("message"):
                            discovery["errors"].append(res["message"])
                
                opportunities = found_all + opportunities
                discovery["candidates"] = len(found_all)
            except Exception as exc:
                discovery["errors"].append(str(exc))
        accepted, rejected, seen = [], [], set()

        for item in opportunities:
            if not isinstance(item, dict):
                rejected.append({"reason": "invalid opportunity"})
                continue

            # Extract fields first so they exist in scope for reject()
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", item.get("source_url", ""))).strip()

            def reject(reason, _title=title, _url=url):
                rejected.append({"title": _title, "source_url": _url, "reason": reason})

            # 1. strict geographic rule
            country = COUNTRY_ALIASES.get(_norm(item.get("country")))
            if not country:
                reject("outside Egypt/Saudi Arabia")
                continue

            # 2. traceability: need a title and a source link
            if not title or not url:
                reject("missing title or source_url")
                continue

            # 3. relevance (education / training)
            haystack = _norm(f"{title} {item.get('description', '')} {item.get('category', '')}")
            if not _RELEVANT_RE.search(haystack):
                reject("not education/training related")
                continue

            # 4. expired
            deadline = parse_date(item.get("deadline"))
            if deadline and deadline < today:
                reject(f"expired on {deadline.isoformat()}")
                continue

            # 5. duplicates (same link, or same title+issuer+country)
            keys = {("url", _norm_url(url)),
                    ("tuple", _norm(title), _norm(item.get("organization")), country)}
            if keys & seen:
                reject("duplicate")
                continue
            seen |= keys

            org = str(item.get("organization", "")).strip()
            eligibility = str(item.get("eligibility", "")).strip()
            days_left = (deadline - today).days if deadline else None

            accepted.append({
                "title": title,
                "country": country,
                "organization": org,
                "deadline": deadline.isoformat() if deadline else str(item.get("deadline", "") or ""),
                "days_left": days_left,
                "category": str(item.get("category", "") or ""),
                "publication_date": str(item.get("publication_date", "") or ""),
                "eligibility": eligibility,
                "documents": item.get("documents", []),
                "description": str(item.get("description", "") or ""),
                "source_url": url,
                "summary": self._summary(title, org, country, deadline, days_left),
                "eligibility_assessment": (
                    "needs_manual_review" if eligibility
                    else "unknown - eligibility not provided"
                ),
                "review_route": ROUTES[country],
                "status": "requires_verification",
                "is_new": True,
            })

        # Egypt first (flagged for immediate review), then nearest deadline
        accepted.sort(key=lambda o: (o["country"] != "Egypt", o["deadline"] or "9999"))

        # ---- new-opportunity detection + alert ----
        new_items = self._mark_new(accepted, task.get("store_path"))
        if new_items and self.notifier:
            try:
                self.notifier(new_items)
            except Exception as exc:
                discovery["errors"].append(f"notifier failed: {exc}")

        output = {
            "opportunities": accepted,
            "count": len(accepted),
            "new_count": len(new_items),
            "rejected": rejected,
            "rejected_count": len(rejected),
            "flagged_for_immediate_review": [
                o["title"] for o in accepted if o["country"] == "Egypt"
            ],
            "monitored_pipeline": [
                o["title"] for o in accepted if o["country"] == "Saudi Arabia"
            ],
            "supported_countries": ["Egypt", "Saudi Arabia"],
            "discovery": discovery,
        }

        csv_path = task.get("csv_path") or task.get("export_csv")
        if csv_path:
            try:
                path = Path(csv_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
                    writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(accepted)
                output["csv_path"] = str(path)
            except (OSError, ValueError) as error:
                output["csv_error"] = str(error)

        return AgentResult(
            agent=self.name, ok=True,
            output=output,
            message=(
                f"Processed {len(accepted)} eligible opportunities "
                f"({len(new_items)} new, {len(rejected)} rejected"
                + (f", {discovery['candidates']} found online" if discovery["ran"] else "")
                + "). Verify each opportunity against its original source."
            ),
            sources=[o["source_url"] for o in accepted],
        )

    @staticmethod
    def _mark_new(accepted, store_path):
        if not store_path:
            return list(accepted)
        path = Path(store_path)
        try:
            known = set(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            known = set()
        new_items = []
        for o in accepted:
            key = _norm_url(o["source_url"])
            o["is_new"] = key not in known
            if o["is_new"]:
                new_items.append(o)
            known.add(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sorted(known), ensure_ascii=False), encoding="utf-8")
        return new_items

    @staticmethod
    def _summary(title, org, country, deadline, days_left):
        who = f" issued by {org}" if org else ""
        when = (f" Deadline {deadline.isoformat()} ({days_left} days left)."
                if deadline else " Deadline not stated.")
        return f"{title}{who} in {country}.{when}"