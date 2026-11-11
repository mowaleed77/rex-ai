"""Saved information: profiles, chat history, leads, curricula, campaigns, documents, email + activity logs."""
from __future__ import annotations

import json
from pathlib import Path

from .db import connect, init_db


def _rows(rows) -> list[dict]:
    return [dict(r) for r in rows]


class Store:
    def __init__(self, db_file: Path | str | None = None):
        self.db_file = db_file
        init_db(db_file)

    # ----------------------------------------------------------------- profile
    PROFILE_FIELDS = ("phone", "education", "experience", "interests", "goals",
                      "preferred_language", "consent_followup", "avatar")

    def get_profile(self, user_id: int) -> dict:
        with connect(self.db_file) as conn:
            row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        base = {f: "" for f in self.PROFILE_FIELDS}
        base.update({"preferred_language": "en", "consent_followup": 0, "avatar": ""})
        if row:
            base.update({k: v for k, v in dict(row).items() if v is not None})
        return base

    def save_profile(self, user_id: int, **fields) -> dict:
        data = {k: fields[k] for k in self.PROFILE_FIELDS if k in fields}
        if "consent_followup" in data:
            data["consent_followup"] = 1 if data["consent_followup"] else 0
        current = self.get_profile(user_id)
        current.update(data)
        with connect(self.db_file) as conn:
            conn.execute(
                "INSERT INTO profiles (user_id, phone, education, experience, interests, goals, "
                "preferred_language, consent_followup, avatar, updated_at) VALUES (?,?,?,?,?,?,?,?,?, datetime('now')) "
                "ON CONFLICT(user_id) DO UPDATE SET phone=excluded.phone, education=excluded.education, "
                "experience=excluded.experience, interests=excluded.interests, goals=excluded.goals, "
                "preferred_language=excluded.preferred_language, consent_followup=excluded.consent_followup, "
                "avatar=excluded.avatar, "
                "updated_at=datetime('now')",
                (user_id, *[current[f] for f in self.PROFILE_FIELDS]),
            )
        return current

    # -------------------------------------------------------------------- chat
    def add_message(self, user_id: int, conversation_id: str, role: str, content: str) -> None:
        with connect(self.db_file) as conn:
            conn.execute(
                "INSERT INTO chat_messages (user_id, conversation_id, role, content) VALUES (?,?,?,?)",
                (user_id, conversation_id, role, content),
            )

    def conversations(self, user_id: int, limit: int = 20) -> list[dict]:
        with connect(self.db_file) as conn:
            rows = conn.execute(
                "SELECT conversation_id, MIN(created_at) AS started, COUNT(*) AS messages, "
                "(SELECT content FROM chat_messages m2 WHERE m2.user_id = m.user_id AND "
                " m2.conversation_id = m.conversation_id AND m2.role = 'user' ORDER BY m2.id LIMIT 1) AS first_question "
                "FROM chat_messages m WHERE user_id = ? GROUP BY conversation_id "
                "ORDER BY MAX(id) DESC LIMIT ?", (user_id, limit),
            ).fetchall()
        return _rows(rows)

    def messages(self, user_id: int, conversation_id: str) -> list[dict]:
        with connect(self.db_file) as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM chat_messages WHERE user_id = ? AND conversation_id = ? "
                "ORDER BY id", (user_id, conversation_id),
            ).fetchall()
        return _rows(rows)

    def delete_history(self, user_id: int) -> None:
        with connect(self.db_file) as conn:
            conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))

    # ------------------------------------------------------------------- leads
    def add_lead(self, user_id: int | None, lead: dict) -> int:
        with connect(self.db_file) as conn:
            cur = conn.execute(
                "INSERT INTO leads (user_id, name, contact, interest, level, format, budget, recommended, consent) "
                "VALUES (?,?,?,?,?,?,?,?,1)",
                (user_id, lead.get("name"), lead.get("contact"), lead.get("interest"), lead.get("level"),
                 lead.get("format"), lead.get("budget"), lead.get("recommended")),
            )
            return cur.lastrowid

    def list_leads(self) -> list[dict]:
        with connect(self.db_file) as conn:
            return _rows(conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall())

    # ---------------------------------------------------------------- curricula
    def save_curriculum(self, user_id: int | None, curriculum: dict, status: str,
                        approved_by: str | None = None, curriculum_id: int | None = None) -> int:
        payload = json.dumps(curriculum, ensure_ascii=False)
        with connect(self.db_file) as conn:
            if curriculum_id:
                conn.execute(
                    "UPDATE curricula SET payload = ?, status = ?, version = ?, approved_by = ?, "
                    "approved_at = CASE WHEN ? IS NOT NULL THEN datetime('now') ELSE approved_at END WHERE id = ?",
                    (payload, status, curriculum.get("version", 1), approved_by, approved_by, curriculum_id),
                )
                return curriculum_id
            cur = conn.execute(
                "INSERT INTO curricula (user_id, course, language, status, version, payload, approved_by) "
                "VALUES (?,?,?,?,?,?,?)",
                (user_id, curriculum.get("course", ""), curriculum.get("language", "en"), status,
                 curriculum.get("version", 1), payload, approved_by),
            )
            return cur.lastrowid

    def list_curricula(self, user_id: int | None = None) -> list[dict]:
        sql, args = "SELECT * FROM curricula", ()
        if user_id is not None:
            sql, args = sql + " WHERE user_id = ?", (user_id,)
        with connect(self.db_file) as conn:
            rows = conn.execute(sql + " ORDER BY id DESC", args).fetchall()
        out = _rows(rows)
        for r in out:
            r["payload"] = json.loads(r["payload"])
        return out

    # --------------------------------------------------------------- campaigns
    def save_campaign(self, user_id: int | None, campaign: dict, status: str = "pending_admin_approval") -> int:
        with connect(self.db_file) as conn:
            cur = conn.execute(
                "INSERT INTO campaigns (user_id, course, language, status, payload) VALUES (?,?,?,?,?)",
                (user_id, campaign.get("course_title", ""), campaign.get("language", "en"), status,
                 json.dumps(campaign, ensure_ascii=False)),
            )
            return cur.lastrowid

    def list_campaigns(self, status: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM campaigns", ()
        if status:
            sql, args = sql + " WHERE status = ?", (status,)
        with connect(self.db_file) as conn:
            rows = conn.execute(sql + " ORDER BY id DESC", args).fetchall()
        out = _rows(rows)
        for r in out:
            r["payload"] = json.loads(r["payload"])
        return out

    def review_campaign(self, campaign_id: int, reviewer: str, approve: bool, note: str = "",
                        status: str | None = None) -> str:
        """Record an admin decision. Pass `status` for other outcomes such as 'changes_requested'."""
        status = status or ("approved" if approve else "rejected")
        with connect(self.db_file) as conn:
            conn.execute(
                "UPDATE campaigns SET status = ?, reviewed_by = ?, reviewed_at = datetime('now'), review_note = ? "
                "WHERE id = ?", (status, reviewer, note, campaign_id),
            )
        return status

    # --------------------------------------------------------------- documents
    def add_document(self, user_id: int | None, doc_type: str, title: str, language: str, file_path: str) -> int:
        with connect(self.db_file) as conn:
            cur = conn.execute(
                "INSERT INTO documents (user_id, doc_type, title, language, file_path) VALUES (?,?,?,?,?)",
                (user_id, doc_type, title, language, file_path),
            )
            return cur.lastrowid

    def list_documents(self, user_id: int | None = None) -> list[dict]:
        sql, args = "SELECT * FROM documents", ()
        if user_id is not None:
            sql, args = sql + " WHERE user_id = ?", (user_id,)
        with connect(self.db_file) as conn:
            return _rows(conn.execute(sql + " ORDER BY id DESC", args).fetchall())

    # -------------------------------------------------------------------- logs
    def log_email(self, user_id: int | None, kind: str, recipients: str, subject: str,
                  status: str, detail: str = "") -> None:
        with connect(self.db_file) as conn:
            conn.execute(
                "INSERT INTO email_log (user_id, kind, recipients, subject, status, detail) VALUES (?,?,?,?,?,?)",
                (user_id, kind, recipients, subject, status, detail[:500]),
            )

    def list_emails(self) -> list[dict]:
        with connect(self.db_file) as conn:
            return _rows(conn.execute("SELECT * FROM email_log ORDER BY id DESC LIMIT 200").fetchall())

    def log(self, user_id: int | None, username: str, action: str, detail: str = "") -> None:
        with connect(self.db_file) as conn:
            conn.execute(
                "INSERT INTO activity_log (user_id, username, action, detail) VALUES (?,?,?,?)",
                (user_id, username, action, detail[:500]),
            )

    def activity(self, limit: int = 200) -> list[dict]:
        with connect(self.db_file) as conn:
            return _rows(conn.execute(
                "SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall())
