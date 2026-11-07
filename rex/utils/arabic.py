"""Arabic text support for PDF output (ReportLab cannot shape or reorder Arabic by itself).

Arabic letters change shape depending on their neighbours and the text runs right-to-left, so
text has to be (1) *shaped* into joined presentation forms and (2) *reordered* into visual order
before being drawn by a left-to-right renderer.

* If `arabic-reshaper` and `python-bidi` are installed (see requirements.txt) they are used.
* Otherwise a built-in pure-Python shaper + simplified bidi algorithm is used, so Arabic PDFs
  still render correctly (diacritics are dropped in that mode).

Public helpers:
    has_arabic(text)                      -> bool
    is_mostly_arabic(text)                -> bool
    visual(text, rtl=True)                -> one-line string ready to draw
    wrap_visual(text, font, size, width)  -> list of visual lines that fit `width` points
    register_fonts()                      -> (regular_font_name, bold_font_name) for ReportLab
"""
from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_TASHKEEL_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")

ASSETS_FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"
FONT_REGULAR = "REX-Arabic"
FONT_BOLD = "REX-Arabic-Bold"


def has_arabic(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))


def is_mostly_arabic(text: str) -> bool:
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if _ARABIC_RE.match(c)) / len(letters) > 0.4


# ------------------------------------------------------------ optional libraries
try:  # pragma: no cover - depends on the environment
    import arabic_reshaper as _reshaper_lib
except Exception:  # ImportError or a broken install
    _reshaper_lib = None

try:  # pragma: no cover - depends on the environment
    from bidi.algorithm import get_display as _get_display
except Exception:
    try:
        from bidi import get_display as _get_display
    except Exception:
        _get_display = None

LIBRARIES_AVAILABLE = _reshaper_lib is not None and _get_display is not None


# ----------------------------------------------------------- built-in shaper
def _build_forms() -> tuple[dict, dict]:
    """Letter -> {form: presentation codepoint}, built from Unicode's own decomposition data."""
    forms: dict[int, dict[str, int]] = {}
    ligatures: dict[tuple[int, int], dict[str, int]] = {}
    for cp in range(0xFE70, 0xFEFD):
        dec = unicodedata.decomposition(chr(cp))
        if not dec.startswith("<"):
            continue
        tag, *rest = dec.split()
        tag = tag.strip("<>")
        if tag not in ("isolated", "final", "initial", "medial"):
            continue
        base = [int(x, 16) for x in rest]
        if len(base) == 1:
            forms.setdefault(base[0], {})[tag] = cp
        elif len(base) == 2 and base[0] == 0x0644:  # lam + alef ligatures
            ligatures.setdefault((base[0], base[1]), {})[tag] = cp
    return forms, ligatures


_FORMS, _LIGATURES = _build_forms()
_ALEFS = {0x0622, 0x0623, 0x0625, 0x0627}


def _is_transparent(ch: str) -> bool:
    return bool(_TASHKEEL_RE.match(ch))


def _dual_joining(ch: str) -> bool:
    cp = ord(ch)
    return cp == 0x0640 or "initial" in _FORMS.get(cp, {})


def _joins_left_side(ch: str) -> bool:
    """True if `ch` can connect to a letter placed before it (to its right)."""
    cp = ord(ch)
    return cp == 0x0640 or "final" in _FORMS.get(cp, {})


def _shape_builtin(text: str) -> str:
    text = _TASHKEEL_RE.sub("", text)
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        cp = ord(ch)
        if cp not in _FORMS and cp != 0x0640:
            out.append(ch)
            i += 1
            continue
        prev = text[i - 1] if i > 0 else ""
        connect_prev = bool(prev) and prev != " " and ord(prev) in _FORMS and _dual_joining(prev) \
            or (bool(prev) and ord(prev) == 0x0640)
        # lam + alef ligature
        if cp == 0x0644 and i + 1 < n and ord(text[i + 1]) in _ALEFS:
            lig = _LIGATURES.get((0x0644, ord(text[i + 1])))
            if lig:
                out.append(chr(lig["final" if connect_prev else "isolated"]))
                i += 2
                continue
        nxt = text[i + 1] if i + 1 < n else ""
        connect_next = _dual_joining(ch) and bool(nxt) and (ord(nxt) in _FORMS or ord(nxt) == 0x0640) \
            and _joins_left_side(nxt)
        if cp == 0x0640:
            out.append(ch)
        else:
            f = _FORMS[cp]
            if connect_prev and connect_next and "medial" in f:
                form = "medial"
            elif connect_next and "initial" in f:
                form = "initial"
            elif connect_prev and "final" in f:
                form = "final"
            else:
                form = "isolated"
            out.append(chr(f.get(form) or f.get("isolated") or cp))
        i += 1
    return "".join(out)


# ----- simplified bidirectional reordering (enough for Arabic text with Latin words and numbers)
_MIRROR = str.maketrans("()[]{}<>", ")(][}{><")


def _kind(ch: str) -> str:
    """R (right-to-left letter), L (left-to-right letter), N (number) or O (neutral)."""
    bidi = unicodedata.bidirectional(ch)
    if bidi in ("R", "AL"):
        return "R"
    if bidi == "L":
        return "L"
    if bidi in ("EN", "AN"):
        return "N"
    return "O"


