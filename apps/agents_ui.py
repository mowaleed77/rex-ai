"""REX AI - unified app: sign-in, the chatbot, the Command Center (orchestrator) and one tab per agent.

Run:  streamlit run apps/agents_ui.py

Roles
    user  : Assistant, Command Center (curriculum / documents / questions), Curriculum, Documents, My Profile
    admin : everything above + Marketing (campaign review), RFP Research (+ e-mail digest) and the Admin panel

Change who sees what in TABS below. First admin: user "admin" - see README / .env (REX_ADMIN_PASSWORD).
"""
import json
import sys
from html import escape as html_escape
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))                          # lets Python find `rex`
sys.path.insert(0, str(Path(__file__).resolve().parent))  # lets Python find ui_theme

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional
    from rex.rag.llm import load_dotenv
    load_dotenv()

import streamlit as st

st.set_page_config(page_title="REX AI | Smart Academy", page_icon="🎓", layout="wide")

import ui_theme  # noqa: E402
from rex.agents.orchestrator import Orchestrator  # noqa: E402
from rex.assistant.engine import RexAssistant, Session  # noqa: E402
from rex.core.auth import AuthError, AuthService  # noqa: E402
from rex.core import stats  # noqa: E402
from rex.core.store import Store  # noqa: E402
from rex.utils import avatars, cv_match, timeline  # noqa: E402
from rex.utils import catalog as cat  # noqa: E402

try:
    from rex.assistant.rag import RagAssistant  # noqa: E402
except Exception:  # keeps the app usable if the RAG extras are not installed
    RagAssistant = None

S = st.session_state
DOCS_DIR = ROOT / "generated_docs"
LEVELS = ["Beginner", "Intermediate", "Advanced"]
CUSTOM = "✏️ Custom course…"
ALL_CHANNELS = ["instagram", "facebook", "instagram_ad", "facebook_ad", "linkedin", "email", "whatsapp"]
STATUS_LABEL = {"draft": "Draft", "in_review": "In review", "changes_requested": "Changes requested",
                "approved": "Approved", "pending_admin_approval": "Pending admin approval", "rejected": "Rejected"}
USER_INTENTS = {"curriculum", "documents", "chat", "help"}   # what a normal user may ask the orchestrator


# ------------------------------------------------------------------ services
@st.cache_resource
def get_services():
    return AuthService(), Store()


auth, store = get_services()


@st.cache_data
def load_catalog() -> list[dict]:
    return cat.load_courses()


COURSES = load_catalog()
CATALOG = {c["title_en"]: c for c in COURSES if c.get("title_en")}


def lang() -> str:
    return S.get("ui_lang", "en")


def t(key: str) -> str:
    return ui_theme.TR[lang()].get(key) or ui_theme.TR["en"].get(key, key)


def new_assistant():
    if RagAssistant is not None:
        try:
            return RagAssistant()
        except Exception:
            pass
    return RexAssistant()


def status_pill(code: str) -> str:
    return ui_theme.pill(STATUS_LABEL.get(code, code), ui_theme.STATUS_KIND.get(code, "muted"))


def pdf_button(path: str, label: str, key: str):
    p = Path(path)
    if p.is_file():
        st.download_button(label, p.read_bytes(), file_name=p.name, mime="application/pdf", key=key)


# -------------------------------------------------------------- authentication
def start_session(user):
    S["user"] = user
    S["greet_pending"] = True                              # the robot says hello once after each sign-in
    S["token"] = auth.create_session(user, days=0.5)      # stay signed in on refresh for 12 hours
    st.query_params["s"] = S["token"]
    store.log(user.id, user.username, "sign_in")
    st.rerun()


def restore_session():
    if "user" in S:
        return S["user"]
    token = st.query_params.get("s")
    user = auth.user_from_token(token) if token else None
    if user:
        S["user"], S["token"] = user, token
    return user


def sign_out():
    user = S.get("user")
    if user:
        store.log(user.id, user.username, "sign_out")
    auth.end_session(S.get("token"))
    keep = S.get("ui_lang", "en")
    S.clear()
    S["ui_lang"] = keep
    st.query_params.clear()
    st.rerun()


def language_switch(key: str):
    choice = st.radio("Language / اللغة", ["English", "العربية"], horizontal=True, key=key,
                      index=0 if lang() == "en" else 1)
    new = "ar" if choice == "العربية" else "en"
    if new != lang():
        S["ui_lang"] = new
        st.rerun()


def login_view():
    ui_theme.inject(st, rtl=lang() == "ar")
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        language_switch("login_lang")
        ui_theme.hero(st, t("app_title"), t("tagline"), "🎓")
        tab_in, tab_up = st.tabs([t("sign_in"), t("sign_up")])
        with tab_in:
            with st.form("login_form"):
                username = st.text_input(t("username"))
                password = st.text_input(t("password"), type="password")
                go = st.form_submit_button(t("sign_in"), type="primary")
            if go:
                try:
                    start_session(auth.authenticate(username, password))
                except AuthError as error:
                    st.error(str(error))
        with tab_up:
            with st.form("signup_form"):
                full_name = st.text_input(t("full_name"))
                email = st.text_input(t("email"))
                username = st.text_input(t("username"), key="su_user")
                password = st.text_input(t("password"), type="password", key="su_pw")
                confirm = st.text_input(t("confirm"), type="password")
                go = st.form_submit_button(t("sign_up"), type="primary")
            st.caption("8+ characters, mixing letters and numbers or symbols.")
            if go:
                if password != confirm:
                    st.error(t("pw_mismatch"))
                else:
                    try:
                        user = auth.register(username, password, full_name, email)
                        st.success(t("account_created"))
                        start_session(user)
                    except AuthError as error:
                        st.error(str(error))


def force_password_change(user):
    ui_theme.inject(st, rtl=lang() == "ar")
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        ui_theme.hero(st, t("change_pw_title"), t("change_pw_info"), "🔒")
        with st.form("force_pw"):
            old = st.text_input(t("current_pw"), type="password")
            new = st.text_input(t("new_pw"), type="password")
            go = st.form_submit_button(t("save"), type="primary")
        if go:
            try:
                auth.change_password(user.id, old, new)
                store.log(user.id, user.username, "password_changed")
                user.must_change_password = False
                start_session(user)   # old sessions were revoked, so open a fresh one
            except AuthError as error:
                st.error(str(error))
        if st.button(t("sign_out")):
            sign_out()


# ------------------------------------------------------------------- runtime
def ensure_runtime(user):
    if "assistant" not in S:
        S["assistant"] = new_assistant()
        S["chat_session"] = Session()
        S["conv_id"] = uuid.uuid4().hex
        S["chat_messages"] = []
    if "rex" not in S:
        folder = DOCS_DIR / user.username
        S["rex"] = Orchestrator(
            docs_dir=folder, courses=COURSES, assistant=S["assistant"],
            on_event=lambda e: store.log(user.id, user.username, f"{e['agent']}:{e['action']}",
                                         ("OK " if e["ok"] else "FAILED ") + e["message"]),
        )
    S.setdefault("ctx", {})


