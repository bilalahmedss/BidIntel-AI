# BidIntel AI

A bid decision intelligence platform for proposal managers and bid teams. Upload an RFP, upload your draft bid response, and BidIntel automatically extracts evaluation criteria, scores your response against each criterion, flags risky clauses, and calculates a Win Probability Score (WPS) — all powered by Groq's Llama 3.3-70B.

---

## What it does

1. **Parses RFPs** — Extracts gates, scored criteria, checklist signals, evidence requirements, poison pills, and submission rules from any tender PDF.
2. **Scores your response** — Retrieves relevant chunks from your bid response and company knowledge base, then uses an LLM to determine which checklist signals are present and which are missing.
3. **Detects poison pills** — Flags clauses that could automatically disqualify you (unlimited liability, sole-discretion clauses, nationality restrictions, etc.) with a severity rating.
4. **Calculates WPS** — Deterministic Win Probability Score across three financial scenarios (conservative / expected / optimistic). Binary gate failures produce an immediate DO NOT BID verdict.
5. **AI chat assistant** — Ask questions about the RFP, your response, or your company capabilities. Answers draw from all three sources simultaneously.
6. **Company knowledge base** — Upload company docs once (CVs, certifications, past proposals). They're automatically searched during every analysis and every chat.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Backend | FastAPI, Python 3.10+, SQLite (WAL mode) |
| LLM | Groq — `llama-3.3-70b-versatile` |
| Embeddings | SentenceTransformer `all-MiniLM-L6-v2` (local, no API cost) |
| Vector store | ChromaDB (ephemeral per-analysis + persistent KB) |
| PDF extraction | PyMuPDF (text layer only — no OCR) |
| RAG | LlamaIndex + ChromaDB |
| Auth | JWT (HS256) + PBKDF2-SHA256 password hashing |
| Streaming | Server-Sent Events (SSE) for analysis progress and chat |

---

## Project structure

```
BidIntel-AI/
├── backend/                  # FastAPI app
│   ├── main.py               # App factory, CORS, DB init, router registration
│   ├── database.py           # SQLite schema, get_db(), init_db()
│   ├── auth_utils.py         # Password hashing, JWT encode/decode
│   ├── deps.py               # get_current_user() dependency injection
│   ├── websocket.py          # WebSocket routing
│   └── routers/
│       ├── auth.py           # Register, login, me
│       ├── projects.py       # Project CRUD + PDF uploads + team members
│       ├── sections.py       # Response section CRUD + auto-generate from RFP
│       ├── analysis.py       # Pipeline orchestration + SSE streaming
│       ├── ask.py            # Per-project AI chat (streaming)
│       └── lookup.py         # Knowledge base upload/delete/search
│
├── ingestion/
│   ├── rfp_parser.py         # PDF → structured JSON via Groq (chunked)
│   ├── response_loader.py    # Bid response PDF → ephemeral ChromaDB index
│   └── kb_loader.py          # Company docs → persistent ChromaDB index
│
├── rag/
│   └── retriever.py          # make_retriever(index) → (query, top_k) → chunks
│
├── scoring/
│   ├── criterion_scorer.py   # Score each criterion via LLM signal matching
│   ├── poison_pill.py        # Two-pass poison pill detection
│   └── wps_calculator.py     # Deterministic WPS across financial scenarios
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── ProjectsPage.tsx
│   │   │   ├── ProjectWorkspacePage.tsx  # Section editor + analysis trigger
│   │   │   ├── AnalysisPage.tsx          # Results: WPS, criteria, poison pills
│   │   │   ├── AskPage.tsx               # AI chat interface
│   │   │   └── KnowledgeBasePage.tsx     # Upload/manage company docs
│   │   ├── context/
│   │   │   ├── AuthContext.tsx           # JWT token, login/logout
│   │   │   └── AnalysisContext.tsx       # Global analysis job state + SSE
│   │   ├── api/                          # Typed API calls (axios)
│   │   └── components/layout/           # Sidebar, AppShell
│   └── vite.config.ts                   # Proxies /api → localhost:8000 in dev
│
├── dashboard/
│   └── app.py                # Legacy Streamlit UI (standalone, no auth/DB)
│
├── data/                     # Auto-created at runtime
│   ├── bidintel.db           # SQLite database
│   ├── uploads/rfp/          # {project_id}_rfp.pdf
│   ├── uploads/response/     # {project_id}_response.pdf
│   ├── company_brain/        # Raw uploaded KB documents
│   └── chroma_kb/            # Persisted ChromaDB vector index
│
├── tests/
├── .env                      # Secret config (not committed)
├── requirements-backend.txt  # Python deps for FastAPI backend
└── requirements.txt          # Python deps for Streamlit dashboard
```

---

## Getting started

### Prerequisites

