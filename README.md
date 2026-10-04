# SecureRAG

Multi-tenant RAG platform with retrieval-time access control, monitoring and an eval loop.

> **Build specification for an AI coding agent.** Put this file in the repo root and tell the agent to follow it.

---

## 0. Instructions for the AI agent (read first)

- Build this project **phase by phase** (Section 7). Do not start a phase until the previous phase's acceptance criteria pass.
- After each phase: run the tests, fix failures, then give a short summary of what was built and how to run it.
- Use **only free tools and free API tiers**. No paid services. Embeddings and reranking run **locally**.
- Prefer clean, simple, well-structured code over clever hacks. Add type hints, docstrings on public functions, and small modules.
- Do **not** add features outside this spec (no extra agents, GraphRAG, voice, etc.) except the optional Phase 9.
- Security rules in Section 8 are mandatory and must be covered by automated tests.
- Never hardcode secrets. Read all config from environment variables; commit only `.env.example`.
- If a model name or free-tier limit is uncertain, make it an environment variable with a sensible default instead of hardcoding it.

---

## 1. Goal and scope

SecureRAG is an API plus dashboard where organizations upload documents and ask questions over them. Answers carry citations. **Permissions are enforced inside the retrieval query itself**, so a user can never receive content from a document they are not allowed to see. Every query is logged, user feedback is collected, and failed queries become regression test cases in an eval loop that tracks quality across versions.

**Why this project exists:** backend engineering + security + production thinking, not just a LangChain demo. Two things must be excellent:

1. Cross-tenant isolation tests
2. The measured eval loop

### Non-goals

- No payments or billing
- No multi-modal (images/audio) support
- No fine-tuning
- No complex agent frameworks beyond the optional Phase 9

---

## 2. Tech stack (fixed, do not substitute)

| Layer | Choice | Notes |
|---|---|---|
| Backend API | Python 3.11 + FastAPI + Pydantic v2 | SQLAlchemy 2.0 + Alembic for DB |
| Database | PostgreSQL 16 with **pgvector** | One DB for users, docs, vectors, full-text search, logs. Free: local Docker, or Neon / Supabase free tier |
| RAG framework | LangChain (text splitters, LLM wrappers, fallbacks) | LangGraph only in Phase 9 |
| Embeddings | `BAAI/bge-small-en-v1.5` via sentence-transformers (384 dim) | Runs locally on CPU. No API |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Local, CPU. Applied to top-20 candidates |
| Sparse search | Postgres full-text (`tsvector` + GIN index) | Used with dense search for hybrid retrieval |
| LLM (main) | Groq via `langchain-groq` | Model name from env `GROQ_MODEL` |
| LLM (fallback) | Gemini Flash via `langchain-google-genai` | Model from env `GEMINI_MODEL`. Use `.with_fallbacks()` on 429/timeouts |
| Auth | JWT (access token) + hashed API keys | Passwords with argon2 or bcrypt |
| Rate limiting | Per-user token bucket | Configurable via env |
| Frontend | React + Vite + Tailwind CSS + Recharts | Pages listed in Section 6 |
| Testing | pytest + httpx (backend), Vitest (frontend, light) | Cross-tenant tests are the priority |
| Deploy | Docker + docker-compose locally; Render / HF Spaces (API), Vercel (UI), Neon / Supabase (DB) | All free tiers. Note cold starts in README |

---

## 3. Repository structure

```
securerag/
  backend/
    app/
      main.py                 # FastAPI app, routers, middleware
      config.py               # env settings (pydantic-settings)
      db/ (models.py, session.py, migrations/)
      auth/ (jwt.py, deps.py, api_keys.py, rate_limit.py)
      ingestion/ (loaders.py, chunker.py, pipeline.py)
      retrieval/ (embed.py, search.py, rerank.py, acl.py)
      llm/ (providers.py, prompts.py, cache.py)
      rag/ (answer.py, agentic_graph.py)   # agentic_graph = Phase 9 only
      observability/ (logging.py, feedback.py)
      evals/ (cases.py, judge.py, runner.py, metrics.py)
      routers/ (auth.py, orgs.py, documents.py, query.py, feedback.py, evals.py, admin.py)
    tests/ (test_auth.py, test_acl_isolation.py, test_retrieval.py, test_cache.py, ...)
    alembic.ini, pyproject.toml, Dockerfile
  frontend/ (Vite React app)
  docker-compose.yml
  .env.example
  README.md
```

