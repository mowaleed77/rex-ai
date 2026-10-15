"""Knowledge base: loads approved academy data and does keyword retrieval.
Answers must come from this data only (no invented course details)."""
import json
from pathlib import Path
from collections import Counter
from .text import tokens

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

class KnowledgeBase:
    def __init__(self, data_dir: Path = DATA_DIR):
        load = lambda n: json.loads((data_dir / f"{n}.json").read_text(encoding="utf-8"))
        self.courses = load("courses")
        self.instructors = {i["id"]: i for i in load("instructors")}
        self.faqs = load("faqs")
        self.admission = load("admission")
        self._index = {c["id"]: self._build(c) for c in self.courses}

    @staticmethod
    def _build(c) -> Counter:
        bag = Counter()
        for t in tokens(c["keywords"]): bag[t] += 3
        for t in tokens(c["title_en"] + " " + c["title_ar"]): bag[t] += 3
        for t in tokens(c["description"] + " " + " ".join(c["learning_outcomes"]) + " " + c["department"]): bag[t] += 1
        return bag

    def search(self, query: str, top_k: int = 5):
        q = set(tokens(query))
        scored = [(sum(self._index[c["id"]][t] for t in q), c) for c in self.courses]
        return [(s, c) for s, c in sorted(scored, key=lambda x: -x[0]) if s > 0][:top_k]

    def find_course(self, text: str):
        """Course explicitly named in text (by title or id), else None."""
        low = text.lower()
        for c in self.courses:
            if c["id"].lower() in low.split() or c["title_en"].lower() in low or c["title_ar"] in text:
                return c
        return None

    def faq(self, text: str):
        q = set(tokens(text))
        best, score = None, 0
        for f in self.faqs:
            s = len(q & set(tokens(f["keywords"] + " " + f["q_en"] + " " + f["q_ar"])))
            if s > score: best, score = f, s
        return best if score >= 1 else None
