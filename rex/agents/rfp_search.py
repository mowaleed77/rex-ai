"""Coordinator for live RFP discovery."""
from rex.agents.rfp_sources import TavilySearch, discover
from rex.rag.llm import load_dotenv


def search_rfps(
    country: str,
    topic: str = "education training digital transformation",
    searcher=None,
    extractor=None,
    max_results: int = 5,
) -> dict:
    """Search one supported country and preserve partial-error information."""
    load_dotenv()
    searcher = searcher if searcher is not None else TavilySearch()

    if getattr(searcher, "available", None) is False:
        return {
            "ok": False,
            "partial": False,
            "opportunities": [],
            "errors": ["Search backend is unavailable. Configure TAVILY_API_KEY."],
            "message": "Search backend is unavailable. Configure TAVILY_API_KEY.",
        }

    try:
        opportunities, errors = discover(
            searcher=searcher,
            countries=(country,),
            extractor=extractor,
            max_results=max_results,
            topic=topic,
        )
    except Exception as exc:
        message = f"Live RFP search failed for {country}: {exc}"
        return {
            "ok": False,
            "partial": False,
            "opportunities": [],
            "errors": [message],
            "message": message,
        }

    ok = bool(opportunities) or not errors
    partial = bool(opportunities and errors)
    if errors and opportunities:
        message = (
            f"Found {len(opportunities)} candidates for {country}, "
            f"but {len(errors)} search/extraction operation(s) failed."
        )
    elif errors:
        message = f"No candidates found for {country}; {len(errors)} operation(s) failed."
    else:
        message = f"Found {len(opportunities)} candidates for {country}."

    return {
        "ok": ok,
        "partial": partial,
        "opportunities": opportunities,
        "errors": errors,
        "message": message + " Verify each opportunity against its official source.",
    }
