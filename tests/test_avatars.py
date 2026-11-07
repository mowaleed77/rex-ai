import sqlite3

from rex.core.auth import AuthService
from rex.core.db import init_db
from rex.core.store import Store
from rex.utils import avatars


def test_eight_distinct_avatars_with_valid_svg():
    ids = avatars.avatar_ids()
    assert len(ids) >= 8 and avatars.DEFAULT_AVATAR in ids
    assert len({avatars.svg(i) for i in ids}) == len(ids)
    for i in ids:
        svg = avatars.svg(i)
        assert svg.startswith("<svg") and svg.endswith("</svg>") and "<script" not in svg
        assert avatars.name(i) and avatars.name(i, arabic=True)
    assert avatars.logo_svg() == avatars.svg("rex")


def test_unknown_ids_never_reach_the_page():
    assert avatars.valid("<img src=x onerror=1>") == avatars.DEFAULT_AVATAR
    assert avatars.svg(None) == avatars.logo_svg()


def test_avatar_is_saved_per_user_and_survives_profile_edits(tmp_path):
    db = tmp_path / "a.db"
    auth, store = AuthService(db), Store(db)
    a, b = auth.register("alice", "Passw0rd!x"), auth.register("bob", "Passw0rd!x")
    assert store.get_profile(a.id)["avatar"] == ""
    store.save_profile(a.id, avatar="nova")
    store.save_profile(a.id, phone="123")            # editing other fields keeps the picture
    assert store.get_profile(a.id)["avatar"] == "nova" and store.get_profile(a.id)["phone"] == "123"
    assert store.get_profile(b.id)["avatar"] == ""
    store.save_profile(a.id, avatar="")
    assert store.get_profile(a.id)["avatar"] == ""


def test_old_database_without_avatar_column_is_upgraded(tmp_path):
    db = tmp_path / "old.db"
    init_db(db)
    with sqlite3.connect(db) as conn:                 # simulate a database made before this feature
        conn.execute("ALTER TABLE profiles DROP COLUMN avatar")
    init_db(db)
    with sqlite3.connect(db) as conn:
        assert "avatar" in {r[1] for r in conn.execute("PRAGMA table_info(profiles)")}
