"""Read access to the academy course catalog (data/courses.json) shared by the agents and the UI."""
from __future__ import annotations

import json
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "courses.json"

LEVEL_AR = {"Beginner": "مبتدئ", "Intermediate": "متوسط", "Advanced": "متقدم"}
FORMAT_AR = {"online": "أونلاين", "onsite": "حضوري", "hybrid": "مدمج"}


def load_courses(path: Path | str | None = None) -> list[dict]:
    try:
        return json.loads(Path(path or DATA_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def find_course(query: str, courses: list[dict] | None = None) -> dict | None:
    """Find a course by id or by (part of) its English / Arabic title."""
    courses = courses if courses is not None else load_courses()
    q = (query or "").strip().casefold()
    if not q:
        return None
    for c in courses:
        if q == str(c.get("id", "")).casefold() or q == str(c.get("title_en", "")).casefold() \
                or q == str(c.get("title_ar", "")).casefold():
            return c
    for c in courses:
        if q in str(c.get("title_en", "")).casefold() or q in str(c.get("title_ar", "")):
            return c
    return None


def find_course_in_text(text: str, courses: list[dict] | None = None) -> dict | None:
    """Course whose title (or id such as C03) is mentioned inside a longer sentence."""
    courses = courses if courses is not None else load_courses()
    low = (text or "").casefold()
    words = set(low.replace(",", " ").split())
    best = None
    for c in courses:
        en, ar = str(c.get("title_en", "")).casefold(), str(c.get("title_ar", ""))
        if (en and en in low) or (ar and ar in text) or str(c.get("id", "")).casefold() in words:
            if best is None or len(en) > len(str(best.get("title_en", ""))):
                best = c
    return best


def marketing_view(course: dict) -> dict:
    """Course dict in the shape the Marketing agent expects (both languages included)."""
    return {
        "title": course.get("title_en", ""),
        "title_ar": course.get("title_ar", ""),
        "description": course.get("description", ""),
        "description_ar": course.get("description_ar", ""),
        "duration_hours": course.get("duration_hours"),
        "price": course.get("price_egp"),
        "promotion": course.get("promotion", ""),
        "promotion_ar": course.get("promotion_ar", ""),
        "level": course.get("level", ""),
        "formats": course.get("formats", []),
        "target_audience": course.get("target_audience", ""),
        "target_audience_ar": course.get("target_audience_ar", ""),
        "learning_outcomes": course.get("learning_outcomes", []),
        "learning_outcomes_ar": course.get("learning_outcomes_ar", []),
        "career_opportunities": course.get("career_opportunities", []),
        "career_opportunities_ar": course.get("career_opportunities_ar", []),
        "accreditation_framework": course.get("accreditation_framework", ""),
        "source": f"data/courses.json#{course.get('id', '')}",
    }
