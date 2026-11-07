
"""Small bilingual Arabic and English text helpers."""

import re
import unicodedata

_ARABIC_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670\u0640]")

STOP = set("""
a an the i me my to of in for and or is are am want would like need
can you do how what which with on at it be learn course courses
hello hi hey thanks thank yes no
أبغى أريد عايز عاوز أنا في من على إلى الي هل ماذا ما كيف هي و
كورس دورة دورات مرحبا أهلا اهلا سلام عليكم شكرا تعلم اتعلم اتعلمه
""".split())


def is_arabic(text: str) -> bool:
    arabic_count = len(re.findall(r"[\u0600-\u06FF]", text))
    latin_count = len(re.findall(r"[A-Za-z]", text))
    return arabic_count > latin_count


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = _ARABIC_DIACRITICS.sub("", text)
    text = re.sub(r"[إأآٱ]", "ا", text)
    text = text.replace("ى", "ي")
    text = text.replace("ة", "ه")
    return text


def tokens(text: str) -> list[str]:
    result = []

    for token in re.findall(r"\w+", normalize(text)):
        if token.startswith("ال") and len(token) > 4:
            token = token[2:]

        if token not in STOP and len(token) > 1:
            result.append(token)

    return result
