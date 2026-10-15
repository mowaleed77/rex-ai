# System Architecture

```mermaid
flowchart TD
    U[User / Admin Interface<br/>Streamlit + REST API] --> O[REX AI Orchestrator / Router]
    O --> A1[Agent 1: REX Course Assistant]
    O --> A2[Agent 2: RFP Research<br/>Egypt + KSA filter]
    O --> A3[Agent 3: Curriculum &<br/>Accreditation Alignment]
    O --> A4[Agent 4: Document Generation]
    O --> A5[Agent 5: Marketing]
    A3 -- approved curriculum --> A4
    A3 -- approved course data --> A5
    A5 -- draft campaign --> ADM[Admin approval]
    A1 & A2 & A3 & A4 & A5 --> KB[(Knowledge Base / RAG)]
    A1 & A2 & A3 & A4 & A5 --> LLM[LLM Integration]
    A1 & A2 --> DB[(Database / Google Sheets<br/>leads, RFPs)]
    A4 --> DOC[(Document Storage / PDFs)]
    A2 --> EXT[External APIs / Search Tools]
    O -.-> LOG[Logging & Error Handling]
```

## Components
| Component | Sprint 1 implementation | Planned |
|---|---|---|
| Interface | Streamlit app, CLI, FastAPI `/chat` | Unified admin UI (Sprint 3) |
| Orchestrator | `rex/agents/orchestrator.py` — registry + dispatch + error capture | Multi-agent workflows |
| Agent interface | `rex/agents/base.py` — `Agent.run(task) -> AgentResult(output, message, sources)` | — |
| Knowledge base | JSON files in `data/` with source + update date per record | Chroma/FAISS embeddings |
| LLM | Not required for baseline | OpenAI-compatible API (Sprint 2) |
| Storage | CSV for leads | SQLite / Google Sheets for RFPs |

## Data contract between agents
Every agent returns `AgentResult` so outputs are reusable and **traceable** (`sources` list):
```
AgentResult(agent: str, ok: bool, output: dict, message: str, sources: list[str])
```
Planned connected workflow (acceptance criterion): **Curriculum approved → Marketing generates campaign → Admin approves**.
