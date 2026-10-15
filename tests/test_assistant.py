import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from rex.assistant.engine import RexAssistant, Session
from rex.assistant.kb import KnowledgeBase
from rex.agents.orchestrator import Orchestrator

@pytest.fixture
def bot(tmp_path): return RexAssistant(leads_file=tmp_path / "leads.csv")

def chat(bot, s, *msgs): return [bot.reply(s, m) for m in msgs]

def test_kb_loads_and_is_complete():
    kb = KnowledgeBase()
    assert len(kb.courses) >= 8
    for c in kb.courses:
        assert c["instructor_id"] in kb.instructors and c["data_source"] and c["updated"]

def test_search_finds_ai_course():
    assert KnowledgeBase().search("machine learning")[0][1]["id"] == "C02"

def test_asks_followups_before_recommending(bot):
    s = Session(); r = chat(bot, s, "hi", "I want to learn web development")
    assert "level" in r[1].lower() and "Here are" not in r[1]

def test_recommends_matching_course(bot):
    s = Session(); r = chat(bot, s, "I want web development", "beginner", "online")
    assert "Web Development with React" in r[-1]

def test_budget_filters_expensive_courses(bot):
    s = Session(); r = chat(bot, s, "machine learning", "intermediate", "online budget 5000")
    assert "Generative AI" not in r[-1]

def test_answers_price_and_instructor_from_data(bot):
    s = Session(); chat(bot, s, "cybersecurity", "beginner", "online")
    assert "4,800" in bot.reply(s, "how much does it cost?")
    assert "Sara Nabil" in bot.reply(s, "who is the instructor?")

def test_arabic_conversation(bot):
    s = Session(); r = chat(bot, s, "أريد تعلم التسويق الرقمي", "مبتدئ", "اونلاين")
    assert "أساسيات التسويق الرقمي" in r[-1]

def test_unknown_topic_does_not_invent_courses(bot):
    s = Session(); r = chat(bot, s, "I want to learn underwater basket weaving", "beginner", "online")
    assert "couldn't find" in r[-1]

def test_lead_saved_only_with_consent(bot, tmp_path):
    s = Session(); chat(bot, s, "excel", "beginner", "online")
    chat(bot, s, "no")
    assert not (tmp_path / "leads.csv").exists()
    s2 = Session(); chat(bot, s2, "excel", "beginner", "online", "yes", "Omar", "omar@example.com")
    assert "omar@example.com" in (tmp_path / "leads.csv").read_text(encoding="utf-8")

def test_orchestrator_stub_and_unknown_agent():
    o = Orchestrator()
    assert not o.dispatch("rfp_research", {}).ok and not o.dispatch("nope", {}).ok

def test_beginner_not_pushed_to_advanced_first(bot):
    s = Session(); r = chat(bot, s, "I want to learn AI", "beginner", "online")
    assert r[-1].split("1. ")[1].startswith("Python for Data Analysis")

def test_arabic_beginner_ai_gets_beginner_course_first(bot):
    s = Session(); r = chat(bot, s, "أريد تعلم الذكاء الاصطناعي", "مبتدئ", "اونلاين")
    assert r[-1].split("1. ")[1].startswith("بايثون لتحليل البيانات")

def test_warns_when_course_is_above_level(bot):
    s = Session(); r = chat(bot, s, "I want generative AI llm", "beginner", "online")
    assert "above your level" in r[-1] and "Python and basic ML knowledge" in r[-1]
