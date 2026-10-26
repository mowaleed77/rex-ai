
from .base import Agent, AgentResult


class RfpAgent(Agent):
    name = "rfp_research"

    ALLOWED_COUNTRIES = {"egypt", "saudi arabia"}

    def run(self, task: dict) -> AgentResult:
        opportunities = task.get("opportunities", [])

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

            country = str(item.get("country", "")).strip()
            if country.lower() not in self.ALLOWED_COUNTRIES:
                continue

            title = str(item.get("title", "")).strip()
            source_url = str(item.get("source_url", "")).strip()

            if not title or not source_url:
                continue

            results.append({
                "title": title,
                "country": (
                    "Egypt" if country.lower() == "egypt"
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
            sources=[
                item["source_url"] for item in results
            ]
        )
