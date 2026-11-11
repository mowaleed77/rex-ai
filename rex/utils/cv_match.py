"""CV / interests -> course recommendations (rule-based, works offline, English + Arabic).

Nothing here is stored: the text is analysed in memory and only the recommendations are returned.
Scoring: every course gets weighted keywords (title x3, learning outcomes / careers x2, description x1);
words that appear in many courses count less. Common skill names in English and Arabic are mapped to
the same concept first (e.g. "بايثون" and "python"), so an Arabic CV matches the English catalog.
"""
from __future__ import annotations

import io
import math
import re
import zipfile
from xml.etree import ElementTree

MAX_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 15
SUPPORTED = (".txt", ".md", ".pdf", ".docx")

# phrase (lower-case, EN or AR) -> concept words added to the CV's vocabulary
ALIASES = {
    "بايثون": "python", "بايثن": "python", "تحليل البيانات": "data analysis analytics",
    "تحليل بيانات": "data analysis analytics", "بيانات": "data", "اكسل": "excel", "إكسل": "excel",
    "تعلم الآلة": "machine learning", "تعلم الالة": "machine learning", "الذكاء الاصطناعي": "ai artificial intelligence",
    "ذكاء اصطناعي": "ai artificial intelligence", "تسويق": "marketing", "التسويق": "marketing",
    "سوشيال ميديا": "social media marketing", "وسائل التواصل": "social media marketing",
    "الأمن السيبراني": "cybersecurity security", "امن المعلومات": "cybersecurity security",
    "أمن المعلومات": "cybersecurity security", "برمجة": "programming development",
    "تطوير الويب": "web development react javascript", "جافاسكربت": "javascript", "ويب": "web",
    "إدارة المشاريع": "project management", "ادارة المشاريع": "project management",
    "إدارة مشروعات": "project management", "مدير مشروع": "project manager management",
    "الرعاية الصحية": "healthcare health", "صحة": "health", "مستشفى": "healthcare clinical",
    "تمريض": "healthcare clinical", "طبيب": "healthcare clinical", "صيدلة": "healthcare clinical",
    "محاسبة": "finance business analysis excel", "مالية": "finance business analysis",
    "ذكاء الأعمال": "business intelligence bi dashboards",
    "sql": "sql data database", "power bi": "dashboards bi data visualization",
    "tableau": "dashboards bi data visualization", "pandas": "python data analysis",
    "numpy": "python data", "tensorflow": "machine learning deep learning",
    "pytorch": "machine learning deep learning", "scikit": "machine learning",
    "chatgpt": "generative ai llm", "prompt": "generative ai llm", "llm": "generative ai llm",
    "react": "react web development javascript front-end", "html": "web development front-end",
    "css": "web development front-end", "javascript": "javascript web development",
    "network": "cybersecurity security networking", "penetration": "cybersecurity security",
    "seo": "digital marketing", "social media": "social media marketing digital marketing",
    "advertising": "marketing digital", "pmp": "project management", "agile": "project management",
    "scrum": "project management", "ehr": "healthcare informatics", "nursing": "healthcare clinical",
    "accounting": "finance business analysis excel", "spreadsheet": "excel business analysis",
}
STOP = set("""a an the and or of in on at to for with from by is are was were be been this that it as at we you i my
our your their he she they his her about into over under more most very can will have has had not no yes
experience skills skill years year work worked working responsible project projects team company university
bachelor degree education curriculum vitae resume cv email phone address name date new etc using use used
""".split())
_WORD = re.compile(r"[a-z][a-z+#.\-]{1,}|[؀-ۿ]{2,}")
_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?|سنوات|سنة|سنين)", re.I)


