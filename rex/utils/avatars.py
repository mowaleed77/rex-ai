"""Chatbot avatars: the REX logo and a set of original robot profile pictures (inline SVG, no image files).

Only ids from AVATARS are ever rendered, so nothing a user types can reach the page as markup.
"""
from __future__ import annotations

DEFAULT_AVATAR = "rex"

# id -> (display name EN, display name AR, background, body, face plate, eyes/lines colour, accent)
_THEMES = {
    "rex":    ("REX", "ريكس", "#DBEAFE", "#2563EB", "#E0ECFF", "#1F3A5F", "#0F766E"),
    "nova":   ("Nova", "نوفا", "#EDE9FE", "#7C3AED", "#F3E8FF", "#3B0764", "#F59E0B"),
    "pixel":  ("Pixel", "بيكسل", "#DCFCE7", "#16A34A", "#ECFDF5", "#14532D", "#2563EB"),
    "sparky": ("Sparky", "سباركي", "#FFEDD5", "#EA580C", "#FFF7ED", "#7C2D12", "#FACC15"),
    "bolt":   ("Bolt", "بولت", "#FEE2E2", "#DC2626", "#FEF2F2", "#7F1D1D", "#1F3A5F"),
    "luna":   ("Luna", "لونا", "#FCE7F3", "#DB2777", "#FDF2F8", "#831843", "#0F766E"),
    "orbit":  ("Orbit", "أوربيت", "#E0F2FE", "#1E293B", "#334155", "#FACC15", "#38BDF8"),
    "zen":    ("Zen", "زِن", "#CCFBF1", "#0F766E", "#F0FDFA", "#134E4A", "#F59E0B"),
}

# per-avatar look: head shape, eyes, mouth, top decoration, side decoration
_LOOKS = {
    "rex":    dict(head=18, eyes="dots", mouth="smile", top="antenna", side="ears"),
    "nova":   dict(head=22, eyes="visor", mouth="line", top="twin", side="none"),
    "pixel":  dict(head=6, eyes="square", mouth="flat", top="none", side="ears"),
    "sparky": dict(head=30, eyes="big", mouth="open", top="bolt", side="cheeks"),
    "bolt":   dict(head=14, eyes="angry", mouth="smirk", top="none", side="phones"),
    "luna":   dict(head=26, eyes="happy", mouth="smile", top="cat", side="cheeks"),
    "orbit":  dict(head=20, eyes="glow", mouth="line", top="ring", side="none"),
    "zen":    dict(head=24, eyes="sleepy", mouth="smile", top="leaf", side="none"),
}


def _eyes(kind: str, ink: str) -> str:
    if kind == "dots":
        return (f'<circle cx="41" cy="52" r="4.5" fill="{ink}"/><circle cx="59" cy="52" r="4.5" fill="{ink}"/>'
                '<circle cx="42.5" cy="50.5" r="1.4" fill="#fff"/><circle cx="60.5" cy="50.5" r="1.4" fill="#fff"/>')
    if kind == "visor":
        return (f'<rect x="32" y="47" width="36" height="10" rx="5" fill="{ink}"/>'
                '<circle cx="42" cy="52" r="2.2" fill="#fff"/><circle cx="58" cy="52" r="2.2" fill="#fff"/>')
    if kind == "square":
        return (f'<rect x="36" y="47" width="9" height="9" fill="{ink}"/><rect x="55" y="47" width="9" height="9" fill="{ink}"/>')
    if kind == "big":
        return (f'<circle cx="40" cy="51" r="7" fill="#fff" stroke="{ink}" stroke-width="2"/>'
                f'<circle cx="60" cy="51" r="7" fill="#fff" stroke="{ink}" stroke-width="2"/>'
                f'<circle cx="41.5" cy="52" r="3.2" fill="{ink}"/><circle cx="58.5" cy="52" r="3.2" fill="{ink}"/>')
    if kind == "angry":
        return (f'<circle cx="41" cy="53" r="4" fill="{ink}"/><circle cx="59" cy="53" r="4" fill="{ink}"/>'
                f'<path d="M34 44 L46 48 M66 44 L54 48" stroke="{ink}" stroke-width="3" stroke-linecap="round"/>')
    if kind == "happy":
        return (f'<path d="M35 54 Q41 46 47 54 M53 54 Q59 46 65 54" fill="none" stroke="{ink}" '
                'stroke-width="3.2" stroke-linecap="round"/>')
    if kind == "glow":
        return (f'<circle cx="41" cy="52" r="6" fill="{ink}" opacity=".35"/><circle cx="59" cy="52" r="6" fill="{ink}" opacity=".35"/>'
                f'<circle cx="41" cy="52" r="3.6" fill="{ink}"/><circle cx="59" cy="52" r="3.6" fill="{ink}"/>')
    if kind == "sleepy":
        return (f'<path d="M35 52 Q41 57 47 52 M53 52 Q59 57 65 52" fill="none" stroke="{ink}" '
                'stroke-width="3.2" stroke-linecap="round"/>')
    return ""


