"""Discovery layer for the RFP agent: online search -> extraction -> raw opportunity dicts.

The RfpAgent (rfp_agent.py) then applies the strict filters. Nothing here decides
what is accepted; it only finds candidates and pulls out whatever fields it can.
"""
import os
import re
from datetime import date, datetime
from urllib.parse import urlparse

import requests

try:  # read TAVILY_API_KEY from .env when python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ----------------------------------------------------------------- dates
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_DATE_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
)


def parse_date(value):
    """Parse many real-world date formats (dd/mm/yyyy preferred). None if unparseable."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).translate(_ARABIC_DIGITS).strip()
    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text, flags=re.I).replace("Sept ", "Sep ")
    for candidate in (text, text[:10]):
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


# --------------------------------------------------------------- country
_COUNTRY_PATTERNS = {
    "Egypt": re.compile(r"\begypt(?:ian)?\b|\bcairo\b|مصر|القاهرة", re.I),
    "Saudi Arabia": re.compile(r"\bsaudi\b|\bksa\b|\briyadh\b|\bjeddah\b|السعودية|الرياض|جدة", re.I),
}


def infer_country(text="", url=""):
    """Country from evidence (domain TLD + text). Returns None if none or ambiguous."""
    found = set()
    host = (urlparse(url).hostname or "").lower()
    if host.endswith(".eg"):
        found.add("Egypt")
    if host.endswith(".sa"):
        found.add("Saudi Arabia")
    for name, pattern in _COUNTRY_PATTERNS.items():
        if pattern.search(text or ""):
            found.add(name)
    return next(iter(found)) if len(found) == 1 else None


# ---------------------------------------------------------------- search
class TavilySearch:
    """Thin wrapper over the Tavily search API (https://tavily.com). Needs TAVILY_API_KEY.

    Any object with `.available` and `.search(query, include_domains=None, max_results=8)`
    returning [{"title", "url", "content"}] can replace this (SerpAPI, Serper, Bing...).
    """
    URL = "https://api.tavily.com/search"

    def __init__(self, api_key=None, timeout=25):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.timeout = timeout

    @property
    def available(self):
        return bool(self.api_key)

    def search(self, query, include_domains=None, max_results=8):
        print(f"DEBUG: Calling Tavily Live Search with query: {query}")
        payload = {"query": query, "search_depth": "advanced", "max_results": max_results}
        if include_domains:
            payload["include_domains"] = include_domains
        resp = requests.post(
            self.URL, json=payload, timeout=self.timeout,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        resp.raise_for_status()
        return resp.json().get("results", [])


PORTAL_DOMAINS = {
    "Egypt": ["etenders.gov.eg"],
    "Saudi Arabia": ["etimad.sa"],
}


def build_queries(country, year=None):
    year = year or date.today().year
    if country == "Egypt":
        return [
            f"training services tender Egypt {year}",
            f"RFP education training Egypt {year}",
            f"IT software training RFQ Egypt {year}",
            "مناقصة تدريب مصر",
        ]
    return [
        f"training services tender Saudi Arabia {year}",
        f"RFP education training KSA {year}",
        f"digital transformation training RFQ Saudi Arabia {year}",
        "منافسة تدريب المملكة العربية السعودية",
    ]


# ------------------------------------------------------------ extraction
_DATE_PATTERN = (
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
    r"|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\.?,?\s+\d{4}"
    r"|[A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})"
)
_DEADLINE_RE = re.compile(
    r"(?:deadline|closing date|closes?|due date|submission date|last date|آخر موعد|الموعد النهائي)\D{0,25}"
    + _DATE_PATTERN, re.I)
_PUBLISHED_RE = re.compile(
    r"(?:published|posted|publication date|issued|date of issue|تاريخ النشر)\D{0,25}" + _DATE_PATTERN, re.I)


def extract_opportunity(result, extractor=None):
    """Turn one search result into an opportunity dict.

    `extractor(text, url) -> dict` is an optional LLM hook that can fill organization,
    deadline, eligibility, category, etc. It can NOT set country or source_url: country is
    always taken from evidence (domain/text) so an LLM cannot talk its way past the filter.
    """
    title = (result.get("title") or "").strip()
    url = (result.get("url") or "").strip()
    content = (result.get("content") or "").strip()
    text = f"{title}\n{content}"

    deadline = _DEADLINE_RE.search(text)
    published = _PUBLISHED_RE.search(text)
    opp = {
        "title": title,
        "source_url": url,
        "description": content[:600],
        "organization": "",
        "country": infer_country(text, url) or "",
        "deadline": deadline.group(1) if deadline else "",
        "publication_date": published.group(1) if published else "",
        "category": "",
        "eligibility": "",
        "documents": [],
    }
    if extractor and opp["country"]:  # skip the LLM for items already failing the country rule
        try:
            extra = extractor(text, url) or {}
            opp.update({k: v for k, v in extra.items()
                        if v and k not in ("country", "source_url")})
        except Exception:  # LLM failure must never kill the pipeline
            pass
    return opp


def discover(searcher, countries=("Egypt", "Saudi Arabia"), extractor=None, max_results=8):
    """Run all queries for each country. Returns (candidates, errors)."""
    candidates, errors, seen_urls = [], [], set()
    for country in countries:
        jobs = [(q, None) for q in build_queries(country)]
        jobs += [("training OR education OR IT tender", PORTAL_DOMAINS[country])]
        for query, domains in jobs:
            try:
                results = searcher.search(query, include_domains=domains, max_results=max_results)
            except Exception as exc:
                errors.append(f"{country} / {query!r}: {exc}")
                continue
            for res in results:
                url = (res.get("url") or "").strip().rstrip("/")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append(extract_opportunity(res, extractor))
    return candidates, errors