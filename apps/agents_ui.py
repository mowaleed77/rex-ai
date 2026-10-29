"""UI for the four task agents.  Run:  streamlit run apps/agents_ui.py

One tab per agent. Every tab calls the Orchestrator, exactly like the code in
apps/demo_sprint2.py, so the UI shows the same behaviour as the tests.
"""
import csv
import io
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # lets Python find the `rex` package

import streamlit as st

from rex.agents.orchestrator import Orchestrator

st.set_page_config(page_title="REX AI | Agents", page_icon="🤖", layout="wide")


@st.cache_resource
def get_orchestrator() -> Orchestrator:
    return Orchestrator()


rex = get_orchestrator()

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
            "Tenders (JSON list – edit freely)",
            value=json.dumps(SAMPLE_RFPS, indent=2),
            height=320,
        )
    with right:
        today = st.date_input("Today's date", value=date.today())
        run_rfp = st.button("Run RFP agent", type="primary")

    if run_rfp:
        try:
            opportunities = json.loads(raw)
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")
        else:
            with tempfile.TemporaryDirectory() as tmp:
                csv_path = Path(tmp) / "rfps.csv"
                res = rex.dispatch("rfp_research", {
                    "opportunities": opportunities,
                    "today": today.isoformat(),
                    "csv_path": str(csv_path),
                })
                csv_bytes = csv_path.read_bytes() if csv_path.exists() else b""
            st.session_state["rfp_result"] = (res, csv_bytes)

    if "rfp_result" in st.session_state:
        res, csv_bytes = st.session_state["rfp_result"]
        if not res.ok:
            st.error(res.message)
        else:
            out = res.output
            c1, c2, c3 = st.columns(3)
            c1.metric("Accepted", out["count"])
            c2.metric("Rejected", out["rejected_count"])
            c3.metric("Egypt flagged", len(out["flagged_for_immediate_review"]))

            st.success(res.message)
            st.markdown("**🚩 Egypt – flagged for immediate review**")
            st.write(out["flagged_for_immediate_review"] or "None")
            st.markdown("**👀 Saudi Arabia – monitored pipeline**")
            st.write(out["monitored_pipeline"] or "None")

            st.markdown("**Accepted opportunities**")
            st.dataframe(
                [{k: o[k] for k in ("title", "country", "organization", "deadline",
                                    "days_left", "review_route", "status", "summary")}
                 for o in out["opportunities"]],
                
            )
            st.markdown("**Rejected (with reason)**")
            st.dataframe(out["rejected"])
            if csv_bytes:
                st.download_button("⬇ Download CSV", csv_bytes, "rfps.csv", "text/csv")

# --------------------------------------------------------------------- Curriculum
with tab_cur:
    st.subheader("Curriculum & Accreditation Alignment Agent")
    st.write(
        "Builds a proposed curriculum from learning outcomes, then runs a gap analysis "
        "against required topics. It never claims official accreditation."
    )
    c_left, c_right = st.columns(2)
    with c_left:
        course = st.text_input("Course title", "Python for Data Analysis")
        level = st.selectbox("Level", ["Beginner", "Intermediate", "Advanced"])
        hours = st.number_input("Total training hours", min_value=1.0, value=24.0, step=1.0)
    with c_right:
        outcomes_raw = st.text_area(
            "Learning outcomes (one per line)",
            "Python basics\nPandas\nData visualization\nCapstone project",
            height=150,
        )
    if st.button("Generate curriculum", type="primary"):
        outcomes = [line.strip() for line in outcomes_raw.splitlines() if line.strip()]
        st.session_state["cur_result"] = rex.dispatch("curriculum", {
            "action": "generate", "course": course, "level": level,
            "duration_hours": hours, "learning_outcomes": outcomes,
        })
        st.session_state.pop("gap_result", None)

    cur = st.session_state.get("cur_result")
    if cur:
        if not cur.ok:
            st.error(cur.message)
        else:
            st.success(cur.message)
            st.caption(cur.output["status"])
            st.dataframe(cur.output["modules"])

            st.markdown("#### Gap analysis")
            required_raw = st.text_area(
                "Required topics (one per line)", "Python basics\nPandas\nSQL", height=100
            )
            if st.button("Run gap analysis"):
                required = [line.strip() for line in required_raw.splitlines() if line.strip()]
                st.session_state["gap_result"] = rex.dispatch("curriculum", {
                    "action": "gap_analysis",
                    "required_topics": required,
                    "curriculum": [{"topics": [m["title"] for m in cur.output["modules"]]}],
                })
            gap = st.session_state.get("gap_result")
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

