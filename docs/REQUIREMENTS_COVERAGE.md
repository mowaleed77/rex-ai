# REX AI - requirements coverage (brief vs. code)

| Brief requirement (MVP checklist) | Where | Test |
|---|---|---|
| REX Assistant answers from real course data, recommends courses (EN/AR) | rex/assistant/engine.py, rag.py | tests/test_assistant.py, test_engine_arabic.py |
| RFP Agent: discovery/processing, **Egypt/Saudi only** filter, expiry, duplicates, summary, review route | rex/agents/rfp.py | tests/test_rfp*.py |
| RFP e-mail to chosen recipients (preview, confirmation, SMTP or saved .eml) | rex/agents/rfp_email.py, UI "RFP Research" | tests/test_rfp_email.py |
| Curriculum Agent: structured curriculum, review loop, versions, gap analysis, never claims accreditation | rex/agents/curriculum.py | tests/test_curriculum*.py |
| Document Agent: downloadable PDFs, 3 types (curriculum_report, course_description, gap_analysis), English + Arabic | rex/agents/document.py, rex/utils/arabic.py | tests/test_arabic_pdf.py |
| Marketing Agent: campaign content from course details, admin approval, never auto-published | rex/agents/marketing.py | tests/test_marketing*.py |
| >= 1 workflow across 2+ agents | Orchestrator `course_launch` (curriculum -> document -> marketing) | tests/test_orchestrator*.py |
| Every major feature has a test | tests/ | `pytest` |
| Demonstrable | `streamlit run apps/agents_ui.py` | - |

Not covered by code (team/process items from the brief): GitHub contributions per student, README/install guide
polish, architecture diagram, sample-document folder, contribution summary, final presentation.
Known limits: Document Agent implements 3 of the 10 listed document types (the brief requires at least 3);
RagAssistant skips the lead-consent flow when an LLM is configured; the REST API (rex/api.py) has no auth.