def persist_curriculum(user, curriculum: dict):
    ctx = S["ctx"]
    if ctx.get("cur_db_id") and ctx.get("cur_db_course") == curriculum["course"]:
        store.save_curriculum(user.id, curriculum, curriculum.get("status_code", "draft"),
                              curriculum.get("approved_by"), curriculum_id=ctx["cur_db_id"])
    else:
        ctx["cur_db_id"] = store.save_curriculum(user.id, curriculum, curriculum.get("status_code", "draft"),
                                                 curriculum.get("approved_by"))
        ctx["cur_db_course"] = curriculum["course"]


def persist_campaign(user, campaign: dict):
    key = (campaign.get("course_title"), campaign.get("history", [{}])[0].get("at"))
    ctx = S["ctx"]
    if ctx.get("camp_db_key") != key:
        ctx["camp_db_id"] = store.save_campaign(user.id, campaign)
        ctx["camp_db_key"] = key


def persist_pdfs(user, pdfs: dict, language: str):
    saved = S["ctx"].setdefault("saved_pdfs", [])
    for doc_type, path in pdfs.items():
        if path not in saved:
            store.add_document(user.id, doc_type, Path(path).stem, language, path)
            saved.append(path)


# ----------------------------------------------------------------- sidebar
NAV_GROUPS = [  # (group label key, [tab keys])
    ("nav_overview", ["dashboard"]),
    ("nav_agents", ["assistant", "command", "curriculum", "documents", "marketing", "rfp"]),
    ("nav_account", ["profile"]),
    ("nav_admin", ["admin"]),
]


def go(key: str):
    S["nav"] = key


def sidebar(user, visible):
    """Brand, user card, grouped navigation (agents / account / admin), language, status, sign-out."""
    by_key = {row[0]: row for row in visible}
    if S.get("nav") not in by_key:
        S["nav"] = visible[0][0]
    with st.sidebar:
        st.markdown(f'<div class="rex-brand"><span class="rex-logo">{avatars.logo_svg()}</span>'
                    f'<div><b>REX AI</b><br><small>{t("brand_sub")}</small></div></div>', unsafe_allow_html=True)
        chosen = store.get_profile(user.id).get("avatar")
        picture = avatars.svg(chosen) if chosen in avatars.AVATARS else None
        initial = html_escape((user.display_name[:1] or "?").upper())
        st.markdown(
            f'<div class="rex-user"><div class="rex-avatar">{picture or initial}</div>'
            f'<div><b>{html_escape(user.display_name)}</b><br>'
            f'{ui_theme.pill(t("role_admin") if user.is_admin else t("role_user"), "info")}</div></div>',
            unsafe_allow_html=True)
        for group_label, keys in NAV_GROUPS:
            rows = [by_key[k] for k in keys if k in by_key]
            if not rows:
                continue
            st.markdown(f'<div class="rex-nav-title">{t(group_label)}</div>', unsafe_allow_html=True)
            for key, label, icon, _, _ in rows:
                st.button(f"{icon}  {t(label)}", key=f"nav_{key}", use_container_width=True,
                          type="primary" if S["nav"] == key else "secondary",
                          on_click=go, args=(key,))
        st.markdown('<div class="rex-nav-title">' + t("nav_settings") + "</div>", unsafe_allow_html=True)
        language_switch("side_lang")
        bot = S.get("assistant")
        if getattr(bot, "llm_enabled", False):
            st.success(f"LLM + RAG · {getattr(bot.llm, 'model', 'LLM')}")
        else:
            st.caption("⚙️ Rule-based mode (no LLM key)")
        if hasattr(bot, "retriever") and hasattr(bot.retriever, "chunks"):
            st.caption(f"{len(bot.retriever.chunks)} knowledge documents loaded")
        if st.button("🚪  " + t("sign_out"), use_container_width=True):
            sign_out()


# ------------------------------------------------------------ tab: dashboard
def _chart(data: dict, title: str):
    if not data:
        return
    st.markdown(f"**{title}**")
    st.bar_chart(data)


def render_dashboard(user):
    data = stats.summary(user.id, user.is_admin, courses=len(COURSES))
    st.caption("Admin view - the whole academy." if user.is_admin else "Your activity.")
    cards = [("Courses in catalog", data["courses"]), ("Curricula", data["curricula_total"]),
             ("PDF documents", data["documents_total"])]
    if user.is_admin:
        cards += [("Campaigns", data["campaigns_total"]), ("Awaiting approval", data["pending_campaigns"]),
                  ("Leads", data["leads"]), ("RFP e-mails", data["emails_sent"] + data["emails_saved"]),
                  ("Users", data["users"])]
    for row in range(0, len(cards), 4):
        cols = st.columns(4)
        for col, (label, value) in zip(cols, cards[row:row + 4]):
            col.metric(label, value)

    left, right = st.columns(2)
    with left:
        _chart({STATUS_LABEL.get(k, k): v for k, v in data["curricula"].items()}, "Curricula by status")
        _chart({k.replace("_", " "): v for k, v in data["documents"].items()}, "Documents by type")
    with right:
        _chart({timeline.label(k).split(" ", 1)[-1]: v for k, v in data["agent_calls"].items()},
               "Agent calls")
        if user.is_admin:
            _chart({STATUS_LABEL.get(k, k): v for k, v in data["campaigns"].items()}, "Campaigns by status")
    if not any((data["curricula_total"], data["documents_total"], data["agent_calls"])):
        st.info("Nothing here yet. Open the Command Center and try: “Launch the Excel for Business Analysis course”.")

    st.markdown("**Quick start**")
    q1, q2, q3 = st.columns(3)
    q1.button("💬 Ask the assistant", key="qs_chat", on_click=go, args=("assistant",), use_container_width=True)
    q2.button("🧭 Launch a course", key="qs_cmd", on_click=go, args=("command",), use_container_width=True)
    q3.button("📚 New curriculum", key="qs_cur", on_click=go, args=("curriculum",), use_container_width=True)

    live = (S.get("rex").trace if S.get("rex") else [])
    if live:
        st.markdown("**Latest agent activity (this session)**")
        events = live[-8:]
        st.markdown(f'<div class="rex-flow">{timeline.flow(events, lang() == "ar")}</div>', unsafe_allow_html=True)
        st.markdown(timeline.timeline_html(events, lang() == "ar"), unsafe_allow_html=True)
    elif data["recent"]:
        st.markdown("**Recent activity**")
        st.dataframe(data["recent"])


