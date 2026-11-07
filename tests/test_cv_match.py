import io
import zipfile

import pytest

from rex.utils import catalog, cv_match

COURSES = catalog.load_courses()
pytestmark = pytest.mark.skipif(not COURSES, reason="needs data/courses.json")


def top(text, arabic=False):
    r = cv_match.recommend(text, COURSES, arabic=arabic)
    assert r["ok"], r
    return r["recommendations"][0]["course"]["id"], r


def titles(r):
    return [x["course"]["title_en"] for x in r["recommendations"]]


def test_python_cv_recommends_data_course():
    _, r = top("Graduate with 2 years experience. Python, pandas, SQL and Power BI dashboards.")
    assert "Python for Data Analysis" in titles(r)[:2]
    assert r["level"] == "Intermediate" and r["years"] == 2
    assert r["recommendations"][0]["score"] == 100


def test_arabic_cv_matches_marketing():
    cid, r = top("خبرة 5 سنوات في التسويق وإدارة صفحات السوشيال ميديا", arabic=True)
    assert "Digital Marketing" in next(c["title_en"] for c in COURSES if c["id"] == cid)
    assert r["level"] == "Advanced"
    assert any("؀" <= ch <= "ۿ" for ch in r["recommendations"][0]["title"])


def test_security_interest():
    _, r = top("I enjoy securing networks and penetration testing")
    assert titles(r)[0] == "Cybersecurity Essentials" and r["level"] == "Beginner"


def test_too_short_text_is_rejected_politely():
    r = cv_match.recommend("hi", COURSES)
    assert not r["ok"] and r["message"]


def test_no_match_returns_message():
    r = cv_match.recommend("zzzz qqqq xxxx vvvv wwww yyyy", COURSES)
    assert not r["ok"] and r["message"]


def test_extract_txt_and_docx():
    assert "Python" in cv_match.extract_text("I know Python".encode(), "cv.txt")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml",
                   '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                   "<w:p><w:r><w:t>Marketing manager</w:t></w:r></w:p></w:body></w:document>")
    assert "Marketing manager" in cv_match.extract_text(buf.getvalue(), "cv.docx")


def test_extract_rejects_bad_files():
    with pytest.raises(ValueError):
        cv_match.extract_text(b"x", "cv.exe")
    with pytest.raises(ValueError):
        cv_match.extract_text(b"not a zip", "cv.docx")
    with pytest.raises(ValueError):
        cv_match.extract_text(b"x" * (cv_match.MAX_BYTES + 1), "cv.txt")
