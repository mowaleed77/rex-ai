"""RagAssistant = REX Assistant with retrieval (RAG) + a real LLM.

Per message:  retrieve the most relevant academy documents -> put them in the prompt as the ONLY
allowed source of facts -> ask the LLM -> return its answer plus the sources used.

Safety nets (the demo can never break):
  * no API key, or the LLM call fails  -> falls back to the rule-based RexAssistant
  * consent / lead capture stays deterministic (same flow as the rule-based bot)
Drop-in replacement: same `reply(session, message)` API as RexAssistant."""
import re

from rex.rag.llm import LLMClient, LLMError
from rex.rag.retriever import Retriever
from .engine import RexAssistant, Session, T, YES, NO
from .text import is_arabic, normalize

SYSTEM_PROMPT = """You are REX, the course assistant of a training academy. You help potential students (leads) choose the right course.

RULES
0. You ONLY discuss this academy, its courses, prices, instructors, admission and choosing a course. For ANY unrelated request (cooking, recipes, general knowledge, coding help, news, etc.) do NOT answer it: say in one friendly sentence that you can only help with the academy's courses, then ask what the learner would like to study. Never answer from general knowledge.Greetings and small talk are fine: greet back warmly in one sentence and ask what the learner would like to study.
1. Use ONLY the facts in the CONTEXT below (academy-approved documents). Never invent courses, prices, dates, instructors, offers or accreditation. If the answer is not in the CONTEXT, say you don't have that information and suggest contacting admissions.
2. Reply in the same language as the user's last message (Arabic or English). For Arabic use simple Egyptian-friendly Modern Standard Arabic.
3. Before recommending, make sure you know the learner's interest and level. If something important is missing, ask ONE or TWO short follow-up questions (background, level, goals, online/onsite, budget, time available) instead of recommending right away.
4. When you recommend, suggest at most 3 courses and explain why each fits (level, goals, format, budget). If a course is above the learner's level, say so and mention its prerequisites.
5. Prices are in EGP (جنيه). Quote prices, durations, offers and prerequisites exactly as written in the CONTEXT.
6. Never claim a course is officially accredited unless the CONTEXT says so.
7. Keep answers short and friendly. Use a numbered list for recommendations.
8. If the user wants to register or be contacted, tell them you can pass their details to admissions (you will ask for their consent first)."""

LEAD_WORDS = "register enroll signup contact call me follow admissions سجلني اسجل تسجيل تواصل كلمني اتصل"


class RagAssistant:
    def __init__(self, retriever: Retriever | None = None, llm=None, fallback: RexAssistant | None = None, use_env_llm: bool = True):
        self.retriever = retriever or Retriever()
        self.fallback = fallback or RexAssistant()
        self.llm = llm if llm is not None else (LLMClient.from_env() if use_env_llm else None)

    @property
    def llm_enabled(self) -> bool:
        return self.llm is not None

    # ---- helpers
    @staticmethod
    def _words(text):
        return set(re.findall(r"\w+", normalize(text)))

    def _query(self, s: Session, msg: str) -> str:
        """Current message plus the user's recent turns, so 'how much is it?' still finds the course."""
        recent = [h["content"] for h in s.history if h["role"] == "user"][-2:]
        return " ".join(recent + [msg])

    def _build_messages(self, s: Session, msg: str, chunks):
        context = "\n\n".join(f"[{c.doc_id}] {c.title}\n{c.text}" for c in chunks) or "(no relevant documents found)"
        profile = {k: v for k, v in {"level": s.level, "format": s.fmt, "budget_egp": s.budget}.items() if v}
        system = SYSTEM_PROMPT + (f"\n\nKNOWN LEARNER PROFILE: {profile}" if profile else "") + f"\n\nCONTEXT\n{context}"
        return [{"role": "system", "content": system}, *s.history[-8:], {"role": "user", "content": msg}]

    @staticmethod
    def _sources_line(chunks, ar: bool) -> str:
        titles = list(dict.fromkeys(c.title for c in chunks if c.score > 0))[:4]
        if not titles:
            return ""
        return ("\n\n📚 المصادر: " if ar else "\n\n📚 Sources: ") + (" · ".join(titles) if titles else "—")

    # ---- main entry
    def reply(self, s: Session, msg: str) -> str:
        msg = msg.strip()
        if not msg:
            return self.fallback.reply(s, msg)
        words = self._words(msg)

        # consent / lead capture is deterministic and identical to the rule-based bot
        if s.stage in ("name", "contact") or (s.stage == "consent" and len(words) <= 2 and words & ({normalize(w) for w in YES} | {normalize(w) for w in NO})):
            s.lang = "ar" if is_arabic(msg) else "en"
            return self.fallback.reply(s, msg)
        if self.llm is None:
            return self.fallback.reply(s, msg)

        s.lang = "ar" if is_arabic(msg) else "en"
        ar = s.lang == "ar"
        self.fallback._update_slots(s, msg)  # keep level / format / budget for lead rows and the prompt

        chunks = self.retriever.search(self._query(s, msg), k=4)
        s.last_courses = [c for c in self.fallback.kb.courses if c["id"] in {x.course_id for x in chunks if x.course_id}][:3] or s.last_courses

        if self._words(LEAD_WORDS) & words and s.last_courses:
            s.stage = "consent"
            return self.fallback._t("consent", s)

        try:
            answer = self.llm(self._build_messages(s, msg, chunks))
        except LLMError:
            return self.fallback.reply(s, msg)  # graceful fallback, never a crash

        s.history += [{"role": "user", "content": msg}, {"role": "assistant", "content": answer}]
        return answer + self._sources_line(chunks, ar)
