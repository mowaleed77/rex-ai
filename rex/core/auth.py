"""Authentication: sign-up, sign-in, roles (user / admin), persistent session tokens.

* Passwords are stored as salted PBKDF2-SHA256 hashes, never in plain text.
* Session tokens are random; only their SHA-256 hash is stored in the database.
* 5 wrong passwords lock the account for 10 minutes.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import connect, init_db

ROLES = ("user", "admin")
PBKDF2_ITERATIONS = 200_000
MAX_FAILED = 5
LOCK_MINUTES = 10
SESSION_DAYS = 7
DEFAULT_ADMIN_PASSWORD = "Admin@12345"   # demo default - the admin is forced to change it at first sign-in

_USERNAME_RE = re.compile(r"^[a-z0-9_.\-]{3,32}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(Exception):
    """Raised with a user-presentable message."""


@dataclass
class User:
    id: int
    username: str
    full_name: str
    email: str
    role: str
    must_change_password: bool = False

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def display_name(self) -> str:
        return self.full_name or self.username


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def hash_password(password: str, salt: bytes | None = None, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def check_password_strength(password: str) -> None:
    if len(password) < 8:
        raise AuthError("Password must be at least 8 characters.")
    if password.isdigit() or password.isalpha():
        raise AuthError("Password must mix letters with numbers or symbols.")


def _row_to_user(row) -> User:
    return User(
        id=row["id"], username=row["username"], full_name=row["full_name"] or "",
        email=row["email"] or "", role=row["role"],
        must_change_password=bool(row["must_change_password"]),
    )


class AuthService:
    def __init__(self, db_file: Path | str | None = None):
        self.db_file = db_file
        init_db(db_file)
        self.ensure_admin()

    # ------------------------------------------------------------------ setup
    def ensure_admin(self) -> None:
        """Create the first admin from REX_ADMIN_USER / REX_ADMIN_PASSWORD (or the demo default)."""
        username = (os.environ.get("REX_ADMIN_USER") or "admin").strip().lower()
        password = os.environ.get("REX_ADMIN_PASSWORD")
        with connect(self.db_file) as conn:
            if conn.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1").fetchone():
                return
            conn.execute(
                "INSERT INTO users (username, full_name, email, role, password_hash, must_change_password) "
                "VALUES (?, ?, ?, 'admin', ?, ?)",
                (username, "Administrator", os.environ.get("REX_ADMIN_EMAIL", ""),
                 hash_password(password or DEFAULT_ADMIN_PASSWORD), 0 if password else 1),
            )

    # --------------------------------------------------------------- sign up
    def register(self, username: str, password: str, full_name: str = "", email: str = "",
                 role: str = "user") -> User:
        username = (username or "").strip().lower()
        email = (email or "").strip()
        if role not in ROLES:
            raise AuthError("Unknown role.")
        if not _USERNAME_RE.match(username):
            raise AuthError("Username: 3-32 characters, letters, numbers, dot, dash or underscore.")
        if email and not _EMAIL_RE.match(email):
            raise AuthError("That email address does not look valid.")
        check_password_strength(password or "")
        with connect(self.db_file) as conn:
            if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                raise AuthError("That username is already taken.")
            cur = conn.execute(
                "INSERT INTO users (username, full_name, email, role, password_hash) VALUES (?, ?, ?, ?, ?)",
                (username, (full_name or "").strip(), email, role, hash_password(password)),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_user(row)

    # --------------------------------------------------------------- sign in
    def authenticate(self, username: str, password: str) -> User:
        username = (username or "").strip().lower()
        with connect(self.db_file) as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            generic = AuthError("Wrong username or password.")
            if row is None:
                hash_password(password or "")  # keep timing similar for unknown users
                raise generic
            if row["locked_until"] and row["locked_until"] > _fmt(_now()):
                raise AuthError(f"Too many attempts. Try again after {row['locked_until']} UTC.")
            if not verify_password(password or "", row["password_hash"]):
                failed = row["failed_attempts"] + 1
                locked = _fmt(_now() + timedelta(minutes=LOCK_MINUTES)) if failed >= MAX_FAILED else None
                conn.execute(
                    "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                    (0 if locked else failed, locked, row["id"]),
                )
                conn.commit()  # keep the counter even though we raise below
                raise generic
            conn.execute(
                "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login = ? WHERE id = ?",
                (_fmt(_now()), row["id"]),
            )
            return _row_to_user(row)

    # ---------------------------------------------------- persistent sessions
    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_session(self, user: User, days: int = SESSION_DAYS) -> str:
        token = secrets.token_urlsafe(32)
        with connect(self.db_file) as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_fmt(_now()),))
            conn.execute(
                "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (self._hash_token(token), user.id, _fmt(_now() + timedelta(days=days))),
            )
        return token

    def user_from_token(self, token: str | None) -> User | None:
        if not token:
            return None
        with connect(self.db_file) as conn:
            row = conn.execute(
                "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
                "WHERE s.token_hash = ? AND s.expires_at > ?",
                (self._hash_token(token), _fmt(_now())),
            ).fetchone()
        return _row_to_user(row) if row else None

    def end_session(self, token: str | None) -> None:
        if token:
            with connect(self.db_file) as conn:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (self._hash_token(token),))

    # --------------------------------------------------------- account admin
    def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
        check_password_strength(new_password or "")
        with connect(self.db_file) as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None or not verify_password(old_password or "", row["password_hash"]):
                raise AuthError("Current password is incorrect.")
            if old_password == new_password:
                raise AuthError("Choose a password different from the current one.")
            conn.execute(
                "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
                (hash_password(new_password), user_id),
            )
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))  # sign out other devices

    def list_users(self) -> list[dict]:
        with connect(self.db_file) as conn:
            rows = conn.execute(
                "SELECT id, username, full_name, email, role, created_at, last_login FROM users ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def set_role(self, user_id: int, role: str) -> None:
        if role not in ROLES:
            raise AuthError("Unknown role.")
        with connect(self.db_file) as conn:
            if role != "admin":
                admins = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
                current = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
                if current and current["role"] == "admin" and admins <= 1:
                    raise AuthError("At least one admin must remain.")
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))

    def reset_password(self, user_id: int, new_password: str) -> None:
        """Admin action: set a temporary password; the user must change it at next sign-in."""
        check_password_strength(new_password or "")
        with connect(self.db_file) as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, must_change_password = 1, failed_attempts = 0, "
                "locked_until = NULL WHERE id = ?", (hash_password(new_password), user_id),
            )
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    def delete_user(self, user_id: int) -> None:
        with connect(self.db_file) as conn:
            row = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
            if row and row["role"] == "admin":
                admins = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
                if admins <= 1:
                    raise AuthError("At least one admin must remain.")
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
