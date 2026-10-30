"""BM25 retriever for Arabic and English RAG documents."""

import math
import pathlib
import re
from collections import Counter
from dataclasses import dataclass, field

from rex.assistant.text import is_arabic, tokens as _tokens


DOCS_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "rag_docs"


def tokens(text):
    """Tokenize text and handle simple English plurals."""
    result = []

    for word in _tokens(text):
        result.append(word)

        if (
            word.isascii()
            and len(word) > 3
            and word.endswith("s")
            and not word.endswith("ss")
        ):
            result.append(word[:-1])

    return result


@dataclass
class Chunk:
    doc_id: str
    title: str
    text: str
    meta: dict = field(default_factory=dict)
    score: float = 0.0

    @property
    def course_id(self):
        return self.meta.get("course_id")


def parse_doc(path: pathlib.Path) -> Chunk:
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)

    meta = {}
    body = raw

    if match:
        for line in match.group(1).splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                meta[key.strip()] = value.strip()

        body = match.group(2).strip()

    return Chunk(
        meta.get("doc_id", path.stem),
        meta.get("title", path.stem),
        body,
        meta,
    )


class Retriever:
    K1 = 1.5
    B = 0.75

    OFFER_TERMS = {
        "offer", "offers", "promotion", "promotions",
        "discount", "discounts", "deal", "deals",
        "special", "sale", "coupon", "coupons",
        "عرض", "عروض", "خصم", "خصومات",
    }

    def __init__(self, docs_dir: pathlib.Path = DOCS_DIR):
        self.chunks = [
            parse_doc(path)
            for path in sorted(pathlib.Path(docs_dir).glob("*.md"))
        ]

        self._tf = []

        for chunk in self.chunks:
            bag = Counter(tokens(chunk.text))

            for token in tokens(
                chunk.title + " " + chunk.meta.get("keywords", "")
            ):
                bag[token] += 3

            self._tf.append(bag)

        count = len(self.chunks)

        self._avg = (
            sum(sum(bag.values()) for bag in self._tf) / count
            if count
            else 1
        )

        if self._avg == 0:
            self._avg = 1

        document_frequency = Counter(
            token
            for bag in self._tf
            for token in bag
        )

        self._idf = {
            token: math.log(
                1 + (count - frequency + 0.5) / (frequency + 0.5)
            )
            for token, frequency in document_frequency.items()
        }

    def search(
        self,
        query: str,
        k: int = 4,
        doc_type: str | None = None,
    ) -> list[Chunk]:
        query_tokens = tokens(query)
        query_lower = query.lower()

        offer_query = any(
            term in query_tokens or term in query_lower
            for term in self.OFFER_TERMS
        )

        scored = []

        for chunk, bag in zip(self.chunks, self._tf):
            if doc_type and chunk.meta.get("type") != doc_type:
                continue

            length = sum(bag.values()) or 1
            score = 0.0

            for token in query_tokens:
                frequency = bag.get(token, 0)

                if frequency:
                    denominator = frequency + self.K1 * (
                        1 - self.B + self.B * length / self._avg
                    )

                    score += (
                        self._idf.get(token, 0)
                        * frequency
                        * (self.K1 + 1)
                        / denominator
                    )

            if score > 0:
                text_lower = chunk.text.lower()
                doc_id = chunk.doc_id.lower()

                if offer_query:
                    if "pricing" in doc_id or "promotion" in doc_id:
                        score *= 3.0

                    if "current offer" in text_lower or "العرض الحالي" in text_lower:
                        score *= 1.5

                    if any(
                        phrase in text_lower
                        for phrase in (
                            "no offer",
                            "offer: none",
                            "لا يوجد",
                        )
                    ):
                        score *= 0.7

                scored.append(
                    Chunk(
                        chunk.doc_id,
                        chunk.title,
                        chunk.text,
                        chunk.meta,
                        round(score, 3),
                    )
                )

        scored.sort(key=lambda chunk: -chunk.score)

        if not scored:
            language = "ar" if is_arabic(query) else "en"
            catalog_id = f"catalog_{language}"

            return [
                chunk
                for chunk in self.chunks
                if chunk.doc_id == catalog_id
            ][:1]

        return scored[:max(0, k)]