# ------------------------------------------------------------------- tab: chat
def render_cv_match(user):
    """Upload a CV or describe interests -> top course matches. Nothing is stored unless the user asks."""
    arabic = lang() == "ar"
    st.caption("Upload a CV (.pdf, .docx, .txt) or describe your skills and goals. REX matches them to our courses. "
               "Your text is analysed in memory and is not saved." if not arabic else
               "ارفع سيرتك الذاتية أو اكتب مهاراتك وأهدافك، وسيطابقها REX مع دورات الأكاديمية. لا يتم حفظ النص.")
    upload = st.file_uploader("CV file", type=["pdf", "docx", "txt", "md"], key="cv_file")
    typed = st.text_area("…or describe your background, skills and goals", key="cv_text", height=110)
    if st.button("🔎 Find my courses", key="cv_go", type="primary"):
        text, error = typed or "", None
        if upload is not None:
            try:
                text = cv_match.extract_text(upload.getvalue(), upload.name) + "\n" + text
            except ValueError as problem:
                error = str(problem)
        if error:
            st.warning(error)
        else:
            S["cv_result"] = cv_match.recommend(text, COURSES, arabic=arabic)
    result = S.get("cv_result")
    if not result:
        return
    if not result["ok"]:
        st.info(result["message"])
        return
    years = f"{result['years']} years" if result.get("years") else "not stated"
    st.markdown(f"**Suggested starting level:** {result['level']} · **Experience:** {years}")
    if result["skills"]:
        st.markdown("**Skills found:** " + ", ".join(f"`{x}`" for x in result["skills"]))
    for i, rec in enumerate(result["recommendations"]):
        c = rec["course"]
        st.markdown(
            f'<div class="rex-card"><h4>{rec["title"]} {ui_theme.pill(str(rec["score"]) + "% match", "ok")}</h4>'
            f'<span class="rex-muted">{c.get("level")} · {c.get("duration_hours")} h · {c.get("price_egp")} EGP</span>'
            f'<br>{rec["reason"]}</div>', unsafe_allow_html=True)
    if st.button("💾 Save these interests to my profile", key="cv_save"):
        titles = ", ".join(r["course"]["title_en"] for r in result["recommendations"])
        store.save_profile(user.id, interests=titles)
        st.success("Saved to My Profile.")


def render_chat(user):
    st.subheader("💬 " + t("tab_assistant"))
    messages = S["chat_messages"]
    if not messages:
        st.markdown(f'<div class="rex-card"><h4>{t("chat_welcome")}</h4>'
                    '<span class="rex-muted">Try: “I want to start a career in data” · “Show all courses” · '
                    '“ما هي الدورات المتاحة؟”</span></div>', unsafe_allow_html=True)
    for m in messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"].replace("\n", "  \n"))

    with st.expander("📎 " + ("Match my CV to courses" if lang() != "ar" else "طابق سيرتي الذاتية مع الدورات")):
        render_cv_match(user)

    with st.form("chat_form", clear_on_submit=True):
        text = st.text_input("Message", placeholder=t("chat_placeholder"), label_visibility="collapsed")
        c1, c2, c3 = st.columns([1, 1, 3])
        sent = c1.form_submit_button("Send", type="primary")
        reset = c2.form_submit_button(t("new_chat"))

    if reset:
        S["assistant"] = new_assistant()
        S["chat_session"], S["conv_id"], S["chat_messages"] = Session(), uuid.uuid4().hex, []
        st.rerun()
    if sent and text.strip():
        text = text.strip()
        messages.append({"role": "user", "content": text})
        store.add_message(user.id, S["conv_id"], "user", text)
        try:
            reply = str(S["assistant"].reply(S["chat_session"], text))
        except Exception as error:  # keep the UI alive on any agent error
            reply = f"Sorry, something went wrong: {error}"
        messages.append({"role": "assistant", "content": reply})
        store.add_message(user.id, S["conv_id"], "assistant", reply)
        st.rerun()

    if messages:
        with st.expander(t("share_details")):
            st.caption(t("share_help"))
            profile = store.get_profile(user.id)
            contact = profile.get("phone") or user.email
            if st.button(t("share_details"), key="share_lead"):
                if not contact:
                    st.warning(t("need_contact"))
                else:
                    sess = S["chat_session"]
                    store.add_lead(user.id, {
                        "name": user.display_name, "contact": contact,
                        "interest": " ".join(dict.fromkeys(getattr(sess, "interest", []))),
                        "level": getattr(sess, "level", None), "format": getattr(sess, "fmt", None),
                        "budget": getattr(sess, "budget", None),
                        "recommended": "|".join(c["id"] for c in getattr(sess, "last_courses", []))})
                    store.save_profile(user.id, consent_followup=1)
                    st.success(t("lead_saved"))


# ------------------------------------------------------- tab: command center
def run_command(user, text: str, approved_by: str | None = None):
    rex = S["rex"]
    allowed = None if user.is_admin else USER_INTENTS
    intent = rex.parse_request(text)["intent"]
    log = S.setdefault("cc_log", [])
    log.append({"role": "user", "text": text})
    if allowed is not None and intent not in allowed:
        log.append({"role": "assistant", "text": "That action needs an admin account "
                    "(marketing campaigns and tender research are admin-only).", "result": None, "source": text})
        return
    options = {"use_llm": bool(S.get("cc_llm")), "approved_by": approved_by}
    before = len(rex.trace)
    res = rex.handle(text, S["ctx"], **options)
    events = list(rex.trace[before:]) if len(rex.trace) >= before else list(rex.trace)
    S["ctx"].update(res.context)
    arts = res.artifacts
    if arts.get("curriculum"):
        persist_curriculum(user, arts["curriculum"])
    if arts.get("campaign"):
        persist_campaign(user, arts["campaign"])
    if arts.get("pdfs"):
        persist_pdfs(user, arts["pdfs"], (arts.get("curriculum") or {}).get("language", "en"))
    log.append({"role": "assistant", "text": res.message, "result": res, "source": text, "events": events})


def render_result(user, entry, index: int):
    res = entry["result"]
    if res is None:
        return
    events = entry.get("events") or []
    if events:
        st.markdown(f'<div class="rex-flow">{timeline.flow(events, lang() == "ar")}</div>', unsafe_allow_html=True)
        info = timeline.summary(events)
        st.caption(f"{info['steps']} agent call(s) · {info['agents']} agent(s) · {info['total_ms']} ms"
                   + (f" · {info['failed']} failed" if info["failed"] else ""))
        with st.expander("Agent activity timeline", expanded=True):
            st.markdown(timeline.timeline_html(events, lang() == "ar"), unsafe_allow_html=True)
    if res.steps:
        with st.expander("What I did", expanded=False):
            for s in res.steps:
                st.markdown(f"{'✅' if s['ok'] else '❌'} **{s['step']}** · `{s['agent']}` — {s['message']}")
    arts = res.artifacts
    if arts.get("curriculum"):
        c = arts["curriculum"]
        st.markdown(f"**Curriculum:** {c['course']} · v{c.get('version', 1)} · "
                    + status_pill(c.get("status_code", "draft")), unsafe_allow_html=True)
    for doc_type, path in (arts.get("pdfs") or {}).items():
        pdf_button(path, f"⬇ {doc_type.replace('_', ' ').title()} (PDF)", f"cc_pdf_{index}_{doc_type}")
    if arts.get("campaign"):
        camp = arts["campaign"]
        total = sum(len(v) for v in camp["content"].values())
        st.markdown(f"**Campaign:** {total} pieces · " + status_pill(camp.get("status", "pending_admin_approval")),
                    unsafe_allow_html=True)
        st.caption("Review it in the Marketing tab - nothing is published without an admin's approval.")
    if arts.get("rfp"):
        out = arts["rfp"]
        st.dataframe([{k: o.get(k) for k in ("title", "country", "organization", "deadline", "review_route")}
                      for o in out["opportunities"]])
    if arts.get("email"):
        st.info(f"E-mail: {arts['email'].get('status', 'previewed')} · {arts['email'].get('subject', '')}")
    if res.awaiting == "curriculum_approval":
        if user.is_admin:
            if st.button("✅ Approve the curriculum and continue", key=f"cc_approve_{index}", type="primary"):
                S["cc_pending"] = {"text": entry["source"], "by": user.display_name}
                st.rerun()
        else:
            st.info("An admin must approve this curriculum before the next steps can run.")
    if res.needs_input:
        st.info("I still need: " + ", ".join(res.needs_input).replace("_", " "))


