# BidIntel AI

BidIntel AI is a bid decision intelligence platform for proposal managers and bid teams. It parses RFPs, scores your draft response against evaluation criteria, flags risky clauses, calculates a Win Probability Score (WPS), and gives you a grounded AI workspace for project-by-project bidding.

## What BidIntel Does

- Parses RFP PDFs into structured gates, criteria, checklist signals, evidence requirements, poison pills, and submission rules.
- Scores your response content against extracted criteria using Groq plus retrieval from your response artifacts and company knowledge base.
- Detects poison-pill clauses that can create legal or commercial disqualification risk.
- Calculates deterministic WPS outcomes across conservative, expected, and optimistic financial scenarios.
- Provides a project-level AI chat assistant grounded in the RFP, uploaded response material, and company knowledge base.
- Stores analyses, chat history, sections, users, and projects in SQLite.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Backend | FastAPI, Python, SQLite |
| LLM | Groq chat completions |
| Embeddings | SentenceTransformers `all-MiniLM-L6-v2` |
| Vector Store | ChromaDB |
| Retrieval | LlamaIndex + Chroma |
| Auth | JWT (HS256) + PBKDF2 password hashing |
| Streaming | Server-Sent Events (SSE) |
| PDF Extraction | PyMuPDF with optional Tesseract OCR fallback |

## Repository Layout

```text
BidIntel-AI/
|-- backend/
|   |-- main.py
|   |-- database.py
|   |-- auth_utils.py
|   |-- deps.py
|   |-- groq_client.py
|   |-- llm_schemas.py
|   |-- schemas.py
|   `-- routers/
|       |-- auth.py
|       |-- projects.py
|       |-- sections.py
|       |-- analysis.py
|       |-- ask.py
|       `-- lookup.py
|-- frontend/
|   |-- src/
|   |   |-- api/
|   |   |-- components/
|   |   |-- context/
|   |   `-- pages/
|   |-- package.json
|   `-- vite.config.ts
|-- ingestion/
|-- rag/
|-- scoring/
|-- tests/
|-- scripts/
`-- requirements.txt
```

## Core Workflows

### 1. Create a Project

Project creation now requires all of the following:

- Project title
- Company knowledge data
- Response RFP content

Optional project metadata:

- Issuer
- RFP ID
- Deadline
- Status
- RFP PDF attachment
- Response PDF attachment

This means a user cannot create a project with empty or missing `company_knowledge_data` or `response_rfp`.

### 2. Build the Company Knowledge Base

Upload reusable company documents from the Knowledge Base page. These documents are indexed and reused across analyses and AI chat.

Examples:

- CVs
- Certifications
- Capability statements
- Past proposals
- Financial statements

### 3. Run Analysis

When a project analysis starts, the backend:

1. extracts and parses the RFP
2. performs poison-pill detection
3. indexes response artifacts and combines them with company knowledge retrieval
4. batch-scores criteria
5. calculates WPS and stores the result

Progress is streamed to the UI with SSE.

### 4. Use Ask

The Ask page lets users ask grounded questions about:

- the RFP
- the response
- the company knowledge base

## Installation Guide

### Prerequisites

- Python 3.10 or newer
- Node.js 18 or newer
- npm
- Groq API key
- Optional: Tesseract OCR for scanned PDFs

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd BidIntel-AI
```

### 2. Create a Python Virtual Environment and Install Dependencies

**Windows:**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Then install dependencies:

```bash
pip install -r requirements.txt
```

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Configure Environment Variables

Create a `.env` file in the repository root:

```env
GROQ_API_KEY=gsk_your_groq_key_here
JWT_SECRET_KEY=replace_with_a_long_random_secret
FRONTEND_ORIGIN=http://localhost:5173
ACCESS_TOKEN_EXPIRE_SECONDS=86400

# Optional
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
GROQ_MAX_RETRIES=3
GROQ_RETRY_BASE_DELAY_S=1.0
GROQ_RETRY_MAX_DELAY_S=8.0
GROQ_SYNC_CONCURRENCY=2
GROQ_ASYNC_CONCURRENCY=2
SCORING_BATCH_WORKERS=3
```

Optional frontend environment:

Create `frontend/.env.local` if your frontend should call a non-default backend URL:

```env
VITE_API_URL=http://localhost:8000
```

### 6. Run the Application

Make sure your virtual environment is activated (step 2), then start the backend:

**Windows:**

```bash
python -m uvicorn backend.main:app --reload --reload-dir backend --reload-dir ingestion --reload-dir rag --reload-dir scoring --host 0.0.0.0 --port 8000
```

**macOS / Linux:**

```bash
python3 -m uvicorn backend.main:app --reload --reload-dir backend --reload-dir ingestion --reload-dir rag --reload-dir scoring --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```

Open:

- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Optional OCR Setup

OCR is used only when PyMuPDF cannot extract a text layer from a PDF page.

### Windows

Install Tesseract, then either add it to `PATH` or set:

```env
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
```

### macOS

```bash
brew install tesseract
```

### Ubuntu / Debian

```bash
sudo apt install tesseract-ocr
```

### OCR Verification

