
"""REX Assistant with retrieval-augmented generation (RAG) and an LLM."""

from rex.rag.llm import LLMClient
from rex.rag.retriever import Retriever
from .engine import RexAssistant, Session
from .text import is_arabic


SYSTEM_PROMPT = """You are REX AI, a helpful bilingual assistant for a training academy.
Answer in the same language as the user's latest message.
Use the supplied academy documents as the source of factual information.
Never invent course names, prices, durations, instructors, or prerequisites.
If information is missing, say that you do not have it.
Keep answers friendly, clear, and concise.
Use conversation history to understand short answers such as "beginner"
or a course topic. Do not repeat questions the user has already answered.
When the user gives their level or preferred topic, use that information
to continue toward a suitable course recommendation.
"""


class RagAssistant:
    def __init__(
        self,
        retriever=None,
        llm=None,
        fallback=None,
        use_env_llm=True,
    ):
        self.retriever = retriever if retriever is not None else Retriever()
        self.fallback = fallback if fallback is not None else RexAssistant()
        self.llm = llm
        self.llm_enabled = llm is not None

        if self.llm is None and use_env_llm:
            try:
                self.llm = LLMClient()
                self.llm_enabled = self.llm is not None
            except Exception:
                self.llm = None
                self.llm_enabled = False

    def _build_messages(
        self,
        session: Session,
        message: str,
        chunks: list,
    ) -> list:
        context = "\n\n".join(
            f"[{chunk.doc_id} | {chunk.title}]\n{chunk.text}"
            for chunk in chunks
        )

        system_content = SYSTEM_PROMPT

        if context:
            system_content += (
                "\n\nCONTEXT\n"
                "Use the following retrieved academy documents as factual context:\n\n"
                + context
            )

        messages = [
            {"role": "system", "content": system_content}
        ]

        history = getattr(session, "history", [])
        messages.extend(history[-8:])
        messages.append({"role": "user", "content": message})

        return messages

    @staticmethod
    def _sources_line(chunks: list, arabic: bool) -> str:
        titles = []

        for chunk in chunks:
            title = getattr(chunk, "title", None)
            if title and title not in titles:
                titles.append(title)

        if not titles:
            return ""

        label = "📚 المصادر: " if arabic else "📚 Sources: "
        return "\n\n" + label + " · ".join(titles[:4])

    def reply(self, session: Session, message: str) -> str:
        arabic = is_arabic(message)
        session.lang = "ar" if arabic else "en"

        try:
            chunks = self.retriever.search(message, k=4)
        except Exception:
            chunks = []

        if not self.llm_enabled or self.llm is None:
            return self.fallback.reply(session, message)

        try:
            answer = self.llm(
                self._build_messages(session, message, chunks)
            )
        except Exception:
            return self.fallback.reply(session, message)

        if not isinstance(answer, str):
            answer = str(answer)

        session.history += [
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer},
        ]

        return answer + self._sources_line(chunks, arabic)

