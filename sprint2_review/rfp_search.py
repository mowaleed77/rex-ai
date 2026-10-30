
import json
import os
import urllib.error
import urllib.request

from rex.rag.llm import load_dotenv


def search_rfps(country: str, topic: str) -> dict:
    load_dotenv()

    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    model = os.environ.get("RFP_SEARCH_MODEL", "openai/gpt-oss-20b")

    if not api_key or "api.groq.com" not in base_url:
        return {
            "ok": False,
            "opportunities": [],
            "message": "Configure a Groq API key and Groq base URL to enable live search.",
        }

    prompt = (
        f"Research real, currently open education, training, or technology "
        f"RFPs and tenders in {country} related to: {topic}. "
        "Use web browser search. Return only a JSON object with an "
        "'opportunities' array. Each item must contain title, country, "
        "organization, deadline, description, and source_url. "
        "Use original official source URLs. Do not invent opportunities. "
        "If no verified opportunities are found, return an empty array."
    )

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"type": "browser_search"}],
        "tool_choice": "required",
        "temperature": 0.1,
    }).encode("utf-8")

    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "REX-AI/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))

        content = data["choices"][0]["message"]["content"]

        if not isinstance(content, str):
            raise ValueError("The search response did not contain text.")

        start = content.find("{")
        end = content.rfind("}")

        if start == -1 or end < start:
            raise ValueError("The search response did not contain JSON.")

        result = json.loads(content[start:end + 1])
        opportunities = result.get("opportunities", [])

        if not isinstance(opportunities, list):
            raise ValueError("The opportunities field must be a list.")

        valid_opportunities = []

        for item in opportunities:
            if not isinstance(item, dict):
                continue

            title = str(item.get("title", "")).strip()
            source_url = str(item.get("source_url", "")).strip()

            if not title or not source_url:
                continue

            valid_opportunities.append(item)

        return {
            "ok": True,
            "opportunities": valid_opportunities,
            "message": (
                f"Live search returned {len(valid_opportunities)} results. "
                "Verify each source against its official website."
            ),
        }

    except urllib.error.HTTPError as error:
        print("HTTP status:", error.code)
        print("Retry-After:", error.headers.get("Retry-After"))
        print(
            "Remaining requests:",
            error.headers.get("x-ratelimit-remaining-requests"),
        )
        print(
            "Remaining tokens:",
            error.headers.get("x-ratelimit-remaining-tokens"),
        )
        print(
            "Request reset:",
            error.headers.get("x-ratelimit-reset-requests"),
        )
        print(
            "Token reset:",
            error.headers.get("x-ratelimit-reset-tokens"),
        )

        try:
            response_body = error.read().decode("utf-8", errors="replace")
        except Exception:
            response_body = "Could not read the error response."

        print("Response body:", response_body)

        return {
            "ok": False,
            "opportunities": [],
            "message": f"Live RFP search failed: HTTP {error.code}",
        }

    except (
        urllib.error.URLError,
        TimeoutError,
        KeyError,
        IndexError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        return {
            "ok": False,
            "opportunities": [],
            "message": f"Live RFP search failed: {error}",
        }
