"""Arabic keyword detection in the assistant engine (these literals were corrupted by a double-encoding bug)."""
from rex.assistant.engine import RexAssistant


def test_arabic_language_switch_is_detected():
    assert RexAssistant._requested_language("ممكن ترد بالعربي") == "ar"
    assert RexAssistant._requested_language("ترجم بالعربية") == "ar"
    assert RexAssistant._requested_language("رد بالانجليزي لو سمحت") == "en"


def test_arabic_course_and_price_list_requests_are_detected():
    assert RexAssistant._is_course_list_request("ما هي الدورات المتاحة؟")
    assert RexAssistant._is_course_list_request("اعرض الكورسات")
    assert RexAssistant._is_price_list_request("أسعار الدورات")
    assert RexAssistant._is_translation_request("ترجم الرد")
    assert not RexAssistant._is_course_list_request("hello")
