"""Sprint 2 demo: run each agent independently.  Usage: python apps/demo_sprint2.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rex.agents.orchestrator import Orchestrator  # noqa: E402

rex = Orchestrator()


def show(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


# 1. RFP agent: mixed list proves the strict filtering
show("1) RFP AGENT - country, expiry, duplicate, relevance filters")
r = rex.dispatch("rfp_research", {
    "today": "2026-10-26",
    "csv_path": "generated_docs/rfps.csv",
    "opportunities": [
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
    ],
})
print(r.message)
print("Immediate review (Egypt):", r.output["flagged_for_immediate_review"])
print("Monitored (Saudi):", r.output["monitored_pipeline"])
print("Rejected:", json.dumps(r.output["rejected"], indent=2))

# 2. Curriculum agent
show("2) CURRICULUM AGENT - generate + gap analysis")
cur = rex.dispatch("curriculum", {
    "action": "generate", "course": "Python for Data Analysis", "level": "Beginner",
    "duration_hours": 24,
    "learning_outcomes": ["Python basics", "Pandas", "Data visualization", "Capstone project"],
})
print(cur.message)
for m in cur.output["modules"]:
    print(f"  Module {m['module']}: {m['title']} ({m['duration_hours']}h)")
gap = rex.dispatch("curriculum", {
    "action": "gap_analysis",
    "required_topics": ["Python basics", "Pandas", "SQL"],
    "curriculum": [{"topics": [m["title"] for m in cur.output["modules"]]}],
})
print("Gap analysis:", json.dumps(gap.output, indent=2))

# 3. Document agent -> real PDF
show("3) DOCUMENT AGENT - PDF generation")
for doc_type in ("curriculum_report", "course_description", "gap_analysis"):
    d = rex.dispatch("document", {
        "document_type": doc_type, "title": f"REX AI - {doc_type}",
        "content": [f"Course: {cur.output['course']}", f"Level: {cur.output['level']}"]
                   + [m["title"] for m in cur.output["modules"]],
    })
    print(d.message)

# 4. Marketing agent
show("4) MARKETING AGENT - campaign (requires admin approval)")
mk = rex.dispatch("marketing", {
    "course": {"title": "Python for Data Analysis", "duration_hours": 24,
               "description": "Hands-on beginner course."},
    "target_audience": "fresh graduates", "channels": ["linkedin", "whatsapp"], "variations": 2,
})
print(mk.message, "| status:", mk.output["status"], "| published:", mk.output["published"])
print("LinkedIn v1:", mk.output["content"]["linkedin"][0]["text"])
