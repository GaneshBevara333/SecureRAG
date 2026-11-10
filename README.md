# SecureRAG

Multi-tenant Retrieval-Augmented Generation (RAG) platform with **retrieval-time access control**, provider fallback, real-time observability, and an automated regression evaluation loop.

---

## 1. What It Is

SecureRAG is an enterprise-grade RAG platform built with security, backend rigor, and production reliability at its core. Rather than relying on simple wrappers or post-retrieval filtering, SecureRAG enforces authorization boundaries **directly inside the SQL database query**. Documents and chunks inaccessible to a user are never loaded into memory or exposed to the Large Language Model.

### Key Capabilities
- **Permission-Aware Retrieval (ACL in SQL):** Enforces tenant isolation, team-based visibility, and private document permissions inside both pgvector dense search and tsvector sparse search queries. Inaccessible documents return `404 Not Found` to prevent existence leakage.
- **Hybrid Search & Local Reranking:** Dense cosine distance (pgvector) + Sparse BM25-equivalent full-text search (`tsvector` + GIN index) combined via Reciprocal Rank Fusion ($k=60$) and reranked using a local cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`). Runs locally on CPU with zero paid API dependencies.
- **LLM Provider Fallback:** Primary Groq provider with automatic LangChain fallback to Gemini Flash upon `429 Rate Limit` or timeout errors.
- **User-Scoped Response Cache:** Cache keys hashed as `SHA-256(user_id + normalized_question + corpus_version)`. Auto-invalidates on document upload or deletion by bumping `corpus_version`.
- **Token Bucket Rate Limiting:** Per-user rate limiting returning `429 Too Many Requests` with a standard `Retry-After` header.
- **Observability & Feedback Loop:** Logs prompt/completion tokens, latency, retrieved chunk IDs, scores, provider, and cache hits for every query. Negative user feedback can be promoted directly into evaluation benchmark cases.
- **Automated Regression Eval Loop:** Measures `Hit@k`, `MRR`, `Faithfulness` (via cached LLM-as-a-judge with 429 exponential backoff), and latency percentiles ($p50$ / $p95$) across configurable retrieval modes (`dense`, `hybrid`, `hybrid+rerank`).

---

## 2. Architecture Diagram

```mermaid
flowchart TD
    subgraph ClientLayer["Client Layer"]
        UI["React + Vite + Tailwind + Recharts UI"]
        APIClient["External API Client (CLI / cURL)"]
    end

    subgraph APIGateway["FastAPI Backend"]
        Auth["Auth & Security Engine<br/>• JWT Access Token Validation<br/>• SHA-256 Hashed API Key Auth<br/>• Per-User Token Bucket Rate Limiter"]
        DocRouter["Documents Router<br/>• Multipart Upload (PDF/TXT/MD)<br/>• Recursive Character Splitter<br/>• Corpus Version Bump"]
        QueryRouter["Query & Answer Engine<br/>• Response Cache Lookup<br/>• Grounded Answer Generator<br/>• Query Logger & Token Tracker"]
        EvalRouter["Evals & Admin Engine<br/>• Eval Runner (Hit@k, MRR)<br/>• Faithfulness LLM Judge<br/>• Usage Aggregation"]
    end

    subgraph StorageLayer["PostgreSQL 16 + pgvector (Neon / Local)"]
        AclEngine["SQL Retrieval Engine<br/>WHERE c.org_id = :org_id<br/>AND (:is_admin OR d.owner_id = :uid<br/>OR d.visibility = 'org'<br/>OR (d.visibility = 'team' AND d.team_id = ANY(:tids)))"]
        DenseIndex[("pgvector HNSW<br/>BAAI/bge-small-en-v1.5<br/>384-dim Embeddings")]
        SparseIndex[("GIN tsvector<br/>PostgreSQL Full-Text Search")]
        RRF["Reciprocal Rank Fusion<br/>k = 60"]
        CrossEncoder["Local Cross-Encoder<br/>ms-marco-MiniLM-L-6-v2<br/>Top-K Final Reranking"]
        DBTables[("Relational Tables<br/>• orgs, users, teams<br/>• documents, chunks<br/>• query_logs, feedback<br/>• eval_cases, eval_runs<br/>• response_cache")]
    end

    subgraph LLMProviders["Inference & Fallback"]
        Groq["Groq (Primary LLM)<br/>llama-3.3-70b-versatile"]
        Gemini["Gemini Flash (Fallback LLM)<br/>Triggered on 429 / Timeouts"]
        ResponseCache[("Response Cache<br/>sha256(user_id + q + corpus_v)")]
    end

    UI -->|Bearer JWT| Auth
    APIClient -->|X-API-Key| Auth
    Auth --> DocRouter
    Auth --> QueryRouter
    Auth --> EvalRouter

    DocRouter -->|Chunks & Embeddings| DBTables
    QueryRouter -->|Check Cache| ResponseCache
    QueryRouter -->|Execute Filtered Search| AclEngine
    AclEngine --> DenseIndex
    AclEngine --> SparseIndex
    DenseIndex --> RRF
    SparseIndex --> RRF
    RRF --> CrossEncoder
    CrossEncoder -->|Permitted Chunks Only| QueryRouter

    QueryRouter -->|Prompt + Context| Groq
    Groq -.->|Fallback on 429| Gemini
    Groq -->|Answer + Citations| QueryRouter
    Gemini -->|Answer + Citations| QueryRouter
    QueryRouter -->|Store Log & Tokens| DBTables
