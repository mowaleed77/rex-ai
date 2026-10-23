# RAG + real LLM (Member 1)

Flow per message: user message -> `Retriever` (BM25 over `data/rag_docs/*.md`) -> top 4 documents go into the
prompt as the ONLY allowed facts -> LLM answers -> answer + "Sources" line.

| Piece | File |
|---|---|
| Corpus generator | `rex/rag/build_docs.py` (`python -m rex.rag.build_docs`) |
| Corpus (30 docs, EN+AR: 9 courses, catalog, pricing, formats, instructors, FAQ, admission) | `data/rag_docs/` |
| Retriever (BM25, Arabic-aware) | `rex/rag/retriever.py` |
| LLM client (any OpenAI-compatible API) | `rex/rag/llm.py` |
| Assistant | `rex/assistant/rag.py` (`RagAssistant`) |

## Enable the LLM
1. `cp .env.example .env`, set `LLM_API_KEY` (and `LLM_BASE_URL` / `LLM_MODEL` for Groq, Gemini, Ollama...).
2. Restart Streamlit. The sidebar shows "LLM + RAG on".
No key or provider error -> automatic fallback to the rule-based bot.

## Update the knowledge
Edit `data/*.json` (replace the SAMPLE data with the academy catalog), then run `python -m rex.rag.build_docs`.

## Guardrails
Answer only from context; no invented prices/offers; no accreditation claims; consent before saving leads (deterministic).

## Limits / next step
BM25 is keyword-based, not embeddings. Upgrade path: replace `Retriever.search` with Chroma/FAISS embeddings (same interface).