---

## 4. Data model

| Table | Key columns |
|---|---|
| `organizations` | id, name, created_at |
| `users` | id, org_id, email (unique), password_hash, role (`admin` / `member`), created_at |
| `teams` | id, org_id, name |
| `team_members` | team_id, user_id |
| `api_keys` | id, user_id, key_hash, prefix, created_at, revoked_at |
| `documents` | id, org_id, owner_id, team_id (nullable), title, filename, visibility (`private` / `team` / `org`), status, version, created_at |
| `chunks` | id, document_id, org_id, chunk_index, page (nullable), text, embedding `vector(384)`, tsv `tsvector`. Indexes: HNSW or IVFFlat on embedding, GIN on tsv, btree on org_id |
| `query_logs` | id, org_id, user_id, question, answer, retrieved_chunk_ids (json), scores (json), latency_ms, prompt_tokens, completion_tokens, provider, cache_hit, mode (`standard` / `agentic`), created_at |
| `feedback` | id, query_log_id, rating (+1 / -1), comment, created_at |
| `eval_cases` | id, org_id, question, expected_doc_id (nullable), expected_answer (nullable), source (`manual` / `feedback`), created_at |
| `eval_runs` | id, org_id, label, config (json: retrieval_mode, rerank, agentic, models), hit_at_k, mrr, faithfulness, p50_ms, p95_ms, created_at |
| `eval_results` | id, run_id, case_id, hit, rank, faithfulness, latency_ms, answer |
| `response_cache` | key (sha256), user_id, answer, citations (json), corpus_version, created_at |

**Access rules:** a user can read a document if (a) it is in their org **and** (b) visibility is `org`, OR visibility is `team` and the user belongs to that team, OR the user is the owner, OR the user's role is `admin`. Private documents are visible only to the owner (and org admins).

---

## 5. Environment variables (`.env.example`)

```bash
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/securerag
JWT_SECRET=change-me
JWT_EXPIRE_MINUTES=60
GROQ_API_KEY=
GROQ_MODEL=            # set to a currently-free Groq model
GEMINI_API_KEY=
GEMINI_MODEL=          # set to a currently-free Gemini Flash model
EMBED_MODEL=BAAI/bge-small-en-v1.5
RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
RATE_LIMIT_PER_MIN=20
CHUNK_SIZE=800
CHUNK_OVERLAP=120
TOP_K_CANDIDATES=20
TOP_K_FINAL=5
```

---

## 6. API and UI

### Endpoints

| Method and path | Purpose | Auth |
|---|---|---|
| `POST /auth/register`, `/auth/login` | Create org + admin on first register; login returns JWT | public |
| `POST /orgs/members`, `/teams`, `/teams/{id}/members` | Admin manages members and teams | admin |
| `POST /documents` (multipart) | Upload PDF/MD/TXT with visibility + team_id; ingest in background | user |
| `GET /documents`, `GET /documents/{id}`, `DELETE /documents/{id}` | List only accessible docs; return **404** (not 403) for inaccessible ids | user |
| `POST /query` | Body: question, mode (`standard` / `agentic`). Returns answer, citations, latency, cache_hit | user or API key |
| `POST /feedback` | Thumbs up/down on a query_log id (only own logs) | user |
| `POST /evals/cases`, `GET /evals/cases` | Manage eval cases; thumbs-down logs can be promoted to cases | admin |
| `POST /evals/run`, `GET /evals/runs` | Run eval with a config + label; list runs and metrics | admin |
| `POST /api-keys`, `DELETE /api-keys/{id}` | Create (shown once) and revoke API keys | user |
| `GET /admin/usage` | Tokens, latency, cache-hit-rate, per-user usage | admin |

