"""RFP & Tender Research Agent (Egypt + Saudi Arabia only).

Pipeline: validate -> country filter -> relevance filter -> expiry filter
-> duplicate detection -> summary -> review routing -> optional CSV export.
Every rejected item is reported with a reason, so filtering is demonstrable.
"""
import csv
import re
from datetime import date
from pathlib import Path

from .base import Agent, AgentResult
from .rfp_search import search_rfps

COUNTRY_ALIASES = {
    "egypt": "Egypt", "eg": "Egypt", "مصر": "Egypt",
    "saudi arabia": "Saudi Arabia", "saudi": "Saudi Arabia", "ksa": "Saudi Arabia",
    "kingdom of saudi arabia": "Saudi Arabia",
    "المملكة العربية السعودية": "Saudi Arabia", "السعودية": "Saudi Arabia",
}

RELEVANT_KEYWORDS = (
    "training", "education", "learning", "course", "curriculum", "capacity building",
    "professional development", "digital transformation", "it ", "software", "technical",
    "skills", "academy", "workshop", "تدريب", "تعليم", "تأهيل",
)

ROUTES = {
    "Egypt": "flag_for_immediate_review",
    "Saudi Arabia": "monitored_pipeline",
}

CSV_FIELDS = [
    "title", "organization", "country", "deadline", "category", "source_url",
    "publication_date", "eligibility", "review_route", "status", "summary",
]


def _parse_date(value):
    """Return a date, or None if missing/unparseable."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text or "").casefold()).strip()


class RfpAgent(Agent):
    name = "rfp_research"

    ALLOWED_COUNTRIES = {"egypt", "saudi arabia"}

    def run(self, task: dict) -> AgentResult:
        country = str(task.get("country", "")).strip()
        topic = str(task.get("topic", "education and technology")).strip()

        if country and country.lower() not in self.ALLOWED_COUNTRIES:
            return AgentResult(
                agent=self.name,
                ok=False,
                message="Only Egypt and Saudi Arabia are supported."
            )
        opportunities = task.get("opportunities")

        if opportunities is None:
            if not country:
                return AgentResult(
                    agent=self.name,
                    ok=True,
                    output={
                        "opportunities": [],
                        "count": 0,
                        "supported_countries": ["Egypt", "Saudi Arabia"],
                    },
                    message="Provide a country to search for RFP opportunities.",
                )

            search_result = search_rfps(
                "Egypt" if country.lower() == "egypt" else "Saudi Arabia",
                topic
            )

            if not search_result["ok"]:
                return AgentResult(
                    agent=self.name,
                    ok=False,
                    output={"opportunities": [], "count": 0},
                    message=search_result["message"]
                )

            opportunities = search_result["opportunities"]

        if not isinstance(opportunities, list):
            return AgentResult(
                agent=self.name, ok=False,
                message="Opportunities must be provided as a list.",
            )

        today = _parse_date(task.get("today")) or date.today()
        accepted, rejected, seen = [], [], set()

        for item in opportunities:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            url = str(item.get("source_url", "")).strip()

            def reject(reason, _title=title):
                rejected.append({"title": _title, "reason": reason})

            item_country = str(
                item.get("country", country)
            ).strip()

            if item_country.lower() not in self.ALLOWED_COUNTRIES:
                continue

            # 2. traceability: need a title and a source link
            if not title or not url:
                reject("missing title or source_url")
                continue

            # 3. relevance (education / training)
            haystack = _norm(f"{title} {item.get('description', '')} {item.get('category', '')} ") + " "
            if not any(k in haystack for k in RELEVANT_KEYWORDS):
                reject("not education/training related")
                continue

            # 4. expired
            deadline = _parse_date(item.get("deadline"))
            if deadline and deadline < today:
                reject(f"expired on {deadline.isoformat()}")
                continue

            # 5. duplicates (same link, or same title+issuer+country)
            keys = {("url", _norm(url)),
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
                "country": (
                    "Egypt" if item_country.lower() == "egypt"
                    else "Saudi Arabia"
                ),
                "review_route": ROUTES[country],
                "status": "requires_verification",
            })

        # Egypt first (flagged for immediate review), then by nearest deadline
        accepted.sort(key=lambda o: (o["country"] != "Egypt", o["deadline"] or "9999"))

        csv_path = task.get("csv_path")
        if csv_path:
            self._export_csv(accepted, Path(csv_path))

        return AgentResult(
            agent=self.name, ok=True,
            output={
                "opportunities": accepted,
                "count": len(accepted),
                "rejected": rejected,
                "rejected_count": len(rejected),
                "flagged_for_immediate_review": [
                    o["title"] for o in accepted if o["country"] == "Egypt"
                ],
                "monitored_pipeline": [
                    o["title"] for o in accepted if o["country"] == "Saudi Arabia"
                ],
                "supported_countries": ["Egypt", "Saudi Arabia"],
            },
            message=(
                f"Processed {len(accepted)} eligible opportunities "
                f"({len(rejected)} rejected). "
                "Verify each opportunity against its original source."
            ),
            sources=[item["source_url"] for item in results]
        )

    @staticmethod
    def _summary(title, org, country, deadline, days_left):
        who = f" issued by {org}" if org else ""
        when = (f" Deadline {deadline.isoformat()} ({days_left} days left)."
                if deadline else " Deadline not stated.")
        return f"{title}{who} in {country}.{when}"

    @staticmethod
    def _export_csv(rows, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)