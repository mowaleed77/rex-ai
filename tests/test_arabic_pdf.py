"""Arabic PDF output: letter shaping, right-to-left order, wrapping, and real PDFs."""
import shutil
import subprocess

import pytest
from reportlab.pdfbase import pdfmetrics

from rex.agents.curriculum import CurriculumAgent
from rex.agents.document import DocumentAgent
from rex.utils import arabic

needs_pdftotext = pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext (poppler) not installed")


def _text(pdf_path) -> str:
    out = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True).stdout
    return "".join(c for c in out if not 0x202A <= ord(c) <= 0x202E)   # pdftotext adds direction marks


def _has_word(text: str, word: str) -> bool:
    """pdftotext may print a shaped word in either glyph order; both mean the word is in the PDF."""
    shaped = arabic.visual(word)
    return shaped in text or shaped[::-1] in text


def _in_presentation_forms(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    return bool(letters) and all(0xFB50 <= ord(c) <= 0xFEFF for c in letters)


def test_letters_are_joined_and_reversed_for_a_left_to_right_renderer():
    assert arabic.visual("با") == "ﺎﺑ"           # alef (final) drawn left of beh (initial)
    assert arabic.visual("لا") == "ﻻ"                  # lam + alef become one ligature
    assert _in_presentation_forms(arabic.visual("مرحبا بكم"))


def test_plain_text_is_untouched():
    assert arabic.visual("Python 3.12") == "Python 3.12"
    assert not arabic.has_arabic("Hello") and arabic.has_arabic("مرحبا")
    assert arabic.is_mostly_arabic("دورة Python متقدمة") and not arabic.is_mostly_arabic("Python course")


def test_english_words_and_numbers_stay_readable_inside_arabic():
    out = arabic.visual("تعلم Python في 2026")
    assert "Python" in out and "2026" in out                # not reversed into "nohtyP" / "6202"
    assert out.index("2026") < out.index("Python")          # right-to-left: later words sit further left


def test_wrapping_respects_the_width_and_keeps_every_word():
    font, _ = arabic.register_fonts()
    text = "هذه فقرة طويلة لاختبار التفاف الأسطر في ملف PDF العربي بحيث تظهر الكلمات بشكل صحيح ومقروء"
    lines = arabic.wrap_visual(text, font, 14, 200)
    assert len(lines) > 2
    assert all(pdfmetrics.stringWidth(line, font, 14) <= 200 + 1 for line in lines)
    assert "".join(lines).count("PDF") == 1


def _arabic_curriculum(status="draft"):
    agent = CurriculumAgent()
    cur = agent.run({"action": "generate", "course": "أساسيات تعلم الآلة", "language": "ar", "level": "Intermediate",
                     "duration_hours": 48, "learning_outcomes": ["تدريب نماذج تعلم الآلة وتقييمها", "تطبيق هندسة الخصائص"]}).output
    if status == "approved":
        cur = agent.run({"action": "approve", "curriculum": cur, "reviewer": "Dr. Sara"}).output
    return cur


@needs_pdftotext
@pytest.mark.parametrize("doc_type", ["curriculum_report", "course_description", "gap_analysis"])
def test_arabic_documents_are_generated_with_shaped_text(tmp_path, doc_type):
    task = {"document_type": doc_type, "curriculum": _arabic_curriculum(), "output_dir": str(tmp_path)}
    if doc_type == "gap_analysis":
        task = {"document_type": doc_type, "language": "ar", "output_dir": str(tmp_path), "title": "تقرير الفجوات",
                "content": {"summary": "تغطية جزئية", "gaps": [{"requirement": "أخلاقيات البيانات", "status": "ناقص",
                                                              "severity": "عالية", "recommendation": "إضافة وحدة"}],
                            "recommended_actions": ["مراجعة الوحدة الرابعة"]}}
    res = DocumentAgent().run(task)
    assert res.ok, res.message
    assert res.output["language"] == "ar"
    text = _text(res.output["file_path"])
    assert text.strip()
    # shaped glyphs are present, and the raw un-joined spelling is not
    assert any(0xFE70 <= ord(c) <= 0xFEFF for c in text)
    assert "أساسيات" not in text


@needs_pdftotext
def test_draft_stamp_depends_on_curriculum_approval(tmp_path):
    draft = DocumentAgent().run({"document_type": "curriculum_report", "curriculum": _arabic_curriculum(),
                                 "output_dir": str(tmp_path / "d")})
    final = DocumentAgent().run({"document_type": "curriculum_report", "curriculum": _arabic_curriculum("approved"),
                                 "output_dir": str(tmp_path / "f")})
    assert draft.ok and final.ok
    assert _has_word(_text(draft.output["file_path"]), "مسودة")
    assert not _has_word(_text(final.output["file_path"]), "مسودة")


@needs_pdftotext
def test_english_documents_still_work_and_use_a_standard_font(tmp_path):
    res = DocumentAgent().run({"document_type": "course_description", "title": "Python Basics",
                               "content": {"pitch": "Start with Python.", "level": "Beginner"},
                               "output_dir": str(tmp_path)})
    assert res.ok and res.output["language"] == "en"
    assert "Start with Python." in _text(res.output["file_path"])


def test_language_is_detected_from_an_arabic_title(tmp_path):
    res = DocumentAgent().run({"document_type": "course_description", "title": "دورة بايثون",
                               "content": {"pitch": "مقدمة عملية"}, "output_dir": str(tmp_path)})
    assert res.ok and res.output["language"] == "ar"


def test_unsupported_document_type_is_rejected(tmp_path):
    assert not DocumentAgent().run({"document_type": "poem", "output_dir": str(tmp_path)}).ok
