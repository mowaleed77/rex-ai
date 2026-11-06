"""Sign-in, roles, saved information (SQLite in a temporary file)."""
import pytest

from rex.core.auth import AuthError, AuthService, hash_password, verify_password
from rex.core.store import Store


@pytest.fixture
def services(tmp_path, monkeypatch):
    monkeypatch.setenv("REX_ADMIN_PASSWORD", "Admin#Pass123")
    db = tmp_path / "rex.db"
    return AuthService(db), Store(db)


def test_password_hash_is_salted_and_verifies():
    a, b = hash_password("Secret#123"), hash_password("Secret#123")
    assert a != b and "Secret#123" not in a
    assert verify_password("Secret#123", a) and not verify_password("wrong", a)


def test_admin_is_seeded_and_can_sign_in(services):
    auth, _ = services
    admin = auth.authenticate("admin", "Admin#Pass123")
    assert admin.is_admin and not admin.must_change_password


def test_default_admin_password_must_be_changed(tmp_path, monkeypatch):
    monkeypatch.delenv("REX_ADMIN_PASSWORD", raising=False)
    auth = AuthService(tmp_path / "x.db")
    admin = auth.authenticate("admin", "Admin@12345")
    assert admin.must_change_password
    auth.change_password(admin.id, "Admin@12345", "NewPass#2026")
    assert not auth.authenticate("admin", "NewPass#2026").must_change_password


def test_register_validation(services):
    auth, _ = services
    user = auth.register("Student1", "Student#2026", "Student One", "s@x.com")
    assert user.role == "user" and user.username == "student1"
    for bad in [("ab", "Student#2026"), ("okname", "short1"), ("okname", "onlyletters"), ("okname", "12345678")]:
        with pytest.raises(AuthError):
            auth.register(*bad)
    with pytest.raises(AuthError):
        auth.register("student1", "Student#2026")          # duplicate
    with pytest.raises(AuthError):
        auth.register("another", "Student#2026", email="not-an-email")


def test_wrong_password_and_lockout(services):
    auth, _ = services
    auth.register("lockme", "Student#2026")
    for _ in range(5):
        with pytest.raises(AuthError):
            auth.authenticate("lockme", "bad")
    with pytest.raises(AuthError) as err:
        auth.authenticate("lockme", "Student#2026")        # correct password, but locked
    assert "Too many attempts" in str(err.value)


def test_unknown_user_gets_the_same_message(services):
    auth, _ = services
    with pytest.raises(AuthError) as err:
        auth.authenticate("ghost", "whatever1")
    assert str(err.value) == "Wrong username or password."


def test_session_token_roundtrip_and_logout(services):
    auth, _ = services
    user = auth.register("tok", "Student#2026")
    token = auth.create_session(user)
    assert auth.user_from_token(token).username == "tok"
    assert auth.user_from_token("not-a-token") is None
    auth.end_session(token)
    assert auth.user_from_token(token) is None


def test_expired_session_is_rejected(services):
    auth, _ = services
    user = auth.register("old", "Student#2026")
    token = auth.create_session(user, days=-1)
    assert auth.user_from_token(token) is None


def test_password_change_signs_out_other_devices(services):
    auth, _ = services
    user = auth.register("chg", "Student#2026")
    token = auth.create_session(user)
    with pytest.raises(AuthError):
        auth.change_password(user.id, "wrong-old", "NewPass#2026")
    auth.change_password(user.id, "Student#2026", "NewPass#2026")
    assert auth.user_from_token(token) is None
    assert auth.authenticate("chg", "NewPass#2026")


def test_last_admin_cannot_be_demoted_or_deleted(services):
    auth, _ = services
    admin = auth.authenticate("admin", "Admin#Pass123")
    with pytest.raises(AuthError):
        auth.set_role(admin.id, "user")
    with pytest.raises(AuthError):
        auth.delete_user(admin.id)


def test_profile_and_chat_history_are_saved_per_user(services):
    auth, store = services
    a = auth.register("alice", "Student#2026")
    b = auth.register("bobby", "Student#2026")
    store.save_profile(a.id, phone="0100", interests="AI", consent_followup=True)
    store.save_profile(a.id, goals="Become an ML engineer")        # partial update keeps earlier fields
    prof = store.get_profile(a.id)
    assert prof["phone"] == "0100" and prof["goals"] == "Become an ML engineer" and prof["consent_followup"] == 1
    assert store.get_profile(b.id)["phone"] == ""
    store.add_message(a.id, "c1", "user", "hello")
    store.add_message(a.id, "c1", "assistant", "hi")
    assert [m["role"] for m in store.messages(a.id, "c1")] == ["user", "assistant"]
    assert store.messages(b.id, "c1") == []
    assert store.conversations(a.id)[0]["first_question"] == "hello"
    store.delete_history(a.id)
    assert store.conversations(a.id) == []


def test_campaign_review_status_is_stored(services):
    _, store = services
    cid = store.save_campaign(None, {"course_title": "X", "content": {}})
    assert store.list_campaigns()[0]["status"] == "pending_admin_approval"
    store.review_campaign(cid, "Admin", False, "needs edits", status="changes_requested")
    row = store.list_campaigns()[0]
    assert row["status"] == "changes_requested" and row["reviewed_by"] == "Admin"
