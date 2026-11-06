"""Discovery layer for the RFP agent: online search -> extraction -> raw opportunity dicts.

This module discovers and extracts candidates only. RfpAgent applies the strict
geographic, relevance, deadline, and duplicate filters.
"""
import logging
import os
import re
from datetime import date, datetime
from urllib.parse import urlparse

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Arabic-Indic and Eastern Arabic-Indic digits -> Western digits.
_DIGIT_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)
_DATE_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y",
    "%B %d %Y", "%b %d %Y",
)


def parse_date(value):
    """Parse common English/Arabic-numeral date formats; return date or None."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).translate(_DIGIT_TRANSLATION).strip()
    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text, flags=re.I)
    text = text.replace("Sept ", "Sep ")
    for candidate in (text, text[:10]):
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


_COUNTRY_PATTERNS = {
    "Egypt": re.compile(r"\begypt(?:ian)?\b|\bcairo\b|مصر|القاهرة", re.I),
    "Saudi Arabia": re.compile(
        r"\bsaudi\b|\bksa\b|\briyadh\b|\bjeddah\b|السعودية|المملكة\s+العربية\s+السعودية|الرياض|جدة",
        re.I,
    ),
}


def infer_country(text="", url=""):
    """Infer a country only when evidence points to exactly one supported country."""
    found = set()
    host = (urlparse(url).hostname or "").lower()
    if host.endswith(".eg"):
        found.add("Egypt")
    if host.endswith(".sa"):
        found.add("Saudi Arabia")
    content = str(text or "")
    for name, pattern in _COUNTRY_PATTERNS.items():
        if pattern.search(content):
            found.add(name)
    return next(iter(found)) if len(found) == 1 else None


class TavilySearch:
    """Thin Tavily client. A compatible injected searcher can replace it."""
    URL = "https://api.tavily.com/search"

    def __init__(self, api_key=None, timeout=25):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.timeout = timeout

    @property
    def available(self):
        return bool(self.api_key)

    def search(self, query, include_domains=None, max_results=8):
        if not self.api_key:
            raise RuntimeError("Tavily API key is not configured (TAVILY_API_KEY).")
        payload = {
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
        }
        if include_domains:
            payload["include_domains"] = include_domains
        response = requests.post(
            self.URL,
            json=payload,
            timeout=self.timeout,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])


PORTAL_DOMAINS = {
    "Egypt": ["etenders.gov.eg"],
    "Saudi Arabia": ["etimad.sa"],
}


def build_queries(country, year=None, topic=None):
    """Build country-specific queries; optional topic augments the default queries."""
    if country not in PORTAL_DOMAINS:
        raise ValueError(f"Unsupported discovery country: {country}")
    year = year or date.today().year
    topic = " ".join(str(topic or "").split()).strip()
    topic_suffix = f" {topic}" if topic else ""
    if country == "Egypt":
        queries = [
            f"training services tender Egypt {year}",
            f"RFP education training Egypt {year}",
            f"IT software training RFQ Egypt {year}",
            "مناقصة تدريب مصر",
        ]
    else:
        queries = [
            f"training services tender Saudi Arabia {year}",
            f"RFP education training KSA {year}",
            f"digital transformation training RFQ Saudi Arabia {year}",
            "منافسة تدريب المملكة العربية السعودية",
        ]
    if topic:
        queries = [f"{query}{topic_suffix}" for query in queries]
    return queries


_DATE_PATTERN = (
    r"(\d{4}-\d{1,2}-\d{1,2}|"
    r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|"
    r"\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\.?,?\s+\d{4}|"
    r"[A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})"
)
_DEADLINE_RE = re.compile(
    r"(?:deadline|closing date|closes?|due date|submission date|last date|آخر موعد|الموعد النهائي)"
    r"\D{0,40}" + _DATE_PATTERN,
    re.I,
)
_PUBLISHED_RE = re.compile(
    r"(?:published|posted|publication date|issued|date of issue|تاريخ النشر)"
    r"\D{0,40}" + _DATE_PATTERN,
    re.I,
)


def extract_opportunity(result, extractor=None, extraction_errors=None):
    """Convert a search result into a candidate; extractor cannot override provenance."""
    title = str(result.get("title") or "").strip()
    url = str(result.get("url") or "").strip()
    content = str(result.get("content") or "").strip()
    text = f"{title}\n{content}"

    deadline_match = _DEADLINE_RE.search(text)
    published_match = _PUBLISHED_RE.search(text)
    opportunity = {
        "title": title,
        "source_url": url,
        "description": content[:600],
        "organization": "",
        "country": infer_country(text, url) or "",
        "deadline": deadline_match.group(1) if deadline_match else "",
        "publication_date": published_match.group(1) if published_match else "",
        "category": "",
        "eligibility": "",
        "documents": [],
    }
    if extractor and opportunity["country"]:
        try:
            extra = extractor(text, url) or {}
            if not isinstance(extra, dict):
                raise TypeError("Extractor must return a dictionary.")
            protected = {"country", "source_url", "url"}
            opportunity.update({
                key: value for key, value in extra.items()
                if value not in (None, "", [], {}) and key not in protected
            })
        except Exception as exc:
            message = f"Extractor failed for {url or title or 'unknown result'}: {exc}"
            if extraction_errors is not None:
                extraction_errors.append(message)
            logger.exception(message)
    return opportunity


def discover(
    searcher,
    countries=("Egypt", "Saudi Arabia"),
    extractor=None,
    max_results=8,
    topic=None,
):
    """Run country queries; return (candidates, errors), retaining partial failures."""
    candidates, errors, seen_urls = [], [], set()
    for country in countries:
        if country not in PORTAL_DOMAINS:
            errors.append(f"Unsupported discovery country: {country}")
            continue
        jobs = [(query, None) for query in build_queries(country, topic=topic)]
        jobs.append((f"training OR education OR IT tender {topic or ''}".strip(),
                     PORTAL_DOMAINS[country]))
        for query, domains in jobs:
            try:
                results = searcher.search(
                    query,
                    include_domains=domains,
                    max_results=max_results,
                )
                if not isinstance(results, list):
                    raise TypeError("Search backend must return a list of results.")
            except Exception as exc:
                errors.append(f"{country} / {query!r}: {exc}")
                continue
            for result in results:
                if not isinstance(result, dict):
                    errors.append(f"{country} / {query!r}: ignored malformed search result")
                    continue
                url = str(result.get("url") or "").strip().rstrip("/")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates.append(extract_opportunity(
                    result, extractor, extraction_errors=errors
                ))
    return candidates, errors
