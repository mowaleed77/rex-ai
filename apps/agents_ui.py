"""UI for the four task agents.  Run:  streamlit run apps/agents_ui.py

One tab per agent. Every tab calls the Orchestrator, exactly like the code in
apps/demo_sprint2.py, so the UI shows the same behaviour as the tests.
"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # lets Python find `rex`

import streamlit as st

from rex.agents.orchestrator import Orchestrator

st.set_page_config(page_title="REX AI | Agents", page_icon="🤖", layout="wide")


@st.cache_resource
def get_orchestrator() -> Orchestrator:
    return Orchestrator()


rex = get_orchestrator()


@st.cache_data
def load_catalog() -> dict:
    """Academy course catalog (data/courses.json), keyed by English title."""
    path = Path(__file__).resolve().parents[1] / "data" / "courses.json"
    try:
        courses = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {c["title_en"]: c for c in courses if c.get("title_en")}


CATALOG = load_catalog()
CUSTOM = "✏️ Custom course…"
LEVELS = ["Beginner", "Intermediate", "Advanced"]

SAMPLE_RFPS = [
    {"title": "IT Training Program", "country": "Egypt", "organization": "MCIT",
     "deadline": "2026-12-01", "source_url": "https://example.com/eg1"},
    {"title": "Corporate Learning Services", "country": "KSA", "organization": "HRDF",
     "deadline": "2026-11-20", "source_url": "https://example.com/sa1"},
    {"title": "Training Tender (USA)", "country": "United States",
     "source_url": "https://example.com/us"},
    {"title": "Old Training RFP", "country": "Egypt", "deadline": "2026-09-01",
     "source_url": "https://example.com/old"},
    {"title": "IT Training Program", "country": "Egypt", "organization": "MCIT",
     "source_url": "https://example.com/eg1-copy"},
    {"title": "Road construction tender", "country": "Egypt",
     "source_url": "https://example.com/road"},
]

# default per-type content for the Document tab
DOC_DEFAULTS = {
    "curriculum_report": {
        "overview": "12-week program covering the fundamentals of the subject.",
        "objectives": [
            "Explain core concepts",
            "Build and evaluate a small project end-to-end",
        ],
        "modules": [
            {"title": "Python basics", "topics": ["Variables", "Loops"], "hours": 8},
            {"title": "Pandas", "topics": ["DataFrames", "GroupBy"], "hours": 10},
            {"title": "Visualization", "topics": ["Matplotlib", "Seaborn"], "hours": 6},
        ],
        "assessments": ["Weekly quizzes", "Midterm project"],
        "capstone": "Build and deploy a small data pipeline.",
    },
    "course_description": {
        "pitch": "Start your data career in 12 weeks — no prior experience required.",
        "audience": "Career switchers",
        "level": "Beginner",
        "duration": "12 weeks",
        "format": "Online, part-time",
        "fee": "EGP 8,000",
        "prerequisites": "Basic computer skills",
        "outcomes": [
            "Read and clean data with Pandas",
            "Visualize results and communicate insights",
        ],
        "careers": ["Junior Data Analyst", "BI Assistant"],
    },
    "gap_analysis": {
        "summary": "3 of 8 competencies partially covered; 1 missing.",
        "gaps": [
            {"requirement": "Data ethics", "status": "Missing", "severity": "High",
             "recommendation": "Add a 3-hour module on data ethics & bias."},
            {"requirement": "Model deployment", "status": "Partial", "severity": "Medium",
             "recommendation": "Add a deployment lab using FastAPI."},
        ],
        "recommended_actions": [
            "Revise module 4 to include ethics",
            "Add a deployment lab",
            "Re-run gap analysis after revisions",
        ],
    },
}

st.title("🤖 REX AI – Task Agents")
st.caption(
    "Each tab sends a task to one agent through the Orchestrator and shows the result. "
    "The chatbot has its own app: `streamlit run apps/streamlit_app.py`."
)

tab_rfp, tab_cur, tab_doc, tab_mkt = st.tabs(
    ["📑 RFP Research", "📚 Curriculum", "📄 Documents (PDF)", "📣 Marketing"]
)

# --------------------------------------------------------------------------- RFP
with tab_rfp:
    st.subheader("RFP & Tender Research Agent")
    st.write(
        "Filters tenders: **Egypt / Saudi Arabia only**, education-related, not expired, "
        "no duplicates. Egypt → immediate review, Saudi → monitored pipeline."
    )
    left, right = st.columns([3, 1])
    with left:
        raw = st.text_area(
            "Tenders (JSON list – edit freely or leave for live search)",
            value=json.dumps(SAMPLE_RFPS, indent=2),
            height=320,
        )
    with right:
        today = st.date_input("Today's date", value=date.today())
        discover_live = st.checkbox("Discover live online (Tavily)", value=True)
        run_rfp = st.button("Run RFP agent", type="primary")

    if run_rfp:
        try:
            opportunities = json.loads(raw)
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")
        else:
            with tempfile.TemporaryDirectory() as tmp:
                csv_path = Path(tmp) / "rfps.csv"
                
                # Build the task payload dynamically
                task_payload = {
                    "today": today.isoformat(),
                    "csv_path": str(csv_path),
                    "discover": discover_live,
                }
                # If discovery is checked, we can also pass the text box items as additional input, 
                # or clear them if you want purely live web results.
                if discover_live:
                    task_payload["opportunities"] = opportunities  # combines live web + any custom JSON you added
                else:
                    task_payload["opportunities"] = opportunities

                res = rex.dispatch("rfp_research", task_payload)
                csv_bytes = csv_path.read_bytes() if csv_path.exists() else b""
            st.session_state["rfp_result"] = (res, csv_bytes)

    if "rfp_result" in st.session_state:
        res, csv_bytes = st.session_state["rfp_result"]
        if not res.ok:
            st.error(f"❌ {res.message}")
        else:
            out = res.output
            c1, c2, c3 = st.columns(3)
            c1.metric("Accepted", out["count"])
            c2.metric("Rejected", out["rejected_count"])
            c3.metric("Egypt flagged", len(out["flagged_for_immediate_review"]))

            st.success(res.message)
            
            # Show live discovery status if ran
            discovery_info = out.get("discovery", {})
            if discovery_info.get("ran"):
                st.info(f" Live Discovery Ran: Found {discovery_info.get('candidates', 0)} candidates from web search.")
                if discovery_info.get("errors"):
                    st.warning(f"Search warnings/errors: {discovery_info['errors']}")

            st.markdown("**🚩 Egypt – flagged for immediate review**")
            st.write(out["flagged_for_immediate_review"] or "None")
            st.markdown("** Saudi Arabia – monitored pipeline**")
            st.write(out["monitored_pipeline"] or "None")

            st.markdown("**Accepted opportunities**")
            st.dataframe(
                [
                    {k: o[k] for k in (
                        "title", "country", "organization", "deadline",
                        "days_left", "review_route", "status", "summary", "source_url"
                    )}
                    for o in out["opportunities"]
                ]
            )
            st.markdown("**Rejected (with reason)**")
            st.dataframe(out["rejected"])
            if csv_bytes:
                st.download_button("⬇ Download CSV", csv_bytes, "rfps.csv", "text/csv")
            else:
                st.warning("CSV was not produced by the agent.")

# --------------------------------------------------------------------- Curriculum
with tab_cur:
    st.subheader("Curriculum & Accreditation Alignment Agent")
    st.write(
        "Builds a proposed curriculum from learning outcomes, then runs a gap analysis "
        "against required topics. It never claims official accreditation."
    )
    def load_course():
        """Fill level / hours / outcomes from the catalog when a course is picked."""
        c = CATALOG.get(st.session_state["cur_choice"])
        if c:
            st.session_state["cur_level"] = c.get("level", "Beginner")
            st.session_state["cur_hours"] = float(c.get("duration_hours", 24))
            st.session_state["cur_outcomes"] = "\n".join(c.get("learning_outcomes", []))
        st.session_state.pop("cur_result", None)
        st.session_state.pop("gap_result", None)

    options = list(CATALOG) + [CUSTOM]
    if "cur_choice" not in st.session_state:
        st.session_state["cur_choice"] = options[0]
        load_course()
    st.session_state.setdefault("cur_level", "Beginner")
    st.session_state.setdefault("cur_hours", 24.0)
    st.session_state.setdefault("cur_outcomes", "")

    c_left, c_right = st.columns(2)
    with c_left:
        choice = st.selectbox(
            "Course (from the academy catalog)", options,
            key="cur_choice", on_change=load_course,
        )
        if choice == CUSTOM:
            course = st.text_input("Custom course title", "", key="cur_custom_title")
        else:
            course = choice
        level = st.selectbox("Level", LEVELS, key="cur_level")
        hours = st.number_input(
            "Total training hours", min_value=1.0, step=1.0, key="cur_hours"
        )
    with c_right:
        outcomes_raw = st.text_area(
            "Learning outcomes (one per line) — loaded from the catalog, edit freely",
            height=190, key="cur_outcomes",
        )
    use_llm = st.checkbox(
        "Use AI generation (needs LLM_API_KEY in .env; otherwise a level-based template is used)",
        value=True, key="cur_use_llm",
    )
    if st.button("Generate curriculum", type="primary"):
        outcomes = [line.strip() for line in outcomes_raw.splitlines() if line.strip()]
        st.session_state["cur_result"] = rex.dispatch("curriculum", {
            "action": "generate", "course": course, "level": level,
            "duration_hours": hours, "learning_outcomes": outcomes,
            "use_llm": use_llm,
        })
        st.session_state.pop("gap_result", None)

    cur = st.session_state.get("cur_result")
    if cur:
        if not cur.ok:
            st.error(f"❌ {cur.message}")
        else:
            st.success(cur.message)
            st.caption(f"{cur.output['status']} · generated by: {cur.output['generated_by']}")
            st.markdown(f"**Prerequisites:** {cur.output['prerequisites']}")
            st.markdown("**Objectives**")
            st.write(cur.output["objectives"])
            st.dataframe(cur.output["modules"])
            st.markdown(f"**Assessments:** {', '.join(cur.output['assessments'])}")
            st.markdown(f"**Capstone:** {cur.output['capstone']}")

            st.markdown("#### Gap analysis")
            st.caption(
                "Checks the proposed curriculum above against a list of **required topics** "
                "(what an accreditation framework, an employer or the academy standard expects). "
                "It shows which required topics are covered, which are missing, and the coverage %. "
                "Paste your own required topics below — it is only an alignment check, never an "
                "official accreditation."
            )
            required_raw = st.text_area(
                "Required topics (one per line)",
                "\n".join(CATALOG.get(choice, {}).get("learning_outcomes", [])) or "SQL",
                height=100,
                key=f"required_{choice}",
            )
            if st.button("Run gap analysis"):
                required = [line.strip() for line in required_raw.splitlines() if line.strip()]
                # Prefer real topics when modules provide them; fall back to title
                curriculum = [
                    {"topics": m.get("topics") or [m["title"]]}
                    for m in cur.output["modules"]
                ]
                st.session_state["gap_result"] = rex.dispatch("curriculum", {
                    "action": "gap_analysis",
                    "required_topics": required,
                    "curriculum": curriculum,
                })
            gap = st.session_state.get("gap_result")
            if gap:
                if not gap.ok:
                    st.error(f"❌ {gap.message}")
                else:
                    g = gap.output
                    g1, g2 = st.columns(2)
                    g1.metric("Coverage", f"{g['coverage_percentage']}%")
                    g2.metric("Accreditation", g["accreditation_status"])
                    st.write("✅ Covered:", g["covered_topics"] or "None")
                    st.write("❌ Missing:", g["missing_topics"] or "None")

# ---------------------------------------------------------------------- Documents
with tab_doc:
    st.subheader("Document Generation Agent")
    st.write(
        "Creates a downloadable, type-specific PDF. "
        "Each document type has its own schema and layout."
    )
    st.caption(
        "• **curriculum_report** → overview, objectives, modules table, "
        "assessments, capstone  \n"
        "• **course_description** → pitch, key-facts table, outcomes, careers  \n"
        "• **gap_analysis** → summary, gaps table, recommended actions"
    )

    doc_type = st.selectbox(
        "Document type",
        ["curriculum_report", "course_description", "gap_analysis"],
    )
    # Everything below follows the curriculum generated in the previous tab.
    cur = st.session_state.get("cur_result")
    cur_ok = bool(cur and cur.ok)
    if cur_ok:
        out = cur.output
        base_course = out["course"]
        cat = CATALOG.get(base_course, {})
        base_audience = cat.get("target_audience") or "Beginners"
        # widget keys change whenever the curriculum changes, so Streamlit resets the fields
        tail = f"{base_course}|{out['level']}|{out['duration_hours']}|{out.get('generated_by')}"
    else:
        base_course, cat, base_audience, tail = "AI Fundamentals", {}, "Beginners", "default"

    titles = {
        "curriculum_report": f"{base_course} — Curriculum",
        "course_description": base_course,
        "gap_analysis": f"{base_course} — Accreditation Gap Report",
    }
    doc_title = st.text_input("Title", titles[doc_type], key=f"title_{doc_type}|{tail}")

    meta_left, meta_right = st.columns(2)
    with meta_left:
        meta_course = st.text_input("Metadata · Course", base_course, key=f"mcourse|{tail}")
    with meta_right:
        meta_audience = st.text_input("Metadata · Audience", base_audience, key=f"maud|{tail}")

    default_content = DOC_DEFAULTS[doc_type]
    if cur_ok:
        st.info("Prefilled from the curriculum generated in the previous tab (edit freely).")
        if doc_type == "curriculum_report":
            default_content = {
                "overview": f"{out['course']} — {out['level']} level, {out['duration_hours']:g} hours.",
                "objectives": out.get("objectives") or [m["title"] for m in out["modules"]],
                "modules": [
                    {
                        "title": m["title"],
                        "topics": m.get("topics") or [m["title"]],
                        "hours": m.get("duration_hours", m.get("hours", 0)),
                    }
                    for m in out["modules"]
                ],
                "assessments": out.get("assessments", []),
                "capstone": out.get("capstone", ""),
            }
        elif doc_type == "course_description":
            default_content = {
                "pitch": cat.get("description") or f"Learn {out['course']} in {out['duration_hours']:g} hours.",
                "audience": base_audience,
                "level": out["level"],
                "duration": f"{out['duration_hours']:g} hours",
                "format": ", ".join(cat.get("formats", [])) or "To be confirmed",
                "fee": f"EGP {cat['price_egp']:,}" if cat.get("price_egp") else "To be confirmed",
                "prerequisites": out.get("prerequisites") or "To be confirmed",
                "outcomes": [m["title"] for m in out["modules"]],
                "careers": cat.get("career_opportunities", []),
            }
        else:  # gap_analysis
            default_content = {
                "summary": f"Draft gap analysis seeded from the generated curriculum for {out['course']}.",
                "gaps": [
                    {"requirement": m["title"], "status": "Covered",
                     "severity": "Low", "recommendation": "—"}
                    for m in out["modules"]
                ],
                "recommended_actions": ["Review with instructor before approval"],
            }

    raw = st.text_area(
        "Content JSON (schema depends on document_type)",
        value=json.dumps(default_content, indent=2, ensure_ascii=False),
        height=300,
        key=f"content_{doc_type}|{tail}",
    )

    if st.button("Generate PDF", type="primary"):
        try:
            content = json.loads(raw)
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")
        else:
            if not isinstance(content, dict) or not content:
                st.error("Content must be a non-empty JSON object.")
            else:
                with tempfile.TemporaryDirectory() as tmp:
                    res = rex.dispatch("document", {
                        "document_type": doc_type,
                        "title": doc_title,
                        "metadata": {
                            "Course": meta_course,
                            "Audience": meta_audience,
                            "Date": str(date.today()),
                        },
                        "content": content,
                        "output_dir": tmp,
                    })
                    pdf_bytes = b""
                    if res.ok and res.output and "file_path" in res.output:
                        p = Path(res.output["file_path"])
                        if p.exists():
                            pdf_bytes = p.read_bytes()
                st.session_state["doc_result"] = (res, pdf_bytes, doc_type)

    if "doc_result" in st.session_state:
        res, pdf_bytes, dtype = st.session_state["doc_result"]
        if not res.ok:
            st.error(f"❌ {res.message}")
        elif not pdf_bytes:
            st.error(
                "Agent reported success but produced no file — "
                "check the agent's output_dir and file_path."
            )
        else:
            st.success(f"✅ PDF created ({len(pdf_bytes):,} bytes) — type: {dtype}")
            st.download_button(
                "⬇ Download PDF",
                pdf_bytes,
                f"{dtype}.pdf",
                "application/pdf",
            )

# ---------------------------------------------------------------------- Marketing
with tab_mkt:
    st.subheader("Marketing Agent")
    st.write("Generates multi-channel campaign content. Nothing is published without admin approval.")
    GENERIC_AUDIENCES = [
        "Fresh graduates", "Career switchers", "Working professionals",
        "University students", "Corporate teams / HR managers",
    ]
    CUSTOM_AUD = "✏️ Custom audience…"
    mkt_options = list(CATALOG) + [CUSTOM]

    def load_mkt_course(cur_out=None):
        """Fill description / hours / price / offer / audience from the catalog (or curriculum)."""
        name = st.session_state["mkt_choice"]
        c = CATALOG.get(name, {})
        st.session_state["m_desc"] = c.get("description", "")
        hours_ = (cur_out or {}).get("duration_hours") or c.get("duration_hours") or 24
        st.session_state["m_hours"] = max(1, int(round(float(hours_))))
        st.session_state["m_price"] = f"EGP {c['price_egp']:,}" if c.get("price_egp") else ""
        st.session_state["m_promo"] = c.get("promotion", "")
        st.session_state["mkt_aud_choice"] = c.get("target_audience") or GENERIC_AUDIENCES[0]
        st.session_state.pop("mkt_result", None)
        st.session_state.pop("mkt_approved", None)

    # Follow the curriculum tab: when a new curriculum is generated, promote that course.
    cur_m = st.session_state.get("cur_result")
    cur_m_out = cur_m.output if cur_m and cur_m.ok else None
    cur_key = (cur_m_out["course"], cur_m_out["level"], cur_m_out["duration_hours"]) if cur_m_out else None
    if "mkt_choice" not in st.session_state:
        st.session_state["mkt_choice"] = mkt_options[0]
        load_mkt_course()
    if cur_key and st.session_state.get("mkt_seen_cur") != cur_key:
        st.session_state["mkt_seen_cur"] = cur_key
        in_catalog = cur_m_out["course"] in CATALOG
        st.session_state["mkt_choice"] = cur_m_out["course"] if in_catalog else CUSTOM
        st.session_state["mkt_custom_title"] = "" if in_catalog else cur_m_out["course"]
        load_mkt_course(cur_m_out)
    if cur_key:
        st.info("Course details are taken from the curriculum generated in the Curriculum tab "
                "(you can pick another course below).")

    m_left, m_right = st.columns(2)
    with m_left:
        m_choice = st.selectbox(
            "Course (from the academy catalog)", mkt_options,
            key="mkt_choice", on_change=load_mkt_course,
        )
        if m_choice == CUSTOM:
            m_title = st.text_input("Custom course title", key="mkt_custom_title")
        else:
            m_title = m_choice
        m_desc = st.text_area("Short description", height=80, key="m_desc")
        m_hours = st.number_input("Duration (hours)", min_value=1, step=1, key="m_hours")
        m_price = st.text_input("Price (optional)", key="m_price")
        m_promo = st.text_input("Offer / promotion (optional)", key="m_promo")
    with m_right:
        cat_aud = CATALOG.get(m_choice, {}).get("target_audience")
        aud_options = ([cat_aud] if cat_aud else []) + GENERIC_AUDIENCES + [CUSTOM_AUD]
        if st.session_state.get("mkt_aud_choice") not in aud_options:
            st.session_state["mkt_aud_choice"] = aud_options[0]
        aud_choice = st.selectbox("Target audience", aud_options, key="mkt_aud_choice")
        if aud_choice == CUSTOM_AUD:
            m_audience = st.text_input("Custom audience", key="mkt_aud_custom")
        else:
            m_audience = aud_choice
        m_channels = st.multiselect(
            "Channels",
            ["instagram", "facebook", "linkedin", "email", "whatsapp"],
            default=["linkedin", "whatsapp"],
        )
        m_vars = st.slider("Variations per channel", 1, 5, 2)

    if st.button("Generate campaign", type="primary"):
        course_data = {"title": m_title, "description": m_desc, "duration_hours": m_hours}
        if m_price:
            course_data["price"] = m_price
        if m_promo:
            course_data["promotion"] = m_promo
        mkt_task = {"course": course_data, "channels": m_channels, "variations": m_vars}
        if m_audience.strip():
            mkt_task["target_audience"] = m_audience.strip()
        st.session_state["mkt_result"] = rex.dispatch("marketing", mkt_task)
        st.session_state["mkt_approved"] = False

    mkt = st.session_state.get("mkt_result")
    if mkt:
        if not mkt.ok:
            st.error(f"❌ {mkt.message}")
        else:
            out = mkt.output
            approved = st.session_state.get("mkt_approved", False)
            s1, s2 = st.columns(2)
            s1.metric("Status", "approved (demo)" if approved else out["status"])
            s2.metric("Published", "False")
            st.markdown("**Campaign strategy**")
            st.json(out["campaign_strategy"])

            for channel, items in out["content"].items():
                with st.expander(
                    f"{channel.title()} – {len(items)} variation(s)", expanded=True
                ):
                    for item in items:
                        st.markdown(
                            f"**Variation {item['variation']}** · _{item['headline']}_"
                        )
                        st.text(item["text"])
                        st.caption(f"CTA: {item['call_to_action']}")

            if st.button("✅ Approve campaign (admin step, demo only)", disabled=approved):
                st.session_state["mkt_approved"] = True
                st.rerun()
            if approved:
                st.success(
                    "Approved in this demo session. "
                    "Publishing is not connected yet (Sprint 3)."
                )