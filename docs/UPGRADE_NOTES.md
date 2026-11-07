# REX AI - Upgrade notes (November 2026)

What was added or changed, how to run it, and what to know before the demo.

## 1. What is new

| Area | What changed | Where |
|---|---|---|
| **Marketing agent (finished)** | Instagram captions, Facebook posts, Facebook/Instagram **ad copy**, LinkedIn, e-mail (subject + body), WhatsApp; headlines, CTAs, hashtags; 1-5 variations per channel; English, Arabic or both; strategy (goal, key messages, 7-day calendar, KPIs, A/B test, budget note); optional AI copywriting with a **fact check** (invented numbers and accreditation claims are rejected); **approve / request changes / reject** workflow; export to Markdown. Nothing is ever published automatically. | `rex/agents/marketing.py` |
| **Orchestrator agent** | Understands a plain-language request (English or Arabic), picks the workflow, calls the agents in order and passes results between them. Workflows: `course_launch` (curriculum -> approval -> PDFs -> campaign -> admin review), `curriculum`, `documents`, `campaign`, `rfp` (+ e-mail). It stops and waits for a human before approving a curriculum or a campaign. Every step is traced. `dispatch()` still works exactly as before. | `rex/agents/orchestrator.py` |
| **Sign-in, roles, saved info** | Sign up / sign in, **user** and **admin** roles, salted PBKDF2 password hashes, lock-out after 5 wrong passwords, stay signed in on refresh, forced password change for the default admin. Saved per user: profile, chat history, leads (with consent), curricula, campaigns, PDFs; admin sees users, queue, leads, e-mail log, activity log. SQLite file `data/rex.db`. | `rex/core/` |
| **Arabic PDFs** | Letters are joined and ordered right-to-left, tables and bullets are mirrored, Arabic and English can be mixed, long lines wrap correctly. Language is chosen per document (`en`, `ar`, `auto`). A DRAFT stamp appears until the curriculum is approved. Bundled font: DejaVu Sans (drop `NotoNaskhArabic-Regular.ttf` into `rex/assets/fonts/` for a calligraphic look). | `rex/agents/document.py`, `rex/utils/arabic.py` |
| **Curriculum <-> Document interaction** | Document agent takes the curriculum directly (no JSON copy-paste). Review loop: generate -> request changes -> revise (free text such as "add module Data ethics (3 hours)" or structured changes) -> approve. Version history is kept. Arabic curricula. | `rex/agents/curriculum.py`, `document.py` |
| **RFP e-mail** | Digest of the RFP results, Egypt first (flagged for immediate review), then Saudi Arabia; plain text + HTML, English or Arabic; preview before sending; SMTP, or an `.eml` file in `generated_docs/outbox/` when SMTP is not configured. | `rex/agents/rfp_email.py` |
| **Interface** | New theme, sign-in page, sidebar with user, **Command Center** tab (talk to the orchestrator), review panels, admin panel, English/Arabic UI with right-to-left layout. | `apps/agents_ui.py`, `apps/ui_theme.py`, `.streamlit/config.toml` |
| **Bug fix** | Arabic keywords in `engine.py` were corrupted (double-encoded), so "reply in Arabic", "show all courses" and "prices" in Arabic were never recognised. Repaired. | `rex/assistant/engine.py` |

## 2. Backups

Before anything was modified, the original versions were copied to `backups/20261105-053023/` (same folder layout).
`python tools/backup.py` makes a new timestamped backup; `python tools/backup.py --restore backups/<folder>` restores one.
Files that were modified: `apps/agents_ui.py`, `rex/agents/{orchestrator,marketing,curriculum,document}.py`,
`rex/assistant/engine.py`, `requirements.txt`, `tests/{test_marketing,test_orchestrator}.py` (the last two are unchanged but backed up).

## 3. Run it

```bash
pip install -r requirements.txt
copy .env.example .env         # then fill in what you need (see below)
streamlit run apps/agents_ui.py
pytest
```

First sign-in: user `admin`, password = `REX_ADMIN_PASSWORD` from `.env`; if empty it is `Admin@12345` and the app forces a
new password immediately. Other people use **Sign up** (they get the `user` role); an admin can promote them in the Admin panel.

Who sees what (edit the `TABS` list in `apps/agents_ui.py`):

| | Assistant | Command Center | Curriculum | Documents | Profile | Marketing | RFP | Admin |
|---|---|---|---|---|---|---|---|---|
| user | yes | yes (curriculum, documents, questions) | yes | yes | yes | - | - | - |
| admin | yes | yes (everything) | yes + approves | yes | yes | yes + approves | yes + e-mail | yes |

Add to `.gitignore`: `.env`, `data/rex.db`, `generated_docs/`, `backups/` (or keep `backups/` if you want it in the repo).

## 3b. Environment variables (`.env.example` lists all)

`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `TAVILY_API_KEY`, `REX_ADMIN_USER`, `REX_ADMIN_PASSWORD`,
`SMTP_HOST/PORT/USER/PASSWORD/FROM/SECURITY`, `REX_RFP_RECIPIENTS`, `REX_DB_PATH`, `REX_ARABIC_FONT`.

## 4. Demo script (about 5 minutes)

1. Sign in as admin. Command Center: type **"Launch the Excel for Business Analysis course"** -> draft curriculum + draft PDFs, the orchestrator waits.
2. Click **Approve the curriculum and continue** -> final PDFs + a multi-channel campaign (this is the two-agent workflow).
3. Marketing tab: review, **Approve**. Export as Markdown.
4. Same request in Arabic: **"أطلق دورة أساسيات تعلم الآلة بالعربي"** -> open the Arabic PDF.
5. Curriculum tab: type "Add module Data ethics (3 hours)" -> new version -> Approve.
6. RFP tab: run, then preview and send the e-mail digest (saved as `.eml` without SMTP).
7. Sign in as a normal user: chat, profile, saved history; show that Marketing / RFP / Admin are hidden.

## 5. Honest limits

* The agents, database, PDFs and e-mail are covered by automated tests (`tests/`). The Streamlit screens were exercised with a
  stand-in `streamlit` module (every tab and the main buttons), **not** in a real browser: click through each tab once before the demo.
* Arabic shaping uses `arabic-reshaper` + `python-bidi` when installed; otherwise a built-in shaper (tested). Check one Arabic PDF visually.
* Live RFP discovery needs `TAVILY_API_KEY`; AI features need `LLM_API_KEY`. Without them the agents use templates and say so.
* SMTP sending was tested with a fake mail server function, not a real mailbox. The default behaviour without SMTP is an `.eml` file.
* `data/courses.json` is marked **SAMPLE DATA**; the marketing agent warns about this until you replace it with the approved catalog.
* Sign-in is built for a demo/prototype (SQLite, session token in the URL). For production put it behind HTTPS and a proper identity provider.
* `rex/api.py` (FastAPI) was not changed and has no authentication.