def _reorder_builtin(text: str, rtl: bool) -> str:
    if not text:
        return text
    kinds = [_kind(c) for c in text]
    n = len(text)
    # separators/currency inside or around numbers behave like part of the number (1,200  3.5  50%)
    for i, c in enumerate(text):
        if kinds[i] == "O" and c in ",.:/%+-$":
            left = i > 0 and kinds[i - 1] == "N"
            right = i + 1 < n and kinds[i + 1] == "N"
            if (left and right) or (left and c == "%"):
                kinds[i] = "N"
    base = 1 if rtl else 0
    levels = [base] * n
    # strong direction of the closest strong letter on each side, for resolving neutrals
    def strong(i, step):
        j = i + step
        while 0 <= j < n:
            if kinds[j] in ("R", "L"):
                return kinds[j]
            j += step
        return None
    for i in range(n):
        k = kinds[i]
        if k == "R":
            levels[i] = 1
        elif k == "L":
            levels[i] = 2 if rtl else 0
        elif k == "N":
            before = strong(i, -1)
            # numbers stay left-to-right, but inside a right-to-left run they sit one level higher
            levels[i] = 2 if (rtl or before == "R") else 0
        else:
            left, right = strong(i, -1), strong(i, 1)
            if left and left == right:
                levels[i] = 1 if left == "R" else (2 if rtl else 0)
            else:
                levels[i] = base
    # neutrals between two numbers of the same run follow the number level (e.g. "2026 - 2027")
    chars = [c.translate(_MIRROR) if levels[i] % 2 == 1 else c for i, c in enumerate(text)]
    hi = max(levels)
    lo_odd = min((lv for lv in levels if lv % 2 == 1), default=hi + 1)
    order = list(range(n))
    for lv in range(hi, lo_odd - 1, -1):
        i = 0
        while i < n:
            if levels[order[i]] >= lv:
                j = i
                while j < n and levels[order[j]] >= lv:
                    j += 1
                order[i:j] = reversed(order[i:j])
                i = j
            else:
                i += 1
    return "".join(chars[k] for k in order)


# ------------------------------------------------------------------ public API
def _shape_word(word: str) -> str:
    if LIBRARIES_AVAILABLE:  # pragma: no cover - depends on the environment
        return _reshaper_lib.reshape(word)
    return _shape_builtin(word)


def _to_display(shaped_line: str, rtl: bool) -> str:
    if LIBRARIES_AVAILABLE:  # pragma: no cover - depends on the environment
        return _get_display(shaped_line, base_dir="R" if rtl else "L")
    return _reorder_builtin(shaped_line, rtl)


def visual(text: str, rtl: bool = True) -> str:
    """Return `text` in visual order, ready to draw with a left-to-right renderer (one line)."""
    text = str(text if text is not None else "")
    if not has_arabic(text):
        return text
    shaped = " ".join(_shape_word(w) for w in text.split(" "))
    return _to_display(shaped, rtl)


def wrap_visual(text: str, font_name: str, font_size: float, max_width: float, rtl: bool = True) -> list[str]:
    """Greedy word wrap done on the *logical* text, then each line shaped and reordered.

    Wrapping must happen before reordering; otherwise the first words of a sentence end up on the
    wrong line. Explicit newlines in `text` start new lines.
    """
    lines: list[str] = []
    for paragraph in str(text if text is not None else "").split("\n"):
        words = paragraph.split(" ")
        current: list[str] = []
        for word in words:
            trial = " ".join(current + [word])
            width = pdfmetrics.stringWidth(" ".join(_shape_word(w) for w in trial.split(" ")),
                                           font_name, font_size)
            if current and width > max_width:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        lines.append(" ".join(current))
    return [visual(line, rtl) for line in lines]


# ------------------------------------------------------------------------- fonts
_registered: tuple[str, str] | None = None

_CANDIDATES = [  # (regular, bold) - first pair found wins
    ("NotoNaskhArabic-Regular.ttf", "NotoNaskhArabic-Bold.ttf"),
    ("Amiri-Regular.ttf", "Amiri-Bold.ttf"),
    ("Cairo-Regular.ttf", "Cairo-Bold.ttf"),
    ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
]
_SYSTEM_DIRS = [
    Path("C:/Windows/Fonts"), Path("/Library/Fonts"), Path("/System/Library/Fonts/Supplemental"),
    Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/truetype"),
]


def _find_font() -> tuple[Path, Path | None]:
    override = os.environ.get("REX_ARABIC_FONT")
    if override and Path(override).is_file():
        return Path(override), None
    for regular, bold in _CANDIDATES:
        folder = ASSETS_FONTS
        if (folder / regular).is_file():
            return folder / regular, (folder / bold if (folder / bold).is_file() else None)
    for folder in _SYSTEM_DIRS:
        for regular, bold in [("arial.ttf", "arialbd.ttf"), ("tahoma.ttf", "tahomabd.ttf"),
                              ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")]:
            if (folder / regular).is_file():
                return folder / regular, (folder / bold if (folder / bold).is_file() else None)
    raise FileNotFoundError(
        "No Arabic-capable font found. Put a TTF such as NotoNaskhArabic-Regular.ttf in rex/assets/fonts/ "
        "or set REX_ARABIC_FONT to a font file path."
    )


def register_fonts() -> tuple[str, str]:
    """Register the Arabic-capable fonts with ReportLab once; returns (regular, bold) names."""
    global _registered
    if _registered:
        return _registered
    regular, bold = _find_font()
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular)))
    if bold:
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))
        _registered = (FONT_REGULAR, FONT_BOLD)
    else:
        _registered = (FONT_REGULAR, FONT_REGULAR)
    return _registered
