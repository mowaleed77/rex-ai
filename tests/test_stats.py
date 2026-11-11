from rex.core import stats
from rex.core.auth import AuthService
from rex.core.store import Store


def test_dashboard_numbers_for_admin_and_user(tmp_path):
    db = tmp_path / "t.db"
    auth, store = AuthService(db), Store(db)
    u1 = auth.register("alice", "Passw0rd!x")
    u2 = auth.register("bob", "Passw0rd!x")
    store.save_curriculum(u1.id, {"course": "A", "language": "en"}, "draft")
    store.save_curriculum(u1.id, {"course": "B", "language": "en"}, "approved")
    store.save_curriculum(u2.id, {"course": "C", "language": "en"}, "draft")
    store.add_document(u1.id, "curriculum_report", "t", "en", "x.pdf")
    store.save_campaign(u1.id, {"course_title": "A"})
    store.log_email(u1.id, "rfp_digest", "a@b.com", "s", "sent")
    store.log_email(u1.id, "rfp_digest", "a@b.com", "s", "saved_to_outbox")
    store.log(u1.id, "alice", "curriculum:generate", "OK")
    store.log(u2.id, "bob", "login", "x")             # not an agent event

    me = stats.summary(u1.id, False, db, courses=9)
    assert me["curricula_total"] == 2 and me["documents_total"] == 1 and "campaigns" not in me
    assert me["agent_calls"] == {"curriculum": 1}

    admin = stats.summary(None, True, db, courses=9)
    assert admin["curricula_total"] == 3 and admin["campaigns_total"] == 1 and admin["pending_campaigns"] == 1
    assert admin["emails_sent"] == 1 and admin["emails_saved"] == 1 and admin["users"] >= 3
