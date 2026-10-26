
from .base import Agent, AgentResult
from .rfp_search import search_rfps


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
                    ok=False,
                    message="Provide a country for live RFP research."
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
                agent=self.name,
                ok=False,
                message="Opportunities must be provided as a list."
            )

        results = []

        for item in opportunities:
            if not isinstance(item, dict):
                continue

            item_country = str(
                item.get("country", country)
            ).strip()

            if item_country.lower() not in self.ALLOWED_COUNTRIES:
                continue

            title = str(item.get("title", "")).strip()
            source_url = str(item.get("source_url", "")).strip()

            if not title or not source_url:
                continue

            results.append({
                "title": title,
                "country": (
                    "Egypt" if item_country.lower() == "egypt"
                    else "Saudi Arabia"
                ),
                "organization": item.get("organization", ""),
                "deadline": item.get("deadline", ""),
                "description": item.get("description", ""),
                "source_url": source_url,
                "status": "requires_verification"
            })

        return AgentResult(
            agent=self.name,
            ok=True,
            output={
                "opportunities": results,
                "count": len(results),
                "supported_countries": ["Egypt", "Saudi Arabia"]
            },
            message=(
                f"Processed {len(results)} eligible opportunities. "
                "Verify each opportunity against its original source."
            ),
            sources=[item["source_url"] for item in results]
        )
