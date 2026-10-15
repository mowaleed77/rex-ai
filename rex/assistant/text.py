"""Small bilingual (Arabic/English) text helpers."""
import re

_AR_DIACRITICS = re.compile(r"[ً-ْـ]")
STOP = set("a an the i me my to of in for and or is are am want would like need can you do how what which with on at it be learn course courses ابغى اريد عايز عاوز انا في من على الى الي هل ما ماذا كيف كورس دورة hello hi hey thanks thank yes no مرحبا اهلا سلام عليكم شكرا تعلم اتعلم اتعلمه".split())

def is_arabic(s: str) -> bool:
    return len(re.findall(r"[؀-ۿ]", s)) > len(re.findall(r"[A-Za-z]", s))

def normalize(s: str) -> str:
    s = _AR_DIACRITICS.sub("", s.lower())
    s = re.sub("[إأآا]", "ا", s).replace("ى", "ي").replace("ة", "ه")
    return s

def tokens(s: str) -> list[str]:
    out = []
    for t in re.findall(r"\w+", normalize(s)):
        if t.startswith("ال") and len(t) > 4:
            t = t[2:]
        if t not in STOP and len(t) > 1:
            out.append(t)
    return out
