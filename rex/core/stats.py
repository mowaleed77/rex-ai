"""Numbers for the dashboard home page, read straight from the database.

Admins see the whole academy; a normal user sees only their own curricula and documents.
"""
from __future__ import annotations

from pathlib import Path

from .db import connect, init_db


def _group(conn, table: str, column: str, where: str = "", args: tuple = ()) -> dict[str, int]:
    rows = conn.execute(f"SELECT {column} AS k, COUNT(*) AS n FROM {table} {where} GROUP BY {column}", args)
    return {str(r["k"] or "-"): r["n"] for r in rows}


def _count(conn, table: str, where: str = "", args: tuple = ()) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table} {where}", args).fetchone()[0]


def summary(user_id: int | None = None, is_admin: bool = False, db_file: Path | str | None = None,
            courses: int = 0) -> dict:
    """`user_id` limits curricula/documents/activity to one person unless `is_admin`."""
    init_db(db_file)
    own = "" if is_admin or user_id is None else "WHERE user_id = ?"
    own_args: tuple = () if is_admin or user_id is None else (user_id,)
    with connect(db_file) as conn:
        activity = _group(conn, "activity_log", "action", own, own_args)
        by_agent: dict[str, int] = {}
        for action, n in activity.items():
            agent = action.split(":", 1)[0]
            if ":" in action:                      # only orchestrator/agent events, not sign-ins
                by_agent[agent] = by_agent.get(agent, 0) + n
        recent = [dict(r) for r in conn.execute(
            f"SELECT created_at, username, action, detail FROM activity_log {own} ORDER BY id DESC LIMIT 8",
            own_args)]
        data = {
            "courses": courses,
            "curricula": _group(conn, "curricula", "status", own, own_args),
            "documents": _group(conn, "documents", "doc_type", own, own_args),
            "agent_calls": dict(sorted(by_agent.items(), key=lambda kv: -kv[1])),
            "recent": recent,
        }
        if is_admin:
            data.update({
                "campaigns": _group(conn, "campaigns", "status"),
                "leads": _count(conn, "leads"),
                "emails_sent": _count(conn, "email_log", "WHERE status = ?", ("sent",)),
                "emails_saved": _count(conn, "email_log", "WHERE status != ?", ("sent",)),
                "users": _count(conn, "users"),
            })
    data["curricula_total"] = sum(data["curricula"].values())
    data["documents_total"] = sum(data["documents"].values())
    data["campaigns_total"] = sum(data.get("campaigns", {}).values())
    data["pending_campaigns"] = data.get("campaigns", {}).get("pending_admin_approval", 0)
    return data