```

---

## 3. Security Model

SecureRAG adheres to strict zero-trust multi-tenancy principles:

1. **Retrieval-Time SQL ACL Enforcement:**
   Every dense and sparse candidate query executes the following mandatory filter directly inside PostgreSQL:
   ```sql
   WHERE c.org_id = :org_id
     AND (
       :is_admin
       OR d.owner_id = :user_id
       OR d.visibility = 'org'
       OR (d.visibility = 'team' AND d.team_id = ANY(:team_ids))
     )
   ```
   **Never Post-Filter:** If a user does not have permission to view a document, its chunks are never fetched from disk, never embedded into candidate lists, and never provided to the LLM context window.

2. **No Information Leaks via Status Codes:**
   Direct `GET /documents/{id}` and `DELETE /documents/{id}` requests on inaccessible documents return `404 Not Found` instead of `403 Forbidden`, preventing attackers from enumerating document existence across tenants.

3. **User-Scoped Response Caching:**
   Cache keys are generated using `SHA-256(user_id + normalized_question + corpus_version)`. Because the key binds directly to `user_id`, User B cannot retrieve cached answers originating from User A's private documents. Whenever any document in the organization is uploaded or deleted, `corpus_version` increments, instantly invalidating stale responses.

4. **Credential & API Key Security:**
   - User passwords are encrypted with bcrypt.
   - API keys (`sec_<token>`) are shown once upon creation and stored exclusively as SHA-256 hashes in the database.
   - Revoked keys are rejected immediately (`401 Unauthorized`).

5. **Prompt Injection Mitigation:**
   Retrieved chunk text is treated as untrusted data. The system prompt instructs the model to answer strictly from factual statements in context and to ignore adversarial instructions embedded in documents.

---

## 4. Local Setup Steps (No Docker)

### Prerequisites
- **Python 3.11+**
- **Node.js 18+ & npm**
- **PostgreSQL 16 with pgvector extension** (or a free cloud database instance from [Neon](https://neon.tech))

### 1. Clone & Configure Environment
```bash
git clone https://github.com/your-org/securerag.git
cd securerag
cp .env.example .env
```

Edit `.env` with your database URL and API keys:
```bash
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/securerag
JWT_SECRET=your-secure-random-secret
JWT_EXPIRE_MINUTES=60
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash
EMBED_MODEL=BAAI/bge-small-en-v1.5
RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
RATE_LIMIT_PER_MIN=20
CHUNK_SIZE=800
CHUNK_OVERLAP=120
TOP_K_CANDIDATES=20
TOP_K_FINAL=5
```

### 2. Backend Setup
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
# source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
```
Backend API will be running at `http://localhost:8000` (API documentation available at `http://localhost:8000/docs`).

### 3. Frontend Setup
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
Frontend UI will be running at `http://localhost:5173`.

---

## 5. Deployment Guide

SecureRAG is architected to run completely on **free tiers** across modern cloud platforms.