# ------------------------------------------------------------------ reading files
def extract_text(data: bytes, filename: str) -> str:
    """Plain text from .txt/.md/.pdf/.docx. Raises ValueError with a user-presentable message."""
    name = (filename or "").lower()
    if len(data) > MAX_BYTES:
        raise ValueError("That file is larger than 5 MB. Please upload a smaller one.")
    if name.endswith((".txt", ".md")):
        for enc in ("utf-8-sig", "utf-16", "cp1256", "latin-1"):
            try:
                return data.decode(enc)
            except (UnicodeDecodeError, UnicodeError):
                continue
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise ValueError("Reading PDFs needs the 'pypdf' package (pip install pypdf), "
                             "or paste the text instead.") from error
        try:
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:MAX_PDF_PAGES])
        except Exception as error:
            raise ValueError("Could not read that PDF. Paste the text instead.") from error
        if not text.strip():
            raise ValueError("That PDF has no selectable text (it may be a scan). Paste the text instead.")
        return text
    if name.endswith(".docx"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = z.read("word/document.xml")
            root = ElementTree.fromstring(xml)
        except Exception as error:
            raise ValueError("Could not read that Word file. Paste the text instead.") from error
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paras = ["".join(t.text or "" for t in p.iter(ns + "t")) for p in root.iter(ns + "p")]
        return "\n".join(paras)
    raise ValueError("Unsupported file type. Use " + ", ".join(SUPPORTED) + " or paste the text.")


# ----------------------------------------------------------------------- matching
def _tokens(text: str) -> list[str]:
    return [w.strip(".-") for w in _WORD.findall((text or "").lower()) if w.strip(".-") not in STOP]


def _expand(text: str) -> list[str]:
    low = (text or "").lower()
    extra: list[str] = []
    for phrase, concept in ALIASES.items():
        if phrase in low:
            extra += concept.split()
    return _tokens(low) + extra


def _course_keywords(course: dict) -> dict[str, float]:
    weights: dict[str, float] = {}

    def add(text: str, w: float):
        for tok in _tokens(str(text)):
            weights[tok] = max(weights.get(tok, 0), w)

    add(course.get("title_en", ""), 3)
    add(course.get("title_ar", ""), 3)
    add(course.get("department", ""), 1.5)
    for item in (course.get("learning_outcomes") or []):
        add(item, 2)
    for item in (course.get("career_opportunities") or []):
        add(item, 2)
    add(course.get("description", ""), 1)
    add(course.get("target_audience", ""), 1)
    return weights


def detect_years(text: str) -> int | None:
    found = [int(m) for m in _YEARS.findall(text or "") if 0 < int(m) < 45]
    return max(found) if found else None


def suggest_level(years: int | None) -> str:
    if years is None or years < 1:
        return "Beginner"
    return "Intermediate" if years < 4 else "Advanced"


def recommend(text: str, courses: list[dict], top: int = 3, arabic: bool = False) -> dict:
    """Return {'level','years','skills','recommendations':[{course,score,matched,reason}],'message'}."""
    text = (text or "").strip()
    if len(text) < 15:
        return {"ok": False, "message": "Please paste a few lines about your skills, studies or interests."
                if not arabic else "من فضلك اكتب بضعة أسطر عن مهاراتك أو دراستك أو اهتماماتك."}
    cv = _expand(text)
    cv_set = set(cv)
    kws = {c["id"]: _course_keywords(c) for c in courses}
    n = max(len(courses), 1)
    df: dict[str, int] = {}
    for k in kws.values():
        for tok in k:
            df[tok] = df.get(tok, 0) + 1
    idf = {tok: 1 + math.log(n / d) for tok, d in df.items()}

    years = detect_years(text)
    level = suggest_level(years)
    scored = []
    for course in courses:
        weights = kws[course["id"]]
        hits = {tok: weights[tok] * idf[tok] for tok in cv_set if tok in weights}
        score = sum(hits.values())
        if score <= 0:
            continue
        if course.get("level") == level:
            score *= 1.15
        matched = [tok for tok, _ in sorted(hits.items(), key=lambda kv: -kv[1])][:6]
        scored.append((score, course, matched))
    scored.sort(key=lambda row: -row[0])
    best = scored[0][0] if scored else 1
    recs = []
    for score, course, matched in scored[:top]:
        title = course.get("title_ar") if arabic and course.get("title_ar") else course.get("title_en")
        if arabic:
            reason = f"تتطابق مع: {', '.join(matched)}"
        else:
            reason = f"Matches your background in: {', '.join(matched)}"
        if course.get("level") != level:
            reason += (" · مستوى الدورة " if arabic else " · course level ") + str(course.get("level"))
        recs.append({"course": course, "title": title, "score": round(100 * score / best),
                     "matched": matched, "reason": reason})
    skills = sorted({tok for tok in cv_set if any(tok in kws[c["id"]] for c in courses)})[:12]
    ok = bool(recs)
    return {"ok": ok, "level": level, "years": years, "skills": skills, "recommendations": recs,
            "message": "" if ok else ("لم أجد دورة مناسبة؛ جرّب ذكر مهارات أو مجالات أكثر." if arabic
                                      else "I could not match your text to a course. Try naming skills or fields.")}