```bash
python tests/test_ocr.py
python tests/test_ocr.py path/to/file.pdf
python tests/test_ocr.py path/to/file.pdf --no-ocr
```

## Usage Guide

### Register and Sign In

1. Start the backend and frontend.
2. Open the app in your browser.
3. Register a user account.
4. Sign in.

### Create a Project

1. Go to `Projects`.
2. Click `New Project`.
3. Enter the required project data:
   - title
   - company knowledge data
   - response RFP
4. Optionally add issuer, deadline, RFP ID, and PDF files.
5. Click `Create Project`.

### Edit Sections

Sections are edited in the workspace and saved through debounced REST autosave. There is no longer a section-collaboration WebSocket layer.

### Run Analysis

1. Open a project workspace.
2. Trigger analysis.
3. Watch live status updates in the UI.
4. Review WPS, criteria, gate results, and poison pills on the analysis pages.

### Search the Knowledge Base

Upload company files once and reuse them across projects through the Knowledge Base and Ask experiences.

## Backend API Overview

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`

### Projects

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{pid}`
- `PATCH /api/projects/{pid}`
- `DELETE /api/projects/{pid}`
- `POST /api/projects/{pid}/members`
- `DELETE /api/projects/{pid}/members/{uid}`

### Sections

- `GET /api/projects/{pid}/sections`
- `POST /api/projects/{pid}/sections`
- `PATCH /api/sections/{sid}`
- `DELETE /api/sections/{sid}`
- `POST /api/projects/{pid}/sections/generate`
- `PATCH /api/projects/{pid}/sections/reorder`

### Analysis

- `POST /api/analysis/start`
- `GET /api/analysis/stream/{job_id}`
- `GET /api/analysis/active/{project_id}`
- `GET /api/analysis/project/{pid}`
- `GET /api/analysis/result/{aid}`

### Ask

- `GET /api/ask/{pid}/history`
- `DELETE /api/ask/{pid}/history`
- `POST /api/ask/{pid}/send`

### Lookup / Knowledge Base

- `GET /api/lookup/docs`
- `POST /api/lookup/upload`
- `DELETE /api/lookup/doc/{filename}`
- `POST /api/lookup/search`

## Data Storage

Runtime data is created under `data/`:

- `data/bidintel.db`: SQLite database
- `data/uploads/rfp/`: uploaded RFP PDFs
- `data/uploads/response/`: uploaded response PDFs
- `data/company_brain/`: raw knowledge-base documents
- `data/chroma_kb/`: persisted Chroma index for company knowledge

## Environment Variable Reference

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key used by LLM calls |
| `JWT_SECRET_KEY` | Yes | Secret used to sign JWTs |
| `FRONTEND_ORIGIN` | Yes | Allowed frontend origin for CORS |
| `ACCESS_TOKEN_EXPIRE_SECONDS` | No | JWT lifetime in seconds |
| `TESSERACT_CMD` | No | Path to Tesseract binary if not available on PATH |
| `GROQ_MAX_RETRIES` | No | Maximum retries for transient Groq failures |
| `GROQ_RETRY_BASE_DELAY_S` | No | Base retry delay in seconds |
| `GROQ_RETRY_MAX_DELAY_S` | No | Maximum retry delay in seconds |
| `GROQ_SYNC_CONCURRENCY` | No | Sync Groq request concurrency limit |
| `GROQ_ASYNC_CONCURRENCY` | No | Async Groq request concurrency limit |
| `SCORING_BATCH_WORKERS` | No | Concurrent criterion scoring batch workers |
| `VITE_API_URL` | No | Frontend override for backend base URL |

## Verification and Testing

Backend tests:

```bash
python -m unittest tests.test_reliability_pass
python -m unittest tests.test_project_creation_requirements
```

Frontend build:

```bash
cd frontend
npm run build
```

If the local frontend TypeScript install is broken, use:

```bash
node scripts/repair-frontend-build.mjs
```

## Troubleshooting

### Frontend build fails because `typescript/lib/tsc.js` is missing

Run:

```bash
node scripts/repair-frontend-build.mjs
```

This removes corrupted frontend install artifacts, reinstalls npm packages, verifies TypeScript, runs the build, and cleans generated build output afterward.

### Groq rate limits

The backend now includes retry and concurrency controls, but large analyses can still be slower under tight Groq account limits. If throughput is too low:

- reduce parallel activity
- increase account quota
- tune retry and concurrency environment variables

### Scanned PDFs return poor results

Make sure Tesseract is installed and accessible. Without it, OCR fallback cannot recover text from image-only pages.

### The frontend cannot reach the backend

Check:

- backend is running on port `8000`
- frontend is running on port `5173`
- `FRONTEND_ORIGIN` is set correctly
- `VITE_API_URL` is set if you are not using the default local backend URL

## Notes for Developers

- Analysis results accumulate in SQLite and are kept as historical runs.
- Job state is persisted in SQLite — completed and errored jobs are recoverable after server restarts.
- Both RFP PDF and response PDF are required when creating a project.

## Recommended Next Improvements

- consolidate backend runtime dependencies into a single locked dependency file
- add `.env.example`
- add automated frontend tests
- add end-to-end setup scripts for Windows and macOS/Linux
- document deployment for production hosting