def render_command(user):
    st.subheader("🧭 " + t("tab_command"))
    st.caption("Tell the orchestrator what you need in plain English or Arabic. It decides which agents to call, "
               "passes the results between them and stops for human approval where it matters.")
    pending = S.pop("cc_pending", None)
    if pending:
        run_command(user, pending["text"], approved_by=pending["by"])

    examples = ["Launch the Excel for Business Analysis course",
                "Create a curriculum for Cybersecurity Essentials",
                "اعمل منهج لدورة أساسيات تعلم الآلة"]
    if user.is_admin:
        examples += ["Write a LinkedIn and WhatsApp campaign for Digital Marketing Fundamentals",
                     "Find training tenders in Egypt and Saudi Arabia"]
    cols = st.columns(len(examples))
    for i, ex in enumerate(examples):
        if cols[i].button(ex, key=f"cc_ex_{i}"):
            run_command(user, ex)
            st.rerun()

    for i, entry in enumerate(S.get("cc_log", [])):
        with st.chat_message(entry["role"]):
            st.markdown(entry["text"].replace("\n", "  \n"))
            if entry["role"] == "assistant":
                render_result(user, entry, i)

    with st.form("cc_form", clear_on_submit=True):
        text = st.text_input("Request", placeholder="e.g. Launch the Python for Data Analysis course in Arabic",
                             label_visibility="collapsed")
        c1, c2 = st.columns([1, 3])
        go = c1.form_submit_button("Run", type="primary")
        c2.checkbox("Use AI generation when an LLM key is configured", key="cc_llm")
    if go and text.strip():
        run_command(user, text.strip())
        st.rerun()


# ------------------------------------------------------------ tab: curriculum
def _load_course_defaults():
    entry = CATALOG.get(S.get("cur_choice"))
    ar = S.get("cur_lang") == "العربية"
    if entry:
        S["cur_level"] = entry.get("level", "Beginner")
        S["cur_hours"] = float(entry.get("duration_hours", 24))
        outcomes = (entry.get("learning_outcomes_ar") if ar else None) or entry.get("learning_outcomes", [])
        S["cur_outcomes"] = "\n".join(outcomes)


