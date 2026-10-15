# Agent Descriptions & Workflows

All agents implement `rex.agents.base.Agent` and return `AgentResult` with `sources`.

## 1. REX Assistant — ✅ prototype
**Flow:** greet → ask interest → ask level → ask format/budget → recommend (≤3, with reasons) → answer questions from KB → ask consent → capture name/contact.
**Rules:** AR/EN; KB-only facts; no lead storage without consent.
**Tests:** `tests/test_assistant.py`.

## 2. RFP & Tender Research — Sprint 2
**Input:** country, categories, deadline range. **Output:** rows {title, organization, country, deadline, eligibility, category, link, published, documents, summary, qualification note, status}.
**Rules:** accept **Egypt** (flag immediately for review) and **Saudi Arabia** (monitored pipeline) only; drop all others; drop expired; detect duplicates (normalized title + org + deadline); store in Google Sheet/SQLite; alert on new relevant items.
**Tests:** non-EG/KSA rejected, expired rejected, duplicate merged, Egypt flagged.

## 3. Curriculum & Accreditation Alignment — Sprint 2
**Input:** course, audience, level, outcomes, hours, framework. **Output:** structured curriculum (objectives, prerequisites, outcomes, modules, hours, exercises, assessments, capstone) + gap report vs. standard + PDF; admin review/revise loop.
**Rule:** may *propose alignment*, never claim "officially accredited" without evidence.

## 4. Document Generation — Sprint 2 (≥3 doc types for MVP)
Suggested MVP types: Course Description, Curriculum PDF, Participant Guide. Template-based, AR/EN, editable before export, downloadable PDF.

## 5. Marketing — Sprint 2 (owner: Member 1)
**Input:** approved course data, audience, platforms, objective, offer/CTA. **Output:** captions, ad copy, LinkedIn post, email, WhatsApp message, headlines, CTAs (multiple variations) + simple strategy. **Rule:** manual approval before anything is sent/published.

## Connected workflow (acceptance criterion)
Curriculum approved → Marketing generates campaign from the same course record → Admin approves.
