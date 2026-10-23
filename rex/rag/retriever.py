"""BM25 retriever over the RAG documents in data/rag_docs (works for Arabic and English).

Pure Python on purpose (no extra installs). The interface (`search(query, k)`) stays the same if you
later swap BM25 for embeddings (Chroma / FAISS) - only this file changes."""
import math
import pathlib
import re
from collections import Counter
from dataclasses import dataclass, field

from rex.assistant.text import is_arabic, tokens as _tokens


def tokens(text):
    """Base tokens + simple English plural stripping (courses -> course)."""
    out = []
    for w in _tokens(text):
        out.append(w)
        if w.isascii() and len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            out.append(w[:-1])
    return out

DOCS_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "rag_docs"


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
    m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    meta, body = {}, raw
    if m:
        for line in m.group(1).splitlines():
            if ": " in line:
                k, v = line.split(": ", 1)
                meta[k.strip()] = v.strip()
        body = m.group(2).strip()
    return Chunk(meta.get("doc_id", path.stem), meta.get("title", path.stem), body, meta)


class Retriever:
    K1, B = 1.5, 0.75

    def __init__(self, docs_dir: pathlib.Path = DOCS_DIR):
        self.chunks = [parse_doc(p) for p in sorted(pathlib.Path(docs_dir).glob("*.md"))]
        self._tf = []
        for c in self.chunks:
            bag = Counter(tokens(c.text))
            for t in tokens(c.title + " " + c.meta.get("keywords", "")):
                bag[t] += 3  # title and keywords count more
            self._tf.append(bag)
        n = len(self.chunks)
        self._avg = (sum(sum(b.values()) for b in self._tf) / n) if n else 0
        df = Counter(t for b in self._tf for t in b)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def search(self, query: str, k: int = 4, doc_type: str | None = None) -> list[Chunk]:
        q = tokens(query)
        scored = []
        for chunk, bag in zip(self.chunks, self._tf):
            if doc_type and chunk.meta.get("type") != doc_type:
                continue
            length = sum(bag.values()) or 1
            s = 0.0
            for t in q:
                f = bag.get(t, 0)
                if f:
                    s += self._idf.get(t, 0) * f * (self.K1 + 1) / (f + self.K1 * (1 - self.B + self.B * length / self._avg))
            if s > 0:
                scored.append(Chunk(chunk.doc_id, chunk.title, chunk.text, chunk.meta, round(s, 3)))
        scored.sort(key=lambda c: -c.score)
        if not scored:  # generic question ("what do you offer?"): fall back to the catalog overview
            lang = "ar" if is_arabic(query) else "en"
            return [c for c in self.chunks if c.doc_id == f"catalog_{lang}"][:1]
        return scored[:k]
