from rex.assistant.engine import RexAssistant, Session
from rex.assistant.rag import RagAssistant
from rex.rag.llm import LLMError
from rex.rag.retriever import Retriever


def make(llm):
    return RagAssistant(retriever=Retriever(), llm=llm, fallback=RexAssistant(), use_env_llm=False)


def test_retriever_finds_price_doc():
    assert Retriever().search("how much is the cybersecurity course", k=1)[0].course_id == "C05"


def test_retriever_arabic_and_generic():
    r = Retriever()
    assert r.search("ايه شروط القبول", k=1)[0].doc_id == "admission_ar"
    assert r.search("what courses do you have")[0].doc_id == "catalog_en"


def test_llm_receives_context_and_sources_returned():
    seen = {}

    def fake(messages):
        seen["system"] = messages[0]["content"]
        return "The Cybersecurity course costs what the context says."

    s = Session()
    out = make(fake).reply(s, "how much is the cybersecurity course")
    assert "CONTEXT" in seen["system"] and "course_C05" in seen["system"]
    assert "Sources" in out and len(s.history) == 2


def test_fallback_without_llm():
    assert make(None).reply(Session(), "I want to learn AI")  # rule-based answer, no crash


def test_fallback_when_llm_fails():
    def boom(messages):
        raise LLMError("down")

    assert make(boom).reply(Session(), "I want to learn AI")


def test_arabic_message_sets_language():
    s = Session()
    make(lambda m: "تمام").reply(s, "كام سعر كورس الامن السيبراني")
    assert s.lang == "ar"
