"""LLM extraction hook for RfpAgent. Reuses the SAME settings as the REX assistant (.env):

    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL      (any OpenAI-compatible endpoint: Groq, Gemini, ...)

Falls back to GROQ_API_KEY / GROQ_MODEL if the LLM_* variables are absent.

Usage:
    agent = RfpAgent(extractor=GroqExtractor())
It only fills organization / deadline / publication_date / category / eligibility /
documents. Country and source_url are never taken from the LLM (the agent ignores them).
"""
import json
import os
import re
import time

import requests

try:  # load .env if python-dotenv is installed (the REX assistant probably already does this)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ALLOWED = ("organization", "deadline", "publication_date", "category", "eligibility", "documents")

SYSTEM = (
    "You extract tender/RFP details from a web search snippet. Reply with ONE JSON object "
    "with exactly these keys: organization, deadline, publication_date, category, eligibility, "
    "documents. Rules: use ONLY facts stated in the text; use an empty string (or [] for "
    "documents) when a fact is not stated; never guess. Dates as YYYY-MM-DD when the full date "
    "is given. category is a short label such as 'IT training' or 'technical training'."
)


def _parse_json(content):
    try:
        return json.loads(content)
    except ValueError:
        match = re.search(r"\{.*\}", content or "", re.S)  # model wrapped JSON in prose/fences
        return json.loads(match.group(0)) if match else {}


class GroqExtractor:
    def __init__(self, api_key=None, base_url=None, model=None, timeout=30, max_chars=3000):
        env = os.environ.get
        self.api_key = api_key or env("LLM_API_KEY") or env("GROQ_API_KEY")
        base = base_url or env("LLM_BASE_URL") or "https://api.groq.com/openai/v1"
        self.url = base.rstrip("/") + "/chat/completions"
        self.model = model or env("LLM_MODEL") or env("GROQ_MODEL") or "llama-3.3-70b-versatile"
        self.timeout = timeout
        self.max_chars = max_chars

    def _post(self, body, headers):
        for attempt in range(2):  # one retry on rate limit (free tiers are tight)
            resp = requests.post(self.url, json=body, headers=headers, timeout=self.timeout)
            if resp.status_code == 429 and attempt == 0:
                time.sleep(float(resp.headers.get("retry-after", 2)))
                continue
            return resp
        return resp

    def __call__(self, text, url=""):
        if not self.api_key:
            return {}
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"URL: {url}\n\n{text[:self.max_chars]}"},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        resp = self._post(body, headers)
        if resp.status_code == 400:  # some endpoints reject response_format: retry without it
            body.pop("response_format")
            resp = self._post(body, headers)
        resp.raise_for_status()
        data = _parse_json(resp.json()["choices"][0]["message"]["content"])
        return {k: data[k] for k in ALLOWED if data.get(k)}


LLMExtractor = GroqExtractor  # generic alias