def render_curriculum(user):
    rex, ctx = S["rex"], S["ctx"]
    st.subheader("📚 " + t("tab_curriculum"))
    st.caption("Design a curriculum, review it, request changes, and approve it. Approved curricula feed the "
               "PDF and marketing agents. Nothing here claims official accreditation.")
    options = list(CATALOG) + [CUSTOM]
    if "cur_choice" not in S:
        S["cur_choice"], S["cur_lang"] = options[0], "English"
        _load_course_defaults()
    S.setdefault("cur_level", "Beginner")
    S.setdefault("cur_hours", 24.0)
    S.setdefault("cur_outcomes", "")

    left, right = st.columns(2)
    with left:
        choice = st.selectbox("Course (from the academy catalog)", options, key="cur_choice",
                              on_change=_load_course_defaults)
        title = st.text_input("Custom course title", key="cur_custom") if choice == CUSTOM else choice
        st.radio("Curriculum language", ["English", "العربية"], horizontal=True, key="cur_lang",
                 on_change=_load_course_defaults)
        st.selectbox("Level", LEVELS, key="cur_level")
        st.number_input("Total training hours", min_value=1.0, step=1.0, key="cur_hours")
    with right:
        st.text_area("Learning outcomes (one per line) — loaded from the catalog, edit freely",
                     height=215, key="cur_outcomes")
    use_llm = st.checkbox("Use AI generation (needs LLM_API_KEY in .env; otherwise a level-based template is used)",
                          value=True, key="cur_use_llm")

    if st.button("Generate curriculum", type="primary", key="cur_generate"):
        outcomes = [l.strip() for l in S["cur_outcomes"].splitlines() if l.strip()]
        language = "ar" if S["cur_lang"] == "العربية" else "en"
        shown = title
        if choice != CUSTOM and language == "ar":
            shown = CATALOG[choice].get("title_ar") or title
        res = rex.dispatch("curriculum", {
            "action": "generate", "course": shown, "level": S["cur_level"], "duration_hours": S["cur_hours"],
            "learning_outcomes": outcomes, "use_llm": use_llm, "language": language})
        if res.ok:
            ctx["curriculum"] = res.output
            ctx["course_info"] = CATALOG.get(choice)
            ctx.pop("cur_db_id", None)
            S.pop("gap_result", None)
            persist_curriculum(user, res.output)
            st.success(res.message)
        else:
            st.error(f"❌ {res.message}")

    cur = ctx.get("curriculum")
    if not cur:
        st.info("Generate a curriculum to review it here.")
        return

    code = cur.get("status_code", "draft")
    st.markdown(f"### {cur['course']} &nbsp; {status_pill(code)}", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Version", cur.get("version", 1))
    m2.metric("Modules", len(cur["modules"]))
    m3.metric("Total hours", f"{cur['duration_hours']:g}")
    m4.metric("Level", cur["level"])
    st.caption(f"{cur['status']} · generated by: {cur.get('generated_by', 'template')}")
    st.markdown(f"**Prerequisites:** {cur['prerequisites']}")
    st.dataframe([{"#": m["module"], "Module": m["title"], "Hours": m["duration_hours"],
                   "Topics": ", ".join(m.get("topics", [])), "Activity": m.get("activity", "")}
                  for m in cur["modules"]])
    a, b = st.columns(2)
    a.markdown("**Objectives**\n" + "\n".join(f"- {o}" for o in cur["objectives"]))
    b.markdown("**Assessments**\n" + "\n".join(f"- {o}" for o in cur["assessments"])
               + f"\n\n**Capstone:** {cur['capstone']}")

    st.markdown("#### 🔁 Review and revise")
    st.caption("Describe the change in your own words, e.g. “add module Data ethics 4 hours”, “remove module 2”, "
               "“rename module 1 to Python basics”, “capstone: build a dashboard”, “total hours 50”, "
               "or in Arabic: “أضف وحدة أخلاقيات البيانات 4 ساعة”.")
    with st.form("revise_form", clear_on_submit=True):
        instruction = st.text_area("Requested changes", height=80, label_visibility="collapsed")
        ai_ops = st.checkbox("Let the AI interpret the request (needs an LLM key)", key="revise_llm")
        go = st.form_submit_button("Apply changes", type="primary")
    if go and instruction.strip():
        res = rex.dispatch("curriculum", {"action": "revise", "curriculum": cur,
                                          "instruction": instruction, "use_llm": ai_ops})
        if res.ok:
            ctx["curriculum"] = res.output
            persist_curriculum(user, res.output)
            st.success(res.message)
            st.rerun()
        else:
            st.error(res.message)

    if user.is_admin:
        st.markdown("#### ✅ Decision")
        note = st.text_input("Note for the record (required when requesting changes)", key="cur_note")
        d1, d2, _ = st.columns([1, 1, 2])
        if d1.button("Approve", type="primary", key="cur_approve", disabled=code == "approved"):
            res = rex.dispatch("curriculum", {"action": "approve", "curriculum": cur,
                                              "reviewer": user.display_name, "note": note})
            if res.ok:
                ctx["curriculum"] = res.output
                persist_curriculum(user, res.output)
                st.rerun()
            st.error(res.message)
        if d2.button("Request changes", key="cur_changes"):
            res = rex.dispatch("curriculum", {"action": "request_changes", "curriculum": cur,
                                              "reviewer": user.display_name, "note": note})
            if res.ok:
                ctx["curriculum"] = res.output
                persist_curriculum(user, res.output)
                st.rerun()
            st.error(res.message)
    else:
        st.caption("An admin approves curricula. Once approved, you can create final PDFs and campaigns from it.")

    with st.expander("History"):
        for h in cur.get("history", []):
            who = f" by {h['by']}" if h.get("by") else ""
            note = f" — {h['note']}" if h.get("note") else ""
            st.markdown(f"- v{h.get('version', '')} **{h['event']}**{who} · {h['at']}{note}")

    st.markdown("#### 📐 Gap analysis")
    st.caption("Checks the curriculum against a list of required topics (accreditation framework, employer or "
               "academy standard). It is an alignment check, never an official accreditation.")
    required_raw = st.text_area("Required topics (one per line)",
                                "\n".join((ctx.get("course_info") or {}).get("learning_outcomes", [])) or "SQL",
                                height=100, key=f"required_{cur['course']}")
    if st.button("Run gap analysis", key="cur_gap"):
        required = [l.strip() for l in required_raw.splitlines() if l.strip()]
        S["gap_result"] = rex.dispatch("curriculum", {
            "action": "gap_analysis", "required_topics": required,
            "curriculum": [{"topics": m.get("topics") or [m["title"]]} for m in cur["modules"]]})
    gap = S.get("gap_result")
    if gap:
        if not gap.ok:
            st.error(gap.message)
        else:
            g = gap.output
            g1, g2 = st.columns(2)
            g1.metric("Coverage", f"{g['coverage_percentage']}%")
            g2.metric("Accreditation", g["accreditation_status"])
            st.write("✅ Covered:", g["covered_topics"] or "None")
            st.write("❌ Missing:", g["missing_topics"] or "None")


# ------------------------------------------------------------- tab: documents
DOC_TYPES = ["curriculum_report", "course_description", "gap_analysis"]


def render_documents(user):
    rex, ctx = S["rex"], S["ctx"]
    st.subheader("📄 " + t("tab_documents"))
    st.caption("Professional PDFs in English or Arabic (right-to-left). Documents are built straight from the "
               "curriculum, so there is nothing to retype.")
    mode = st.radio("Source", ["From the current curriculum", "Custom content (advanced)"],
                    horizontal=True, key="doc_mode")
    folder = DOCS_DIR / user.username
    result = None

    if mode.startswith("From"):
        cur = ctx.get("curriculum")
        if not cur:
            st.info("No curriculum yet. Create one in the Curriculum tab, or ask the Command Center "
                    "(“Create a curriculum for …”).")
        else:
            st.markdown(f"**Using:** {cur['course']} · v{cur.get('version', 1)} · "
                        + status_pill(cur.get("status_code", "draft")), unsafe_allow_html=True)
            if cur.get("status_code") != "approved":
                st.warning("This curriculum is not approved yet. The PDF will be marked DRAFT.")
            c1, c2, c3 = st.columns(3)
            doc_type = c1.selectbox("Document type", DOC_TYPES, key="doc_type")
            language = c2.selectbox("PDF language", ["auto", "en", "ar"], key="doc_lang",
                                    help="auto follows the curriculum language")
            title = c3.text_input("Title (optional)", key="doc_title")
            if doc_type == "gap_analysis" and not S.get("gap_result"):
                st.info("Run the gap analysis in the Curriculum tab first, then come back.")
            elif st.button("Generate PDF", type="primary", key="doc_go"):
                task = {"document_type": doc_type, "curriculum": cur, "course_info": ctx.get("course_info"),
                        "language": cur.get("language", "en") if language == "auto" else language,
                        "output_dir": str(folder)}
                if title.strip():
                    task["title"] = title.strip()
                if doc_type == "gap_analysis":
                    task["gap"] = S["gap_result"].output
                result = rex.dispatch("document", task)
    else:
        defaults = json.dumps({"overview": "…", "objectives": ["…"], "modules": [
            {"title": "Module 1", "topics": ["Topic"], "hours": 6}], "assessments": ["Quiz"],
            "capstone": "…"}, indent=2, ensure_ascii=False)
        c1, c2 = st.columns(2)
        doc_type = c1.selectbox("Document type", DOC_TYPES, key="doc_type2")
        language = c2.selectbox("PDF language", ["auto", "en", "ar"], key="doc_lang2")
        title = st.text_input("Title", "Custom document", key="doc_title2")
        raw = st.text_area("Content JSON (schema depends on the document type)", defaults, height=260, key="doc_json")
        if st.button("Generate PDF", type="primary", key="doc_go2"):
            try:
                content = json.loads(raw)
            except json.JSONDecodeError as error:
                st.error(f"Invalid JSON: {error}")
            else:
                result = rex.dispatch("document", {
                    "document_type": doc_type, "title": title, "content": content, "language": language,
                    "metadata": {"Date": str(date.today())}, "output_dir": str(folder)})

    if result is not None:
        if result.ok:
            path = result.output["file_path"]
            persist_pdfs(user, {result.output["document_type"]: path}, result.output["language"])
            S["doc_last"] = path
        else:
            st.error(f"❌ {result.message}")
    if S.get("doc_last") and Path(S["doc_last"]).is_file():
        st.success("PDF created.")
        pdf_button(S["doc_last"], "⬇ Download PDF", "doc_dl_last")

    st.markdown("#### Saved documents")
    docs = store.list_documents(None if user.is_admin else user.id)[:10]
    if not docs:
        st.caption("Nothing saved yet.")
    for d in docs:
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**{d['title']}** · {d['doc_type']} · {d['language']} · {d['created_at']}")
        with c2:
            pdf_button(d["file_path"], "⬇", f"doc_saved_{d['id']}")


# ------------------------------------------------------------- tab: marketing
def _marketing_course_defaults():
    S.pop("mkt_result", None)


def render_marketing(user):
    rex, ctx = S["rex"], S["ctx"]
    st.subheader("📣 " + t("tab_marketing"))
    st.caption("Generates multi-channel content in English and Arabic from approved course data. "
               "Nothing is published without an admin's approval.")
    cur = ctx.get("curriculum")
    options = list(CATALOG) + [CUSTOM]
    default_index = 0
    if cur and cur["course"] in CATALOG:
        default_index = options.index(cur["course"])
    left, right = st.columns(2)
    with left:
        choice = st.selectbox("Course", options, index=default_index, key="mkt_choice",
                              on_change=_marketing_course_defaults)
        entry = CATALOG.get(choice)
        title = st.text_input("Custom course title", key="mkt_title") if choice == CUSTOM else choice
        if choice == CUSTOM:
            desc = st.text_area("Short description", key="mkt_desc", height=80)
        if cur and cur["course"].casefold() == (title or "").casefold():
            st.caption("Facts are also checked against the current curriculum "
                       f"({STATUS_LABEL.get(cur.get('status_code', 'draft'))}).")
        objective = st.selectbox("Campaign objective", ["leads", "awareness", "enrollment"], key="mkt_obj")
        budget = st.text_input("Budget (optional)", key="mkt_budget")
        cta = st.text_input("Custom call to action (optional)", key="mkt_cta")
    with right:
        language = st.radio("Language", ["en", "ar", "both"], horizontal=True, key="mkt_lang",
                            format_func=lambda v: {"en": "English", "ar": "العربية", "both": "Both"}[v])
        audience = st.text_input("Target audience (optional - catalog value is used otherwise)", key="mkt_aud")
        channels = st.multiselect("Channels", ALL_CHANNELS, default=["instagram", "linkedin", "whatsapp"],
                                  key="mkt_channels")
        variations = st.slider("Variations per channel", 1, 5, 2, key="mkt_vars")
        use_llm = st.checkbox("Use AI copywriting (needs an LLM key; facts are still checked)", key="mkt_llm")

    if st.button("Generate campaign", type="primary", key="mkt_go"):
        course = cat.marketing_view(entry) if entry else {"title": title, "description": S.get("mkt_desc", "")}
        task = {"course": course, "channels": channels, "variations": variations, "language": language,
                "objective": objective, "use_llm": use_llm,
                "curriculum": cur if cur and cur["course"].casefold() == (title or "").casefold() else None}
        for key, val in (("target_audience", audience.strip()), ("budget", budget.strip()), ("cta", cta.strip())):
            if val:
                task[key] = val
        res = rex.dispatch("marketing", task)
        if res.ok:
            ctx["campaign"] = res.output
            persist_campaign(user, res.output)
        else:
            st.error(f"❌ {res.message}")

    camp = ctx.get("campaign")
    if not camp:
        return
    st.markdown(f"### {camp['course_title']} &nbsp; {status_pill(camp['status'])}", unsafe_allow_html=True)
    for w in camp.get("warnings", []):
        st.warning(w)
    m1, m2, m3 = st.columns(3)
    m1.metric("Approved", "Yes" if camp["approved"] else "No")
    m2.metric("Published", "No")
    m3.metric("Generated by", camp.get("generated_by", "template"))

    with st.expander("Campaign strategy", expanded=True):
        s = camp["campaign_strategy"]
        st.markdown(f"**Goal:** {s['goal']}  \n**Audience:** {s['target_audience']}")
        st.markdown("**Key messages**\n" + "\n".join(f"- {m}" for m in s["key_messages"] if m))
        st.dataframe(s["posting_calendar_7_days"])
        st.markdown("**KPIs:** " + " · ".join(s["kpis"]))
        if s.get("budget_note"):
            st.info(s["budget_note"])
    with st.expander("Headlines, calls to action and hashtags"):
        st.markdown("**Headlines**\n" + "\n".join(f"- {h}" for h in camp["headlines"]))
        st.markdown("**Calls to action**\n" + "\n".join(f"- {c}" for c in camp["call_to_actions"]))
        st.markdown("**Hashtags:** " + " ".join(camp["hashtags"]))
    for channel, items in camp["content"].items():
        with st.expander(f"{channel.replace('_', ' ').title()} · {len(items)} variation(s)", expanded=False):
            for item in items:
                st.markdown(f"**Variation {item['variation']}** · {item.get('language', '')} · _{item['headline']}_")
                if item.get("subject"):
                    st.markdown(f"**Subject:** {item['subject']}")
                st.text(item["text"])
                st.caption(f"CTA: {item['call_to_action']}")

    st.markdown("#### ✅ Admin review")
    if not user.is_admin:
        st.info("An admin reviews campaigns before anything is published.")
        return
    note = st.text_input("Review note (required to reject or request changes)", key="mkt_note")
    a, b, c, _ = st.columns([1, 1, 1, 1])
    for col, label, action in ((a, "Approve", "approve"), (b, "Request changes", "request_changes"),
                               (c, "Reject", "reject")):
        if col.button(label, key=f"mkt_{action}", type="primary" if action == "approve" else "secondary"):
            res = rex.dispatch("marketing", {"action": action, "campaign": camp,
                                             "reviewer": user.display_name, "note": note})
            if res.ok:
                ctx["campaign"] = res.output
                if ctx.get("camp_db_id"):
                    store.review_campaign(ctx["camp_db_id"], user.display_name, action == "approve", note,
                                          status=res.output.get("status"))
                st.rerun()
            st.error(res.message)
    if camp["approved"]:
        exp = rex.dispatch("marketing", {"action": "export", "campaign": camp})
        if exp.ok:
            st.download_button("⬇ Export approved content (Markdown)", exp.output["markdown"],
                               file_name="campaign.md", mime="text/markdown", key="mkt_export")
        st.caption("Publishing is manual: copy the approved content to each channel.")


# ------------------------------------------------------------------- tab: RFP
SAMPLE_RFPS = [
    {"title": "IT Training Program", "country": "Egypt", "organization": "MCIT",
     "deadline": "2026-12-01", "source_url": "https://example.com/eg1"},
    {"title": "Corporate Learning Services", "country": "KSA", "organization": "HRDF",
     "deadline": "2026-11-20", "source_url": "https://example.com/sa1"},
    {"title": "Training Tender (USA)", "country": "United States", "source_url": "https://example.com/us"},
    {"title": "Old Training RFP", "country": "Egypt", "deadline": "2025-09-01", "source_url": "https://example.com/old"},
    {"title": "IT Training Program", "country": "Egypt", "organization": "MCIT", "source_url": "https://example.com/eg1-copy"},
    {"title": "Road construction tender", "country": "Egypt", "source_url": "https://example.com/road"},
]


def render_rfp(user):
    rex = S["rex"]
    st.subheader("📑 " + t("tab_rfp"))
    st.write("Filters tenders: **Egypt / Saudi Arabia only**, education-related, not expired, no duplicates. "
             "Egypt → immediate review, Saudi → monitored pipeline.")
    left, right = st.columns([3, 1])
    with left:
        raw = st.text_area("Tenders to add manually (JSON list - optional, edit freely)",
                           value=json.dumps(SAMPLE_RFPS, indent=2), height=240, key="rfp_json")
    with right:
        today = st.date_input("Today's date", value=date.today(), key="rfp_today")
        discover = st.checkbox("Discover live online (Tavily)", value=True, key="rfp_discover")
        run = st.button("Run RFP agent", type="primary", key="rfp_run")

    if run:
        try:
            opportunities = json.loads(raw)
        except json.JSONDecodeError as error:
            st.error(f"Invalid JSON: {error}")
        else:
            csv_path = DOCS_DIR / user.username / "rfps.csv"
            res = rex.dispatch("rfp_research", {"today": today.isoformat(), "csv_path": str(csv_path),
                                                "discover": discover, "opportunities": opportunities})
            S["rfp_result"] = (res, csv_path.read_bytes() if csv_path.exists() else b"")
            S["ctx"]["rfp"] = res.output if res.ok else None
            S.pop("rfp_email_result", None)

    if "rfp_result" not in S:
        return
    res, csv_bytes = S["rfp_result"]
    if not res.ok:
        st.error(f"❌ {res.message}")
        return
    out = res.output
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Accepted", out["count"])
    c2.metric("Rejected", out["rejected_count"])
    c3.metric("Egypt flagged", len(out["flagged_for_immediate_review"]))
    c4.metric("New", out.get("new_count", 0))
    st.success(res.message)
    info = out.get("discovery", {})
    if info.get("ran"):
        st.info(f"Live discovery ran: {info.get('candidates', 0)} candidates from web search.")
        if info.get("errors"):
            st.warning(f"Search warnings: {info['errors']}")
    st.markdown("**🚩 Egypt - flagged for immediate review**")
    st.write(out["flagged_for_immediate_review"] or "None")
    st.markdown("**Saudi Arabia - monitored pipeline**")
    st.write(out["monitored_pipeline"] or "None")
    st.markdown("**Accepted opportunities**")
    st.dataframe([{k: o.get(k) for k in ("title", "country", "organization", "deadline", "days_left",
                                          "review_route", "status", "summary", "source_url")}
                  for o in out["opportunities"]])
    st.markdown("**Rejected (with reason)**")
    st.dataframe(out["rejected"])
    if csv_bytes:
        st.download_button("⬇ Download CSV", csv_bytes, "rfps.csv", "text/csv", key="rfp_csv")

    st.markdown("#### ✉️ E-mail digest")
    st.caption("Sends Egypt items first (immediate review), then Saudi Arabia. Preview first; nothing is sent "
               "until you confirm. Without SMTP settings in .env the e-mail is saved as an .eml file instead.")
    e1, e2 = st.columns([3, 1])
    recipients = e1.text_input("Recipients (comma separated)", key="rfp_to",
                               placeholder="team@academy.com, manager@academy.com")
    mail_lang = e2.selectbox("Language", ["en", "ar"], key="rfp_mail_lang")
    only_new = st.checkbox("Only new opportunities", key="rfp_only_new")
    base = {"rfp_result": out, "recipients": recipients, "language": mail_lang, "only_new": only_new,
            "attach_csv": out.get("csv_path")}
    p1, p2 = st.columns([1, 1])
    if p1.button("Preview e-mail", key="rfp_preview"):
        S["rfp_email_result"] = rex.dispatch("rfp_email", {**base, "send": False})
    confirm = p2.checkbox("I confirm sending this e-mail", key="rfp_confirm")
    if st.button("Send e-mail", type="primary", key="rfp_send", disabled=not confirm):
        res_mail = rex.dispatch("rfp_email", {**base, "send": True})
        S["rfp_email_result"] = res_mail
        if res_mail.output:
            store.log_email(user.id, "rfp_digest", ", ".join(res_mail.output.get("recipients", [])),
                            res_mail.output.get("subject", ""), res_mail.output.get("status", "failed"),
                            res_mail.message)
    mail = S.get("rfp_email_result")
    if mail:
        (st.success if mail.ok else st.error)(mail.message)
        if mail.output.get("html"):
            with st.expander("Preview", expanded=True):
                st.markdown(f"**Subject:** {mail.output['subject']}")
                st.markdown(mail.output["html"], unsafe_allow_html=True)


# ----------------------------------------------------------------- tab: profile
def pick_avatar(user_id: int, avatar_id: str):
    store.save_profile(user_id, avatar=avatar_id if avatar_id in avatars.AVATARS else "")


def render_avatar_picker(user):
    current = store.get_profile(user.id).get("avatar") or ""
    ar = lang() == "ar"
    st.markdown("#### " + ("صورتك الشخصية" if ar else "Your profile picture"))
    st.caption("اختر روبوت ليظهر بجانب اسمك." if ar else "Pick a chatbot avatar. It appears beside your name.")
    ids = avatars.avatar_ids()
    for start in range(0, len(ids), 4):
        cols = st.columns(4)
        for col, avatar_id in zip(cols, ids[start:start + 4]):
            with col:
                selected = avatar_id == current
                st.markdown(f'<div class="rex-pick{" sel" if selected else ""}">{avatars.svg(avatar_id)}</div>',
                            unsafe_allow_html=True)
                st.button(("✓ " if selected else "") + avatars.name(avatar_id, ar), key=f"av_{avatar_id}",
                          use_container_width=True, type="primary" if selected else "secondary",
                          on_click=pick_avatar, args=(user.id, avatar_id))
    if current:
        st.button("Use my initial instead" if not ar else "استخدم الحرف الأول بدلاً منها", key="av_clear",
                  on_click=pick_avatar, args=(user.id, ""))


def render_profile(user):
    st.subheader("👤 " + t("tab_profile"))
    render_avatar_picker(user)
    profile = store.get_profile(user.id)
    st.caption("Saved details are used to prefill your requests and, with your consent, let admissions contact you.")
    with st.form("profile_form"):
        c1, c2 = st.columns(2)
        phone = c1.text_input("Phone", profile["phone"])
        education = c2.text_input("Education level", profile["education"])
        experience = c1.text_input("Experience", profile["experience"])
        interests = c2.text_input("Interests / topics", profile["interests"])
        goals = st.text_area("Career goals", profile["goals"], height=80)
        pref = st.selectbox("Preferred language", ["en", "ar"], index=0 if profile["preferred_language"] != "ar" else 1,
                            format_func=lambda v: {"en": "English", "ar": "العربية"}[v])
        consent = st.checkbox("I agree that the admissions team may contact me about courses",
                              value=bool(profile["consent_followup"]))
        if st.form_submit_button(t("save"), type="primary"):
            store.save_profile(user.id, phone=phone, education=education, experience=experience,
                               interests=interests, goals=goals, preferred_language=pref, consent_followup=consent)
            st.success("Saved.")

    with st.expander("Change password"):
        with st.form("pw_form"):
            old = st.text_input(t("current_pw"), type="password")
            new = st.text_input(t("new_pw"), type="password")
            if st.form_submit_button(t("save")):
                try:
                    auth.change_password(user.id, old, new)
                    st.success("Password changed. Please sign in again.")
                    sign_out()
                except AuthError as error:
                    st.error(str(error))

    st.markdown("#### Conversation history")
    convs = store.conversations(user.id)
    if not convs:
        st.caption("No saved conversations yet.")
    for conv in convs:
        label = f"{conv['started']} · {conv['messages']} messages · {(conv['first_question'] or '')[:60]}"
        with st.expander(label):
            for m in store.messages(user.id, conv["conversation_id"]):
                st.markdown(f"**{'You' if m['role'] == 'user' else 'REX'}:** {m['content']}")
    if convs and st.button("Delete my chat history", key="del_hist"):
        store.delete_history(user.id)
        st.rerun()


# ------------------------------------------------------------------ tab: admin
def render_admin(user):
    rex = S["rex"]
    st.subheader("🛡️ " + t("tab_admin"))
    t_users, t_camp, t_cur, t_leads, t_mail, t_log, t_sys = st.tabs(
        ["Users", "Campaign approvals", "Curricula", "Leads", "E-mail log", "Activity", "System"])

    with t_users:
        users = auth.list_users()
        st.dataframe(users)
        names = {f"{u['username']} (#{u['id']})": u for u in users}
        pick = names[st.selectbox("Select a user", list(names), key="adm_user")]
        c1, c2, c3 = st.columns(3)
        new_role = c1.selectbox("Role", ["user", "admin"], index=0 if pick["role"] == "user" else 1, key="adm_role")
        if c1.button("Change role", key="adm_role_go"):
            try:
                auth.set_role(pick["id"], new_role)
                store.log(user.id, user.username, "role_changed", f"{pick['username']} -> {new_role}")
                st.rerun()
            except AuthError as error:
                st.error(str(error))
        temp = c2.text_input("Temporary password", type="password", key="adm_temp")
        if c2.button("Reset password", key="adm_reset"):
            try:
                auth.reset_password(pick["id"], temp)
                store.log(user.id, user.username, "password_reset", pick["username"])
                st.success("Done. The user must choose a new password at next sign-in.")
            except AuthError as error:
                st.error(str(error))
        if c3.button("Delete user", key="adm_delete"):
            try:
                if pick["id"] == user.id:
                    st.error("You cannot delete your own account.")
                else:
                    auth.delete_user(pick["id"])
                    store.log(user.id, user.username, "user_deleted", pick["username"])
                    st.rerun()
            except AuthError as error:
                st.error(str(error))

    with t_camp:
        queue = store.list_campaigns()
        if not queue:
            st.caption("No campaigns yet.")
        for row in queue:
            camp = row["payload"]
            head = f"#{row['id']} · {row['course']} · {STATUS_LABEL.get(row['status'], row['status'])} · {row['created_at']}"
            with st.expander(head):
                for channel, items in camp["content"].items():
                    st.markdown(f"**{channel.replace('_', ' ').title()}**")
                    for item in items[:2]:
                        st.text(item["text"][:600])
                if row["status"] == "pending_admin_approval":
                    note = st.text_input("Note", key=f"adm_note_{row['id']}")
                    a, b = st.columns(2)
                    if a.button("Approve", key=f"adm_ap_{row['id']}", type="primary"):
                        store.review_campaign(row["id"], user.display_name, True, note)
                        store.log(user.id, user.username, "campaign_approved", str(row["id"]))
                        st.rerun()
                    if b.button("Reject", key=f"adm_rej_{row['id']}"):
                        if note.strip():
                            store.review_campaign(row["id"], user.display_name, False, note)
                            store.log(user.id, user.username, "campaign_rejected", str(row["id"]))
                            st.rerun()
                        else:
                            st.error("Add a note explaining the rejection.")
                elif row["reviewed_by"]:
                    st.caption(f"Reviewed by {row['reviewed_by']} · {row['reviewed_at']} · {row['review_note'] or ''}")

    with t_cur:
        rows = store.list_curricula()
        st.dataframe([{"id": r["id"], "course": r["course"], "language": r["language"], "status": r["status"],
                       "version": r["version"], "approved_by": r["approved_by"], "created": r["created_at"]}
                      for r in rows])

    with t_leads:
        leads = store.list_leads()
        st.markdown("**Leads captured with consent (database)**")
        st.dataframe(leads)
        csv_file = ROOT / "data" / "leads.csv"
        if csv_file.exists():
            st.markdown("**Leads captured by the chatbot (data/leads.csv)**")
            st.download_button("⬇ Download leads.csv", csv_file.read_bytes(), "leads.csv", "text/csv", key="adm_leads_csv")

    with t_mail:
        st.dataframe(store.list_emails())

    with t_log:
        st.dataframe(store.activity())
        with st.expander("This session's agent trace"):
            st.dataframe(list(reversed(rex.trace)))

    with t_sys:
        import os
        from rex.agents.rfp_email import EmailConfig
        st.markdown(
            f"- LLM key: {'✅' if os.environ.get('LLM_API_KEY') or os.environ.get('GROQ_API_KEY') or os.environ.get('OPENAI_API_KEY') else '❌ not set'}\n"
            f"- Tavily (RFP discovery): {'✅' if os.environ.get('TAVILY_API_KEY') else '❌ not set'}\n"
            f"- SMTP (e-mail digest): {'✅' if EmailConfig.from_env().configured else '❌ not set - e-mails are saved as .eml'}\n"
            f"- Catalog: {len(COURSES)} courses")


# ---------------------------------------------------------------------- main
TABS = [  # (key, label key, icon, renderer, roles)
    ("dashboard", "tab_dashboard", "🏠", render_dashboard, {"user", "admin"}),
    ("assistant", "tab_assistant", "💬", render_chat, {"user", "admin"}),
    ("command", "tab_command", "🧭", render_command, {"user", "admin"}),
    ("curriculum", "tab_curriculum", "📚", render_curriculum, {"user", "admin"}),
    ("documents", "tab_documents", "📄", render_documents, {"user", "admin"}),
    ("marketing", "tab_marketing", "📣", render_marketing, {"admin"}),
    ("rfp", "tab_rfp", "📑", render_rfp, {"admin"}),
    ("profile", "tab_profile", "👤", render_profile, {"user", "admin"}),
    ("admin", "tab_admin", "🛡️", render_admin, {"admin"}),
]


def main():
    user = restore_session()
    if user is None:
        login_view()
        return
    if user.must_change_password:
        force_password_change(user)
        return
    ui_theme.inject(st, rtl=lang() == "ar")
    ensure_runtime(user)
    visible = [row for row in TABS if user.role in row[4]]
    sidebar(user, visible)
    current = next(row for row in visible if row[0] == S["nav"])
    if S.pop("greet_pending", False):
        from datetime import datetime
        pending = len(store.list_campaigns("pending_admin_approval")) if user.is_admin else 0
        ui_theme.robot_greeting(st, user.display_name, user.is_admin, lang() == "ar",
                                datetime.now().hour, pending)
    ui_theme.hero(st, t(current[1]), t("tagline"), f"{user.display_name} · "
                  f"{t('role_admin') if user.is_admin else t('role_user')}")
    try:
        current[3](user)
    except Exception as error:  # one broken section must not take the whole app down
        st.error(f"This section hit an error: {error}")

main()
