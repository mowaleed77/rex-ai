# Team Responsibilities (2 members)

Every student owns agents/modules **and** appears in commits, branches and PRs under their own account.

| | Member 1 – MoWaleed77 | Member 2 – NourWalid111 |
|---|---|---|
| **Agents owned** | Agent 1 REX Assistant · Agent 2 RFP Research · Agent 5 Marketing | Agent 3 Curriculum & Accreditation · Agent 4 Document Generation (PDF) |
| **Shared components** | Knowledge base / RAG, orchestrator (`rex/agents/orchestrator.py`), FastAPI | Streamlit UI, PDF templates, reference documents |
| **Tests** | `tests/test_assistant.py`, `test_rfp.py`, `test_marketing.py` | `tests/test_curriculum.py`, `test_documents.py` |
| **Reviews PRs of** | Member 2 | Member 1 |
| **Docs** | README, agent specs for own agents | Architecture diagram, WBS, agent specs for own agents |

**Why this split:** agents 3→4 form one chain (curriculum feeds documents) and 3→5 is the required connected workflow (*Curriculum approved → Marketing campaign*), so the two members must integrate through the shared `AgentResult` interface — which also gives both of you visible PRs and reviews.

## Sprint ownership
| Sprint | Member 1 | Member 2 |
|---|---|---|
| 1 (Oct 10–18) | Real KB data, REX Assistant demo, GitHub repo + instructor access | Architecture diagram, WBS, README polish, Streamlit UI shell, collect reference docs |
| 2 (Oct 19–27) | Finish REX Assistant; RFP agent (EG/KSA filter); basic Marketing agent | Curriculum generator + alignment report; PDF templates (≥3 doc types) |
| 3 (Oct 28–Nov 5) | Orchestrator workflows, error handling, marketing approval | Final UI, PDF testing, presentation + demo |

## Rules
- Branch per task: `feature/<agent>-<task>`; PR into `develop`; the *other* member reviews before merge.
- Commit messages describe the change (`Add Egypt/KSA country filter to RFP pipeline`).
- Each member can explain every line they own in the final discussion.
- Commit regularly under your own account — avoid one person pushing everything.
