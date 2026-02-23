# Cost & API Optimization Design

This document describes architecture-level optimizations to reduce LLM API costs and align compute with usage tiers: **RAG over your own embeddings**, **hybrid deterministic + LLM logic**, **strict schemas & validation**, and **cost-aware design with tier-based models**.

---

## 1. RAG over your own embeddings

**Goal:** Avoid feeding large background docs into the model every time. Embed knowledge (S3 data, reports, FAQs), retrieve only top-K relevant chunks, and pass those to the model to cut input tokens.

### Current state
- **Market Research:** Full report text (or chunked) is sent to the LLM each request. No reuse of prior embeddings.
- **S3:** Industry surveys are listed and downloaded; content is not embedded or used as retrieval knowledge.

### Target architecture
- **Knowledge base:** Ingest S3 reports/FAQs (and optionally past reverse-engineered outputs) into a vector store.
- **Embedding:** Use a single embedding model (e.g. OpenAI `text-embedding-3-small` or local model) to embed chunks (e.g. 512–1024 tokens with overlap).
- **Retrieval:** For each reverse-engineer request, embed the user’s report (or a short summary), retrieve top-K most similar chunks from the knowledge base, and pass only those chunks + the current report to the LLM.
- **Effect:** Large background corpora are no longer sent every time; only the current report + a small, relevant context window is sent → large input-token savings.

### Implementation phases
| Phase | Task | Notes |
|-------|------|--------|
| 1 | Define chunking strategy (size, overlap) and metadata (source, industry) | Reuse existing `MAX_REPORT_CHARS` / chunk overlap where relevant |
| 2 | Embedding service: embed text → vector; optional batch for S3 ingestion | Config: `OPENAI_EMBEDDING_MODEL` or local embedding |
| 3 | Vector store: store and query by vector (e.g. in-memory FAISS, or OpenSearch / Pinecone / pgvector) | Start simple (in-memory) for dev; pluggable for production |
| 4 | S3 ingestion job: list objects under prefix, extract text (PDF/CSV), chunk, embed, upsert | Run on schedule or on-demand; optional “refresh index” API |
| 5 | RAG in reverse-engineer: retrieve top-K by report (or summary), build context string, pass to LLM with strict token budget | `RAG_TOP_K`, `RAG_CONTEXT_MAX_TOKENS` in config |

---

## 2. Hybrid deterministic + LLM logic

**Goal:** Use plain Python for scoring, filtering, segment selection, and rule-based decisions. Call LLMs only for open-ended reasoning and natural-language synthesis.

### Current state
- **Validation:** Already hybrid — statistical tests (chi-square, KS, etc.) and match scores are pure Python; no LLM.
- **Market Research:** LLM does full reverse-engineering; heuristic fallback when no API key does simple extraction. No rule-based pre/post steps to reduce LLM scope.

### Target behavior
- **Rules first:**  
  - Detect report type, language, presence of tables/figures.  
  - Extract sample size (n), question labels, and numeric tables with regex/rules where unambiguous.  
  - Score “confidence” per question (e.g. clear table → high; prose only → low).  
- **LLM only for:**  
  - Ambiguous or free-text parts (research intent, question phrasing, option labels).  
  - Synthesizing natural language (objectives, section summaries).  
- **Optional:** Two-step flow: (1) rule-based extraction → structured stub, (2) LLM fills only missing or low-confidence fields.

### Implementation phases
| Phase | Task | Notes |
|-------|------|--------|
| 1 | Expose `_extract_overall_sample_size` and table-detection heuristics; use to pre-fill n and skip LLM when report is “simple” | Gate: e.g. “if single table and all numeric → heuristic only” |
| 2 | Add confidence scoring per question (deterministic); pass only low-confidence items to LLM or smaller model | Reduces tokens and allows cheaper model for easy questions |
| 3 | Split prompt: “objectives/summaries” vs “questionnaire reconstruction”; call LLM only for the part that needs it | Optional; can combine with RAG context |

---

## 3. Strict schemas & validation

**Goal:** Force the model to output predictable JSON; validate server-side. On invalid output, run a cheap “repair” pass (e.g. smaller model) instead of re-running full generation on the expensive model.

### Current state
- **Market Research:** Model returns markdown; server parses with regex (`_parse_structured_output`). Parse failures fall back to heuristic; no JSON schema, no repair step.

### Target behavior
- **Structured output:** Request JSON (OpenAI `response_format` / Claude structured output) matching a fixed schema: e.g. `overall_objectives`, `overall_sample_size_n`, `sections[]`, `questions[]` with `question_id`, `question_text`, `options[]`, `option_values[]`, `sample_size_n`.
- **Validation:** After each LLM call, validate against the schema (Pydantic). If valid → use. If invalid → call a **repair** step: small model (e.g. `gpt-4o-mini` / `claude-3-haiku`) with system prompt “Fix this JSON to match the schema” and the raw string. Single retry with repaired JSON; if still invalid, fall back to heuristic.
- **Effect:** Fewer full re-runs on the primary model; invalid outputs are fixed with a much cheaper call.

