import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps"))
import ui_theme  # noqa: E402


class FakeSt:
    def __init__(self):
        self.out = []

    def markdown(self, html, unsafe_allow_html=False):
        self.out.append(html)


def test_texts_differ_by_role_language_and_time():
    user_en = ui_theme.greeting_text("Nour", False, False, 9)
    admin_en = ui_theme.greeting_text("Admin", True, False, 20, pending=3)
    assert user_en[0].startswith("Good morning") and "CV" in user_en[1]
    assert admin_en[0].startswith("Good evening") and "3 campaign" in admin_en[1]
    assert "المدير" in ui_theme.greeting_text("المدير", True, True, 15, 2)[0]
    assert "2" in ui_theme.greeting_text("x", True, True, 15, 2)[1]


def test_robot_is_rendered_and_name_is_escaped():
    st = FakeSt()
    ui_theme.robot_greeting(st, "<script>alert(1)</script>", False, True, 10)
    html = st.out[0]
    assert "rex-greet ar" in html and "<svg" in html and "prefers-reduced-motion" in html
    assert "<script>" not in html and "&lt;script&gt;" in html