def _mouth(kind: str, ink: str) -> str:
    return {
        "smile": f'<path d="M42 64 Q50 71 58 64" fill="none" stroke="{ink}" stroke-width="3" stroke-linecap="round"/>',
        "line": f'<path d="M43 65 H57" stroke="{ink}" stroke-width="3" stroke-linecap="round"/>',
        "flat": f'<path d="M42 65 H58" stroke="{ink}" stroke-width="3.4"/>',
        "open": f'<path d="M43 63 Q50 74 57 63 Z" fill="{ink}"/>',
        "smirk": f'<path d="M42 65 Q52 69 60 62" fill="none" stroke="{ink}" stroke-width="3" stroke-linecap="round"/>',
    }.get(kind, "")


def _top(kind: str, body: str, accent: str) -> str:
    if kind == "antenna":
        return (f'<line x1="50" y1="26" x2="50" y2="15" stroke="{body}" stroke-width="3" stroke-linecap="round"/>'
                f'<circle cx="50" cy="13" r="4.5" fill="{accent}"/>')
    if kind == "twin":
        return (f'<path d="M38 28 L33 14 M62 28 L67 14" stroke="{body}" stroke-width="3" stroke-linecap="round"/>'
                f'<circle cx="33" cy="13" r="3.6" fill="{accent}"/><circle cx="67" cy="13" r="3.6" fill="{accent}"/>')
    if kind == "bolt":
        return f'<path d="M53 8 L44 22 H51 L47 31 L58 16 H51 Z" fill="{accent}"/>'
    if kind == "cat":
        return (f'<path d="M30 34 L31 14 L44 27 Z M70 34 L69 14 L56 27 Z" fill="{body}"/>'
                f'<path d="M33 28 L33.6 19 L39 25 Z M67 28 L66.4 19 L61 25 Z" fill="{accent}"/>')
    if kind == "ring":
        return (f'<ellipse cx="50" cy="18" rx="17" ry="5" fill="none" stroke="{accent}" stroke-width="3"/>'
                f'<line x1="50" y1="23" x2="50" y2="28" stroke="{accent}" stroke-width="3"/>')
    if kind == "leaf":
        return (f'<line x1="50" y1="27" x2="50" y2="18" stroke="{body}" stroke-width="3" stroke-linecap="round"/>'
                f'<path d="M50 19 Q60 8 68 14 Q60 24 50 19 Z" fill="{accent}"/>')
    return ""


def _side(kind: str, body: str, ink: str, accent: str) -> str:
    if kind == "ears":
        return (f'<rect x="17" y="46" width="7" height="16" rx="3.5" fill="{ink}"/>'
                f'<rect x="76" y="46" width="7" height="16" rx="3.5" fill="{ink}"/>')
    if kind == "phones":
        return (f'<rect x="14" y="42" width="11" height="22" rx="5.5" fill="{ink}"/>'
                f'<rect x="75" y="42" width="11" height="22" rx="5.5" fill="{ink}"/>'
                f'<path d="M20 44 Q50 8 80 44" fill="none" stroke="{ink}" stroke-width="3"/>')
    if kind == "cheeks":
        return (f'<circle cx="31" cy="62" r="4" fill="{accent}" opacity=".55"/>'
                f'<circle cx="69" cy="62" r="4" fill="{accent}" opacity=".55"/>')
    return ""


def _svg(avatar_id: str) -> str:
    name, _, bg, body, plate, ink, accent = _THEMES[avatar_id]
    look = _LOOKS[avatar_id]
    r = look["head"]
    return (
        f'<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{name} avatar">'
        f'<rect width="100" height="100" fill="{bg}"/>'
        f'{_top(look["top"], body, accent)}{_side(look["side"], body, ink, accent)}'
        f'<rect x="22" y="28" width="56" height="52" rx="{min(r, 26)}" fill="{body}"/>'
        f'<rect x="28" y="35" width="44" height="36" rx="{max(r - 8, 4)}" fill="{plate}"/>'
        f'{_eyes(look["eyes"], ink)}{_mouth(look["mouth"], ink)}'
        f'<rect x="38" y="82" width="24" height="14" rx="6" fill="{body}"/>'
        f'<circle cx="50" cy="89" r="3" fill="{accent}"/></svg>'
    )


AVATARS: dict[str, str] = {key: _svg(key) for key in _THEMES}


def avatar_ids() -> list[str]:
    return list(AVATARS)


def valid(avatar_id: str | None) -> str:
    """Return a known avatar id (falls back to the default)."""
    return avatar_id if avatar_id in AVATARS else DEFAULT_AVATAR


def name(avatar_id: str, arabic: bool = False) -> str:
    entry = _THEMES[valid(avatar_id)]
    return entry[1] if arabic else entry[0]


def svg(avatar_id: str | None) -> str:
    return AVATARS[valid(avatar_id)]


def logo_svg() -> str:
    """The fixed REX robot used as the brand logo beside "REX AI"."""
    return AVATARS[DEFAULT_AVATAR]