- Python 3.10+
- Node.js 18+
- A [Groq API key](https://console.groq.com) (free tier works)

### 1. Clone and configure

```bash
git clone <repo-url>
cd BidIntel-AI
```

Create a `.env` file in the project root:

```env
GROQ_API_KEY=gsk_...            # Your Groq API key
JWT_SECRET_KEY=<random-hex>     # Any long random string, e.g. openssl rand -hex 32
FRONTEND_ORIGIN=http://localhost:5173
```

### 2. Install Python dependencies

```bash
pip install -r requirements-backend.txt
pip install pymupdf chromadb llama-index llama-index-vector-stores-chroma sentence-transformers
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 4. Run

Open two terminals:

**Terminal 1 — Backend:**
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173), register an account, and you're ready.

> **API docs:** [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI, auto-generated)

---

## How the analysis pipeline works

When you click **Run Analysis**, the backend runs a 5-step async pipeline streamed live to the UI:

```
RFP PDF
  │
  ▼
[1] RFP Parser (rfp_parser.py)
    - Extract text pages with PyMuPDF (no OCR — text layer only)
    - Chunk into ~20K char segments with 1-page overlap
    - Send each chunk to Groq → extract gates, criteria, poison pills, rules
    - Deduplicate and merge across chunks
    - Cache parsed JSON in DB
  │
  ▼
[2] Poison Pill Detection (poison_pill.py)
    - Pass 1: Locate parser-extracted clauses in raw pages
    - Pass 2: Groq semantic sweep of every page for missed risky clauses
    - Output: clauses with page number, severity (CRITICAL/HIGH/MEDIUM), reason
  │
  ▼
[3] Index Response + Knowledge Base
    - Bid response PDF → ephemeral ChromaDB (SentenceTransformer embeddings)
    - Company brain docs → persistent ChromaDB (rebuilt on upload)
    - Combined retriever merges results from both, deduplicates
  │
  ▼
[4] Criterion Scoring (criterion_scorer.py)
    - For each criterion: retrieve top-3 chunks from combined index
    - Groq LLM: which checklist signals are present in the retrieved text?
    - Score = (matched signals / total signals) × max_points
    - Binary gates: fail if any criterion has gaps
    - Scored gates: compare sum to advancement threshold
  │
  ▼
[5] WPS Calculation (wps_calculator.py)
    - Conservative / Expected / Optimistic financial adjustments
    - Binary gate failure → WPS = 0, verdict = DO NOT BID
    - WPS = pq_gate × (Phase A + Phase B + Financial Score)
    - Verdict bands: Strong / Competitive / Borderline / Weak / DO NOT BID
```

All steps stream live progress to the frontend via SSE with step label, percentage, and elapsed time.

---

## Key workflows

### Creating a project

1. **Projects** → **New Project**
2. Fill in title, issuer, deadline, status
3. Upload the RFP PDF (required) and your draft bid response PDF (optional)
4. Click **Create**

### Running analysis

1. Open a project → **Project Workspace**
2. Click **Run Analysis** (top-right)
3. Watch live progress — each step shows what's happening and how long it's taking
4. When complete, go to **Analysis** to see results

### Interpreting results

- **WPS tab** — Top-line Win Probability Score across scenarios, elimination reason if applicable
- **Criteria tab** — Per-criterion scores, matched signals, and gap signals (missing evidence)
- **Poison Pills tab** — Risky clauses with page references and severity
- Switch between Conservative / Expected / Optimistic using the scenario selector

### Building the knowledge base

1. Go to **Knowledge Base** in the sidebar
2. Upload company documents: capability statements, CVs, certifications, past proposals, financials
3. Done — they're indexed automatically and used in every future analysis and Ask conversation

### Using Ask (AI chat)

Open a project → navigate to **Ask** and ask anything:
- "Do we meet the ISO 9001 requirement?"
- "What's our proposed methodology for phase 2?"
- "Summarise the evaluation criteria and their weights"

The AI draws context from the RFP, your bid response, and your company knowledge base simultaneously.

---

## Database schema (overview)

| Table | Purpose |
|---|---|
| `users` | Accounts (email, hashed password) |
| `projects` | Bid projects with metadata and cached parsed RFP |
| `project_members` | Many-to-many: users ↔ projects with roles (admin/editor) |
| `sections` | Editable response sections (auto-generated or manual) |
| `analysis_jobs` | Job tracking (queued / running / complete / error) |
| `analysis_results` | Full pipeline output stored as JSON columns |
| `chat_messages` | Per-project chat history |
| `lookup_docs` | Knowledge base file metadata |

SQLite with WAL mode. The database is created automatically at `data/bidintel.db` on first startup.

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key for all LLM calls |
| `JWT_SECRET_KEY` | Yes | Secret for signing JWT tokens — use a long random string in production |
| `FRONTEND_ORIGIN` | Yes | Frontend URL for CORS (`http://localhost:5173` in dev) |

---

## Notes for collaborators

- **LLM costs:** All LLM calls go through Groq. The free tier has rate limits (~30 req/min). For large RFPs (many chunks) you may hit limits — use a paid tier for production workloads.
- **Embeddings are local:** The SentenceTransformer model (`all-MiniLM-L6-v2`) runs on-device with no API cost. It downloads automatically on first use (~90 MB).
- **ChromaDB:** The persistent KB index lives at `data/chroma_kb/`. Don't delete this unless you want to re-index all company brain documents.
- **SQLite:** Suitable for small teams (up to ~10 concurrent users). For larger deployments, the SQL in `database.py` maps cleanly to PostgreSQL with minor syntax changes.
- **Analysis state persists across navigation:** `AnalysisContext` keeps the SSE connection alive globally — you can start analysis on one page and check progress on another.
- **Re-running analysis:** Each run creates a new job and result. Old results accumulate in the DB and are not overwritten.
- **Legacy Streamlit dashboard:** `dashboard/app.py` is a standalone alternative UI with no auth or DB. Useful for quick one-off analysis without setting up the full stack.