### Implementation phases
| Phase | Task | Notes |
|-------|------|--------|
| 1 | Define Pydantic schema for reverse-engineer output; add JSON-mode prompts and `response_format` in OpenAI/Claude calls | See `backend/routers/market_research.py` |
| 2 | Server-side validation: parse JSON → validate with Pydantic; on failure, call repair endpoint (small model, short prompt) | Config: `REPAIR_MODEL_OPENAI`, `REPAIR_MODEL_ANTHROPIC` |
| 3 | Keep markdown path as fallback when JSON not supported or repair fails; merge with heuristic where needed | Backward compatible |

---

## 4. Process & pricing alignment

**Goal:** Cost-aware design reviews and tier-based model/compute so that heavy users pay for extra LLM load.

### Cost-aware design checklist (for every new feature)
- **Token estimate:** How many input/output tokens per request (and per user per month)? Can part of the flow use rules, caching, or a smaller model?
- **Avoid:** Designs that call the most expensive model in a loop without caching or RAG.
- **Prefer:** Deterministic logic first; RAG to shrink context; strict JSON + repair to avoid re-runs; tier-based model selection.

### Tier-based model alignment
| Tier | Respondents / study | Features | Model / compute |
|------|---------------------|----------|------------------|
| **Basic / Student** | Small (e.g. &lt; 500), limited rebuttal time | Core validation, simple reverse-engineer | Cheaper models only (e.g. `gpt-4o-mini`, Haiku); optional RAG; no Sonnet |
| **Pro** | Medium (e.g. 500–2k) | Full validation, reverse-engineer, richer insights | Mix: mini for repair/simple; Sonnet for main reverse-engineer; RAG enabled |
| **Enterprise** | Large, full rebuttal, simulations | Full stack, Sonnet-backed simulations, full reverse-engineering and insights | Sonnet/default models; higher rate limits; priced to cover LLM cost |

### Implementation phases
| Phase | Task | Notes |
|-------|------|--------|
| 1 | Add config: `TIER` or `PLAN` (basic / pro / enterprise); `OPENAI_MODEL_BASIC`, `OPENAI_MODEL_PRO`, `REPAIR_MODEL_*` | Default tier from env; can be overridden per request if multi-tenant |
| 2 | In market research (and any future LLM features): select model from tier (basic → cheap only; pro/enterprise → primary + repair) | Central helper: `get_model_for_tier(feature, tier)` |
| 3 | Optional: rate limits or caps per tier (e.g. max reverse-engineer calls per day for Basic) | Enforced in API layer |

---

## 5. Config summary (current + proposed)

| Variable | Purpose |
|----------|--------|
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | Existing |
| `OPENAI_MODEL`, `ANTHROPIC_MODEL` | Primary model (existing) |
| `OPENAI_MODEL_BASIC`, `ANTHROPIC_MODEL_BASIC` | Tier: Basic uses these (e.g. gpt-4o-mini, claude-3-haiku) |
| `REPAIR_MODEL_OPENAI`, `REPAIR_MODEL_ANTHROPIC` | Cheap model for JSON repair (e.g. gpt-4o-mini) |
| `TIER` or `PLAN` | `basic` \| `pro` \| `enterprise` |
| `RAG_ENABLED` | Enable RAG retrieval in reverse-engineer (future) |
| `RAG_TOP_K`, `RAG_CONTEXT_MAX_TOKENS` | RAG params (future) |
| `OPENAI_EMBEDDING_MODEL` | Embeddings for RAG (future) |

---

## 6. Implementation order (recommended)

1. **Strict JSON + validation + repair** — immediate token and cost savings from fewer full re-runs; small code surface.
2. **Tier-based model selection** — config + one branch in market research (and any new LLM feature).
3. **RAG over S3** — embedding service, vector store, S3 ingestion, then wire into reverse-engineer.
4. **Hybrid rules** — expand heuristics and confidence scoring; gate LLM to “only when needed.”
5. **Cost-aware review** — document this checklist in team process; optional per-feature token estimates.

---

## 7. Implemented now (current codebase)

The following are already wired into `backend/routers/market_research.py`:

- Deterministic request cache keyed by `(provider, model, system_prompt, prompt_hash)`.
- Optional near-duplicate cache reuse for almost-identical prompts.
- Concurrency limit for heavy LLM calls (`LLM_MAX_CONCURRENT_HEAVY_CALLS`).
- Daily token budget guardrail (`LLM_DAILY_TOKEN_BUDGET`) with best-effort usage tracking.
- Tier-based model selection (`TIER=basic|pro|enterprise`) and cheap repair model path.

Tune these via `.env` (see `.env.example`).