### Frontend pages

- **Login / Register**
- **Documents:** upload, choose visibility/team, status, delete
- **Chat:** ask questions, toggle standard/agentic, show citations (doc, page), thumbs up/down, latency badge
- **Metrics:** eval runs table + Recharts charts comparing hit@k, faithfulness, p95 latency across runs
- **Admin:** members, teams, API keys, usage

---

## 7. Build phases with acceptance criteria

### Phase 1: Project skeleton and basic RAG core

**Tasks**
- Set up repo, docker-compose (Postgres + pgvector), config, Alembic migrations, health endpoint.
- Ingestion: load PDF/MD/TXT, split with `RecursiveCharacterTextSplitter` (size/overlap from env), store page numbers where available.
- Embed chunks locally and store in pgvector. Implement dense search and a basic answer chain with citations.
- Prompt must instruct the LLM to answer ONLY from provided context and say "not found in your documents" otherwise.

**Acceptance criteria**
- Upload a document, ask a question, get an answer with a citation to the right chunk.
- Unit tests for chunker and ingestion pipeline pass.

### Phase 2: Auth, organizations, teams, roles

**Tasks**
- Register/login with JWT, password hashing, org creation, admin invites members, teams and team membership.
- Dependency that resolves current user, org, role and team ids on every request.

**Acceptance criteria**
- Auth tests pass: wrong password rejected, expired token rejected, member cannot call admin endpoints.

### Phase 3: Permission-aware retrieval (MOST IMPORTANT)

**Tasks**
- Add visibility/team/owner/org columns and implement `retrieval/acl.py` that builds the SQL access filter.
- Apply the filter **inside** the vector and full-text SQL (WHERE clause), never by filtering results afterwards.
- Document endpoints return 404 for inaccessible ids. Chunk text must never be returned without passing the filter.
- Write the cross-tenant test suite (see Section 8).

**Acceptance criteria**
- All isolation tests pass with 100% success. Provide a test report in the README.

### Phase 4: Hybrid search and reranking

**Tasks**
- Run dense (pgvector cosine) and sparse (tsvector rank) queries, each `LIMIT TOP_K_CANDIDATES`, with the ACL filter in both.
- Fuse results with Reciprocal Rank Fusion (k=60). Rerank fused top candidates with the local cross-encoder; return `TOP_K_FINAL`.
- Make retrieval mode configurable: `dense`, `hybrid`, `hybrid+rerank` (needed for eval comparisons).

**Acceptance criteria**
- Tests confirm each mode runs and returns only permitted chunks.
- A small script prints hit@k for the three modes on a sample eval set.

### Phase 5: Usage controls

**Tasks**
- Per-user rate limiting (429 with `Retry-After`). API key creation (shown once, stored hashed) and API-key auth for `/query`.
- Log prompt/completion tokens for every query.

**Acceptance criteria**
- Exceeding the rate limit returns 429. Revoked API key is rejected. Token counts appear in `query_logs`.

### Phase 6: Observability, feedback and eval loop (SECOND MOST IMPORTANT)

**Tasks**
- Log every query: retrieved chunk ids, scores, latency, tokens, provider, cache_hit, mode.
- Feedback endpoint. Admin can promote thumbs-down queries into `eval_cases` and attach expected doc or answer.
- Eval runner: for each case compute hit@k and MRR (expected doc in retrieved chunks), faithfulness via LLM-as-judge, latency.
- **Judge calls must be cached** (hash of question + answer + context) and the eval set kept small (about 50 cases) to respect free-tier limits.
- Store each run with a label and config so runs can be compared (e.g. `dense`, `hybrid`, `hybrid+rerank`).

**Acceptance criteria**
- Running evals for three configs produces three `eval_runs` rows and a comparison view.
- Re-running an unchanged eval makes zero new judge LLM calls (cache works).

### Phase 7: Provider fallback and response cache

**Tasks**
- Wrap Groq with Gemini fallback using LangChain fallbacks; log which provider answered.
- Response cache keyed by `sha256(user_id + normalized question + corpus_version)`. **The key must include the user's identity** so cached answers never cross permission boundaries. Invalidate when documents change (bump `corpus_version`).