### Database: Neon Serverless PostgreSQL
1. Create a free account at [neon.tech](https://neon.tech) and create a PostgreSQL 16 project.
2. In the Neon SQL Console, enable `vector`:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Copy the pooled connection string with `sslmode=require` and use it as `DATABASE_URL`.

### Backend: Render Web Service
1. Create a new **Web Service** on [render.com](https://render.com) connected to your repository.
2. Configure settings:
   - **Environment:** Python 3
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt && alembic upgrade head`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Add Environment Variables in Render:
   | Variable | Value / Notes |
   |---|---|
   | `DATABASE_URL` | Neon connection string (`postgresql+psycopg://...`) |
   | `JWT_SECRET` | 32+ character random secret string |
   | `JWT_EXPIRE_MINUTES` | `60` |
   | `GROQ_API_KEY` | Your Groq API key |
   | `GROQ_MODEL` | `llama-3.3-70b-versatile` |
   | `GEMINI_API_KEY` | Your Google AI Studio Gemini API key |
   | `GEMINI_MODEL` | `gemini-1.5-flash` |
   | `EMBED_MODEL` | `BAAI/bge-small-en-v1.5` |
   | `RERANK_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
   | `RATE_LIMIT_PER_MIN` | `20` |
   | `TOP_K_CANDIDATES` | `20` |
   | `TOP_K_FINAL` | `5` |

### Frontend: Vercel
1. Create a new project on [vercel.com](https://vercel.com) importing the repository.
2. Configure settings:
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
3. Add Environment Variable:
   - `VITE_API_URL`: `https://<your-render-service-name>.onrender.com`

### Note on Cold Starts
> [!NOTE]
> **Free-Tier Cold Start Characteristics:**
> - **Render Web Services:** Free instances spin down after 15 minutes of inactivity. The initial incoming request triggers a cold start taking **40–60 seconds** as the container boots and loads the local PyTorch sentence-transformer (`BAAI/bge-small-en-v1.5`) and Cross-Encoder (`ms-marco-MiniLM-L-6-v2`) models into CPU memory. Subsequent requests run with standard low latency.
> - **Neon Serverless Database:** Inactive compute endpoints suspend automatically and wake within **1–3 seconds** on the next incoming query.

---

## 6. Evaluation & Benchmarks

The built-in evaluation framework runs regression suites across retrieval modes (`dense`, `hybrid`, `hybrid+rerank`) and calculates:
- **Hit@k:** Fraction of cases where the expected document is present in the top-$k$ retrieved chunks.
- **MRR (Mean Reciprocal Rank):** Average reciprocal rank of the first relevant chunk.
- **Faithfulness:** Factual groundedness scored by LLM-as-a-judge ($0.0 \dots 1.0$) with SHA-256 caching.
- **Latency ($p50$ / $p95$):** Measured in milliseconds per query.

### Measured Evaluation Numbers
<!-- PLACEHOLDER: Eval Results (hit@k, MRR, Faithfulness, Latency across Dense / Hybrid / Hybrid+Rerank) -->
| Retrieval Mode | Hit@1 | Hit@3 | Hit@5 | MRR | Faithfulness | Latency p50 | Latency p95 |
|---|---|---|---|---|---|---|---|
| Dense (pgvector) | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* |
| Hybrid (Dense + Sparse RRF) | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* |
| Hybrid + Reranker (Cross-Encoder) | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* | *[PLACEHOLDER]* |

---

## 7. Cross-Tenant Isolation Test Results

Automated cross-tenant pytest suite verifying strict multi-tenant data boundaries:
- User in Org A querying for Org B's unique marker strings: 0 chunks leaked.
- Member outside a team querying team-restricted documents: 0 chunks leaked.
- Non-owner querying private document: 0 chunks leaked.
- Direct `GET` / `DELETE` on inaccessible document ID: returns `404 Not Found`.
- Prompt injection text inside permitted documents: 0 unauthorized chunks accessed.

<!-- PLACEHOLDER: Cross-Tenant Isolation Test Results (N passed / N total) -->
```
<!-- PLACEHOLDER: Paste your test output here (e.g. 44 passed in 85s) -->
```

---

## 8. Application Screenshots

<!-- PLACEHOLDER: Application Screenshots (Chat, Documents, Metrics, Admin) -->

### Chat Interface with Citations, Latency & Cache Badges
<!-- PLACEHOLDER: Screenshot of Chat UI showing answer, citations, cache hit badge, and thumbs feedback -->

### Document Management & Access Control
<!-- PLACEHOLDER: Screenshot of Documents table showing Org, Team, and Private documents -->

### Evaluation Metrics & Quality Benchmarks
<!-- PLACEHOLDER: Screenshot of Metrics page showing Recharts bar charts and historical runs table -->

### Admin Center: Members, Teams, API Keys & Usage Controls
<!-- PLACEHOLDER: Screenshot of Admin Center showing usage stats and token analytics -->

---

## 9. Specification Reference

The original phase-by-phase build specification is preserved in [`SPEC.md`](SPEC.md).
