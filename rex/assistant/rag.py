"""RAG-enabled assistant with native Groq LLM client and rule-based fallback."""

import logging

from rex.rag.llm import LLMClient
from rex.rag.retriever import Retriever
from .engine import RexAssistant, Session
from .text import is_arabic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are REX AI, an official bilingual assistant strictly dedicated to Smart Academy courses, prices, durations, prerequisites, instructors, and career paths.

STRICT DOMAIN BOUNDARIES:
1. You MUST welcome the user warmly when they say greetings like "hi", "hello", "hey", or "مرحباً".
2. You MUST ONLY assist with questions related to the academy, courses, enrollment, fees, schedule, skills, and learning paths.
3. If the user asks about anything outside of Smart Academy or education (such as cooking recipes, general jokes, weather, sports, personal advice, etc.), politely decline by saying:
   - In English: "I can only assist you with Smart Academy courses, pricing, admission, and learning paths."
   - In Arabic: "يمكنني مساعدتك فقط في كل ما يتعلق بكورسات الأكاديمية، الأسعار، القبول، والمجالات التعليمية."
4. Never invent course names, prices, instructors, or admission rules.
5. Keep all responses clear, helpful, professional, and concise.
"""


class RagAssistant:
    def __init__(
        self,
        retriever=None,
        llm=None,
        fallback=None,
        use_env_llm=True,
        max_history_messages=8,
    ):
        self.retriever = retriever if retriever is not None else Retriever()
        self.fallback = fallback if fallback is not None else RexAssistant()
        self.max_history_messages = max(0, max_history_messages)
        self.history = {}
        self.llm = llm

        # Initialize native LLMClient from environment directly (avoiding LangChain overrides)
        if self.llm is None and use_env_llm:
            try:
                self.llm = LLMClient.from_env()
                if self.llm is not None:
                    logger.info(f"Native LLMClient initialized with model: {self.llm.model}")
            except Exception:
                logger.exception("Failed to initialize the LLM client.")
                self.llm = None

        self.llm_enabled = self._is_llm_usable(self.llm)

        if self.llm is not None and not self.llm_enabled:
            logger.warning(
                "The configured LLM client is not usable. "
                "RAG will use the rule-based fallback."
            )

    @staticmethod
    def _is_llm_usable(llm):
        """Check whether the configured LLM supports a usable interface."""
        if llm is None:
            return False

        return (
            callable(getattr(llm, "invoke", None))
            or callable(llm)
            or callable(getattr(llm, "generate", None))
        )

    def _call_llm(self, messages):
        """Call the native LLM client."""
        if self.llm is None:
            raise RuntimeError("No LLM client is configured.")

        if callable(self.llm):
            return self.llm(messages)

        if callable(getattr(self.llm, "invoke", None)):
            return self.llm.invoke(messages)

        raise TypeError(f"Unsupported LLM client type: {type(self.llm).__name__}")

    def _build_messages(self, session, message, chunks):
        context = "\n\n".join(
            f"[{chunk.doc_id} | {chunk.title}]\n{chunk.text}"
            for chunk in chunks
            if getattr(chunk, "text", "")
        )

        system = SYSTEM_PROMPT

        if context:
            system += "\n\nCONTEXT:\n" + context
        else:
            system += (
                "\n\nCONTEXT:\nNo relevant documents were retrieved. "
                "Do not invent academy facts."
            )

        key = id(session)
        history = self.history.setdefault(key, [])

        messages = [{"role": "system", "content": system}]

        if self.max_history_messages:
            messages.extend(history[-self.max_history_messages:])

        messages.append({"role": "user", "content": message})

        return messages

    @staticmethod
    def _sources_line(chunks, arabic):
        titles = list(
            dict.fromkeys(
                chunk.title
                for chunk in chunks
                if getattr(chunk, "title", "")
            )
        )

        if not titles:
            return ""

        label = "المصادر: " if arabic else "Sources: "
        return "\n\n" + label + " · ".join(titles[:4])

    def reply(self, session: Session, message: str) -> str:
        if not isinstance(message, str) or not message.strip():
            return self.fallback.reply(
                session,
                message if isinstance(message, str) else "",
            )

        message = message.strip()
        lower = message.lower()

        special_phrases = (
            "switch to arabic",
            "switch to english",
            "translate",
            "list all courses",
            "all courses",
            "list course prices",
            "all prices",
        )

        if (
            any(phrase in lower for phrase in special_phrases)
            or session.stage != "chat"
        ):
            return self.fallback.reply(session, message)

        arabic = is_arabic(message)

        if session.language_locked:
            arabic = session.lang == "ar"

        if not self.llm_enabled:
            return self.fallback.reply(session, message)

        try:
            chunks = self.retriever.search(message, k=4) or []
            messages = self._build_messages(session, message, chunks)

            answer = self._call_llm(messages)

            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("The LLM returned an empty answer.")

            answer = answer.strip()

            key = id(session)
            history = self.history.setdefault(key, [])

            conversation_turn = [
                {"role": "user", "content": message},
                {"role": "assistant", "content": answer},
            ]

            history.extend(conversation_turn)
            session.history.extend(conversation_turn)

            if self.max_history_messages:
                self.history[key] = history[-self.max_history_messages:]
            else:
                self.history[key] = []

            session.lang = "ar" if arabic else "en"
            session.last_answer = answer

            return answer + self._sources_line(chunks, arabic)

        except Exception as e:
            logger.exception(
                f"RAG response failed with error: {e}; using rule-based fallback."
            )
            return self.fallback.reply(session, message)