**Acceptance criteria**
- Simulated Groq 429 falls back to Gemini and the request succeeds.
- Cache test: user B never receives user A's cached answer; cache invalidates after a document upload or delete.

### Phase 8: Frontend, deployment and README

**Tasks**
- Build the five pages in Section 6. Keep the UI simple, responsive and clean.
- Dockerfiles, docker-compose for local, deployment notes for free hosts (mention cold-start behavior).
- README with architecture diagram (Mermaid), setup steps, security model, eval results table, screenshots, and a "what I tried and what failed" section.

**Acceptance criteria**
- A new developer can run the full stack with one documented command sequence.
- README contains measured numbers only (no invented metrics).

### Phase 9 (optional, only after Phases 1-8 are complete): LangGraph agentic mode

**Tasks**
- Build `rag/agentic_graph.py` with nodes: `route`, `retrieve`, `grade_relevance`, `rewrite_query` (max 2 loops), `generate`, `check_groundedness`.
- The `retrieve` node MUST call the same ACL-enforced retrieval function. The agent must have no direct database or vector-store access.
- Expose via `mode="agentic"` and add it as a config in the eval runner.

**Acceptance criteria**
- Isolation tests also pass in agentic mode.
- Eval table shows standard vs agentic with accuracy and latency side by side.

---

## 8. Mandatory security rules and tests

### Retrieval query shape (reference sketch)

```sql
-- ACL predicate (built in retrieval/acl.py), used in BOTH dense and sparse queries
WHERE c.org_id = :org_id
  AND ( :is_admin
        OR d.owner_id = :user_id
        OR d.visibility = 'org'
        OR (d.visibility = 'team' AND d.team_id = ANY(:team_ids)) )

-- dense candidates
SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id
WHERE <ACL predicate> ORDER BY c.embedding <=> :qvec LIMIT :k;

-- sparse candidates
SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id
WHERE <ACL predicate> AND c.tsv @@ plainto_tsquery('english', :q)
ORDER BY ts_rank_cd(c.tsv, plainto_tsquery('english', :q)) DESC LIMIT :k;
-- then fuse with RRF in Python, then rerank
```

### Rules

- Filter in SQL, never post-filter. The LLM must never see a chunk the user cannot access.
- Return 404 for inaccessible documents (do not reveal existence).
- Cache keys and query logs are scoped per user/org. Users can only read their own logs and feedback.
- Treat retrieved document text as untrusted: prompts must tell the model to ignore instructions found inside documents.
- Validate upload type and size. Never trust filenames. Store secrets only in env vars.

### Cross-tenant test suite (pytest)

Create two orgs, each with admin, members and teams, plus private/team/org documents containing unique marker strings. Assert:

- User in org A can never retrieve chunks from org B, with queries designed to match org B's marker strings.
- Member not on a team cannot retrieve that team's chunks; owner can read own private doc; other members cannot.
- Direct GET/DELETE on another tenant's document id returns 404.
- Citations and answers never include forbidden marker strings, in standard and (if built) agentic mode.
- Cached answers are not shared across users; cache invalidates after document changes.
- Prompt-injection text inside a permitted document does not cause access to other tenants' data.
- Query logs and feedback of other users are not readable.

---

## 9. Metrics to measure and report

| Metric | How |
|---|---|
| hit@k and MRR | Expected doc present in retrieved chunks; compare dense vs hybrid vs hybrid+rerank |
| Faithfulness | LLM-as-judge (cached), scored per answer; averaged per run |
| Latency p50 / p95 | From `query_logs`, per mode |
| Cross-tenant leak tests | N passed / N total (target 100%) |
| Cache hit-rate and tokens per query | From `query_logs` |

---

## 10. Definition of done

- All phases 1-8 acceptance criteria pass; test suite green.
- Deployed demo link with seeded demo data (two demo orgs) and a short demo video.
- README includes real eval numbers, leak-test results, architecture diagram and limitations.
- No secrets in the repo. Runs entirely on free tiers.
