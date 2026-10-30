import json
import os
from rex.agents.rfp_sources import TavilySearch
from rex.rag.llm import load_dotenv


def search_rfps(country: str, topic: str, searcher=None, extractor=None) -> dict:
    load_dotenv()

    # Fall back to internal TavilySearch client if not provided
    searcher = searcher if searcher is not None else TavilySearch()

    try:
        # Query Tavily directly for real-time RFP results
        query = f"education training digital transformation RFP tender {country}"
        raw_results = searcher.search(query, max_results=5)

        if not raw_results:
            return {
                "ok": True,
                "opportunities": [],
                "message": f"No live search results found for {country}.",
            }

        valid_opportunities = []

        for item in raw_results:
            if not isinstance(item, dict):
                continue

            title = str(item.get("title", "")).strip()
            source_url = str(item.get("url", item.get("source_url", ""))).strip()

            if not title or not source_url:
                continue

            valid_opportunities.append({
                "title": title,
                "country": country,
                "organization": item.get("organization", "Official Tender Portal"),
                "deadline": item.get("deadline", ""),
                "description": item.get("content", item.get("description", "")),
                "source_url": source_url,
                "category": "Education & Training",
            })

        return {
            "ok": True,
            "opportunities": valid_opportunities,
            "message": (
                f"Live search returned {len(valid_opportunities)} results for {country}. "
                "Verify each source against its official website."
            ),
        }

    except Exception as error:
        return {
            "ok": False,
            "opportunities": [],
            "message": f"Live RFP search failed: {error}",
        }