# ---------------------------------------------------------------------- Documents
with tab_doc:
    st.subheader("Document Generation Agent")
    st.write("Creates a downloadable PDF from the content you provide.")

    default_lines = ""
    cur = st.session_state.get("cur_result")
    if cur and cur.ok:
        default_lines = "\n".join(
            [f"Course: {cur.output['course']}", f"Level: {cur.output['level']}"]
            + [m["title"] for m in cur.output["modules"]]
        )
        st.info("Content pre-filled from the curriculum you generated in the previous tab.")

    d_left, d_right = st.columns(2)
    with d_left:
        doc_type = st.selectbox(
            "Document type", ["curriculum_report", "course_description", "gap_analysis"]
        )
        doc_title = st.text_input("Title", "REX AI - Course Document")
    with d_right:
        doc_content = st.text_area(
            "Content (one paragraph per line)",
            default_lines or "Course: Python for Data Analysis\nLevel: Beginner",
            height=150,
        )
    if st.button("Generate PDF", type="primary"):
        lines = [line.strip() for line in doc_content.splitlines() if line.strip()]
        with tempfile.TemporaryDirectory() as tmp:
            res = rex.dispatch("document", {
                "document_type": doc_type, "title": doc_title,
                "content": lines, "output_dir": tmp,
            })
            pdf_bytes = Path(res.output["file_path"]).read_bytes() if res.ok else b""
        st.session_state["doc_result"] = (res, pdf_bytes, doc_type)

    if "doc_result" in st.session_state:
        res, pdf_bytes, dtype = st.session_state["doc_result"]
        if not res.ok:
            st.error(res.message)
        else:
            st.success("PDF created successfully.")
            st.download_button("⬇ Download PDF", pdf_bytes, f"{dtype}.pdf", "application/pdf")

# ---------------------------------------------------------------------- Marketing
with tab_mkt:
    st.subheader("Marketing Agent")
    st.write("Generates multi-channel campaign content. Nothing is published without admin approval.")
    m_left, m_right = st.columns(2)
    with m_left:
        m_title = st.text_input("Course title", "Python for Data Analysis", key="m_title")
        m_desc = st.text_area("Short description", "Hands-on beginner course.", height=80)
        m_hours = st.number_input("Duration (hours)", min_value=1, value=24, step=1)
        m_price = st.text_input("Price (optional)", "")
        m_promo = st.text_input("Offer / promotion (optional)", "")
    with m_right:
        m_audience = st.text_input("Target audience", "fresh graduates")
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
        st.session_state["mkt_result"] = rex.dispatch("marketing", {
            "course": course_data, "target_audience": m_audience,
            "channels": m_channels, "variations": m_vars,
        })
        st.session_state["mkt_approved"] = False

    mkt = st.session_state.get("mkt_result")
    if mkt:
        if not mkt.ok:
            st.error(mkt.message)
        else:
            out = mkt.output
            approved = st.session_state.get("mkt_approved", False)
            s1, s2 = st.columns(2)
            s1.metric("Status", "approved (demo)" if approved else out["status"])
            s2.metric("Published", "False")
            st.markdown("**Campaign strategy**")
            st.json(out["campaign_strategy"])

            for channel, items in out["content"].items():
                with st.expander(f"{channel.title()} – {len(items)} variation(s)", expanded=True):
                    for item in items:
                        st.markdown(f"**Variation {item['variation']}** · _{item['headline']}_")
                        st.text(item["text"])
                        st.caption(f"CTA: {item['call_to_action']}")

            if st.button("✅ Approve campaign (admin step, demo only)", disabled=approved):
                st.session_state["mkt_approved"] = True
                st.rerun()
            if approved:
                st.success("Approved in this demo session. Publishing is not connected yet (Sprint 3).")
