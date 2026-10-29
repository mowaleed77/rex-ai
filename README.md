# REX AI — Multi-Agent System for Academy Operations

Graduation project (Oct 10 – Nov 5, 2026). REX AI automates core academy operations with five specialized agents behind one orchestrator.

| # | Agent | Status |
|---|-------|--------|
| 1 | **REX Assistant** – course recommendation chatbot (AR/EN, RAG + LLM) | ✅ Sprint 2 |
| 2 | **RFP & Tender Research** (Egypt + Saudi Arabia only) | ✅ Sprint 2 – country/expiry/duplicate/relevance filters, Egypt vs Saudi routing, CSV export |
| 3 | **Curriculum & Accreditation Alignment** | ✅ Sprint 2 – generation + gap analysis (LLM enrichment planned) |
| 4 | **Document Generation (PDF)** | ✅ Sprint 2 – 3 PDF document types |
| 5 | **Marketing** | ✅ Sprint 2 – multi-channel content, admin approval required |

> **Data note:** `data/*.json` is **sample data** for development. Replace it with the academy's approved catalog (same fields) — generate/edit via `data/build_kb.py` or edit the JSON directly.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python apps/cli_demo.py                    # chat in the terminal
streamlit run apps/streamlit_app.py        # chat UI
uvicorn rex.api:app --reload               # REST API  -> http://127.0.0.1:8000/docs
pytest                                     # run tests
```
API example: `POST /chat {"message": "I want to learn AI", "session_id": null}` → returns `reply` and `session_id` (send it back to continue).

## Project layout
```
rex/assistant/   REX Assistant: kb.py (data + retrieval), engine.py (conversation), text.py (AR/EN helpers)
rex/agents/      base.py (common Agent interface), orchestrator.py (router), stubs.py (Sprint 2 placeholders)
rex/api.py       FastAPI service
apps/            Streamlit UI and CLI demo
data/            Knowledge base (courses, instructors, faqs, admission)
docs/            Architecture, WBS, team responsibilities, agent specs, Git workflow
tests/           Test cases
```

## How the REX Assistant works (Sprint 1)
1. Detects Arabic/English per message.
2. Asks follow-ups (interest → level → format/budget) before recommending.
3. Recommends up to 3 courses with reasons, filtered by level, format and budget.
4. Answers price, duration, instructor, prerequisites, outcomes and career questions **only from the KB** — unknown topics get "no match", never invented courses.
5. Saves lead details to `data/leads.csv` **only after explicit consent** (git-ignored).

**Known limits / Sprint 2:** retrieval is keyword-based; swap in embeddings (Chroma/FAISS) and an LLM for wording; add Arabic descriptions to the KB.

## Docs
[Architecture](docs/ARCHITECTURE.md) · [WBS](docs/WBS.md) · [Team responsibilities](docs/TEAM.md) · [Agent specs](docs/AGENTS.md) · [Git workflow](docs/GIT_WORKFLOW.md) · [Sprint 1 checklist](docs/SPRINT1_CHECKLIST.md)

## RAG + LLM
See docs/RAG.md (set LLM_API_KEY in .env to enable the real LLM).
