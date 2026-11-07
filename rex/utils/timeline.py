"""Agent activity timeline: turns orchestrator trace events into a readable flow + HTML timeline.

An event is the dict the Orchestrator records for every agent call:
    {"at": "12:01:07", "agent": "curriculum", "action": "generate", "ok": True, "message": "...", "ms": 12}
"""
from __future__ import annotations

from html import escape

AGENTS = {  # agent name -> (English label, Arabic label, icon)
    "orchestrator": ("Orchestrator", "المنسّق", "🧭"),
    "assistant": ("REX Assistant", "مساعد REX", "💬"),
    "curriculum": ("Curriculum Agent", "وكيل المناهج", "📚"),
    "document": ("Document Agent", "وكيل المستندات", "📄"),
    "marketing": ("Marketing Agent", "وكيل التسويق", "📣"),
    "rfp": ("RFP Agent", "وكيل المناقصات", "📑"),
    "rfp_research": ("RFP Agent", "وكيل المناقصات", "📑"),
    "rfp_email": ("RFP E-mail Agent", "وكيل بريد المناقصات", "✉️"),
}


def label(agent: str, arabic: bool = False) -> str:
    en, ar, icon = AGENTS.get(agent, (agent.replace("_", " ").title(), agent, "🤖"))
    return f"{icon} {ar if arabic else en}"


def flow(events: list[dict], arabic: bool = False) -> str:
    """'Orchestrator → Curriculum Agent → Document Agent' (consecutive repeats collapsed)."""
    names: list[str] = []
    for event in events:
        if not names or names[-1] != event.get("agent"):
            names.append(event.get("agent", "?"))
    if not names:
        return ""
    return " → ".join([label("orchestrator", arabic)] + [label(n, arabic) for n in names])


def summary(events: list[dict]) -> dict:
    total_ms = sum(e.get("ms") or 0 for e in events)
    failed = sum(1 for e in events if not e.get("ok"))
    return {"steps": len(events), "failed": failed, "agents": len({e.get("agent") for e in events}),
            "total_ms": total_ms}


def timeline_html(events: list[dict], arabic: bool = False) -> str:
    """Vertical timeline; one row per agent call. All text is HTML-escaped."""
    if not events:
        return ""
    rows = []
    for event in events:
        ok = bool(event.get("ok"))
        ms = event.get("ms")
        timing = f" · {ms} ms" if ms is not None else ""
        rows.append(
            f'<div class="rex-tl-row {"ok" if ok else "bad"}">'
            f'<span class="rex-tl-dot">{"✓" if ok else "✕"}</span>'
            f'<div class="rex-tl-body"><b>{escape(label(event.get("agent", ""), arabic))}</b> '
            f'<code>{escape(str(event.get("action", "")))}</code>'
            f'<span class="rex-muted"> {escape(str(event.get("at", "")))}{timing}</span><br>'
            f'<span class="rex-tl-msg">{escape(str(event.get("message", "")))}</span></div></div>'
        )
    return '<div class="rex-timeline">' + "".join(rows) + "</div>"
