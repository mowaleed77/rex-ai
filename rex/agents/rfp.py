
"""RFP & Tender Research Agent (Egypt + Saudi Arabia only).

Pipeline: validate -> country filter -> relevance filter -> expiry filter
-> duplicate detection -> summary -> review routing -> optional CSV export.
"""

import csv
import re
from datetime import date, datetime
from pathlib import Path

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

RELEVANT_KEYWORDS = (
    "training",
    "education",
    "learning",
    "course",
    "curriculum",
    "capacity building",
    "professional development",
    "digital transformation",
    "software",
    "technical",
    "skills",
    "academy",
    "workshop",
    "تدريب",
    "تعليم",
    "تأهيل",
)

ROUTES = {
    "Egypt": "flag_for_immediate_review",
    "Saudi Arabia": "monitored_pipeline",
}

CSV_FIELDS = [
    "title",
    "organization",
    "country",
    "deadline",
    "category",
    "source_url",
    "publication_date",
    "eligibility",
    "review_route",
    "status",
    "summary",
]


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    value = str(value).strip()
    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            pass
    return None


def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text or "").casefold()).strip()


def _canonical_country(value):
    return COUNTRY_ALIASES.get(_norm(value))


class RfpAgent(Agent):
    name = "rfp_research"

    ALLOWED_COUNTRIES = {"egypt", "saudi arabia", "ksa"}

    def run(self, task: dict) -> AgentResult:
        if not isinstance(task, dict):
            return AgentResult(
                agent=self.name,
                ok=False,
                message="Task must be a dictionary.",
            )

        country = str(task.get("country", "")).strip()
        topic = str(
            task.get("topic", "education and technology")
        ).strip() or "education and technology"

        requested_country = _canonical_country(country)

        if country and requested_country is None:
            return AgentResult(
                agent=self.name,
                ok=False,
                message="Only Egypt and Saudi Arabia are supported.",
            )

        opportunities = task.get("opportunities")

        if opportunities is None:
            if not requested_country:
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

            try:
                search_result = search_rfps(requested_country, topic)
            except Exception as error:
                return AgentResult(
                    agent=self.name,
                    ok=False,
                    output={"opportunities": [], "count": 0},
                    message=f"RFP search failed: {error}",
                )

            if not isinstance(search_result, dict):
                return AgentResult(
                    agent=self.name,
                    ok=False,
                    output={"opportunities": [], "count": 0},
                    message="RFP search returned an invalid response.",
                )

            if not search_result.get("ok"):
                return AgentResult(
                    agent=self.name,
                    ok=False,
                    output={"opportunities": [], "count": 0},
                    message=search_result.get("message", "RFP search failed."),
                )

            opportunities = search_result.get("opportunities", [])

        if not isinstance(opportunities, list):
            return AgentResult(
                agent=self.name,
                ok=False,
                message="Opportunities must be provided as a list.",
            )

        today = _parse_date(task.get("today")) or date.today()
        accepted = []
        rejected = []
        seen_urls = set()
        seen_records = set()

        for item in opportunities:
            if not isinstance(item, dict):
                rejected.append({"reason": "invalid opportunity"})
                continue

            opportunity = dict(item)
            title = str(opportunity.get("title", "")).strip()
            source_url = str(opportunity.get("source_url", "")).strip()
            organization = str(
                opportunity.get("organization", "")
            ).strip()
            item_country = _canonical_country(
                opportunity.get("country", "")
            )

            if not title or not source_url:
                rejected.append({
                    "title": title,
                    "reason": "missing title or source URL",
                })
                continue

            if not item_country:
                rejected.append({
                    "title": title,
                    "reason": "unsupported or missing country",
                })
                continue

            if requested_country and item_country != requested_country:
                rejected.append({
                    "title": title,
                    "reason": "country mismatch",
                })
                continue

            searchable_text = " ".join(
                str(opportunity.get(field, ""))
                for field in ("title", "description", "category", "summary")
            )
            normalized_text = _norm(searchable_text)

            if not any(
                _norm(keyword) in normalized_text
                for keyword in RELEVANT_KEYWORDS
            ):
                rejected.append({
                    "title": title,
                    "reason": "unrelated topic",
                })
                continue

            deadline = _parse_date(opportunity.get("deadline"))
            if deadline and deadline < today:
                rejected.append({
                    "title": title,
                    "reason": "expired deadline",
                })
                continue

            normalized_url = _norm(source_url).rstrip("/")
            record_key = (
                _norm(title),
                _norm(organization),
                item_country,
            )

            if normalized_url in seen_urls or record_key in seen_records:
                rejected.append({
                    "title": title,
                    "reason": "duplicate",
                })
                continue

            seen_urls.add(normalized_url)
            seen_records.add(record_key)

            opportunity["title"] = title
            opportunity["source_url"] = source_url
            opportunity["organization"] = organization
            opportunity["country"] = item_country
            opportunity["review_route"] = ROUTES[item_country]
            opportunity["status"] = "requires_verification"
            opportunity["summary"] = str(
                opportunity.get("description")
                or opportunity.get("summary")
                or title
            ).strip()

            accepted.append(opportunity)

        # Always list Egypt before Saudi Arabia.
        accepted.sort(
            key=lambda item: (
                0 if item["country"] == "Egypt" else 1,
                item["title"].casefold(),
            )
        )

        output = {
            "opportunities": accepted,
            "count": len(accepted),
            "rejected": rejected,
            "rejected_count": len(rejected),
            "supported_countries": ["Egypt", "Saudi Arabia"],
        }

        csv_path = task.get("csv_path") or task.get("export_csv")

        if csv_path:
            try:
                path = Path(csv_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open(
                    "w",
                    newline="",
                    encoding="utf-8-sig",
                ) as csv_file:
                    writer = csv.DictWriter(
                        csv_file,
                        fieldnames=CSV_FIELDS,
                        extrasaction="ignore",
                    )
                    writer.writeheader()
                    writer.writerows(accepted)
                output["csv_path"] = str(path)
            except (OSError, ValueError) as error:
                output["csv_error"] = str(error)

        return AgentResult(
            agent=self.name,
            ok=True,
            output=output,
            message=(
                f"Processed {len(opportunities)} opportunities: "
                f"{len(accepted)} accepted, {len(rejected)} rejected."
            ),
            sources=[item["source_url"] for item in accepted],
        )
