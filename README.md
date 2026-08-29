# ConsulTax — AI-Powered Indian Tax Advisory Platform

> **Enterprise-grade, production-ready tax intelligence system** combining a rules-based computation engine, Retrieval-Augmented Generation (RAG) Q&A, OCR document scanning, and multi-LLM orchestration — deployable as a fully decoupled backend API and static Next.js frontend.

---

## Table of Contents

1. [Executive Overview](#1-executive-overview)
2. [Core Architecture & Innovations](#2-core-architecture--innovations)
3. [System Design](#3-system-design)
4. [Technology Stack](#4-technology-stack)
5. [API Reference](#5-api-reference)
6. [Folder Structure](#6-folder-structure)
7. [Installation & Operation](#7-installation--operation)
8. [Environment Variables](#8-environment-variables)
9. [Deployment](#9-deployment)
10. [Testing](#10-testing)
11. [Compliance & Disclaimer](#11-compliance--disclaimer)
12. [Contributing](#12-contributing)

---

## 1. Executive Overview

**ConsulTax** is a production-grade Indian tax advisory platform built for FY 2024-25, 2025-26, and 2026-27. It provides:

- **Deterministic Tax Computation** via a version-controlled, JSON-driven rules engine covering both Old and New tax regimes under the Income Tax Act, 1961.
- **AI-Powered Q&A** using Retrieval-Augmented Generation (RAG) with Cohere and Groq LLMs, grounded on curated Indian tax law documents.
- **OCR Smart Scanner** for extracting structured financial data from Form 16, salary slips, and investment proofs (PDF/image).
- **Dual-Check Validation** that cross-references OCR-extracted totals against the rules engine to surface discrepancies automatically.
- **Tax Scenario Simulator** for what-if analysis (regime switch, investment changes) without touching production sessions.
- **Session Management** with an in-memory, TTL-based, thread-safe store for multi-turn advisory conversations.
- **PDF Export** of complete tax analysis reports via ReportLab.

**Live Endpoints:**

| Service | URL |
|---|---|
| Backend API | `https://consultax.onrender.com` |
| Interactive Docs (Swagger) | `https://consultax.onrender.com/docs` |
| Frontend (Netlify) | *(configured via Netlify deployment)* |

---

## 2. Core Architecture & Innovations

### 2.1 Layered Architecture

```
+------------------------------------------------------------------+
|                         CLIENT LAYER                            |
|      Next.js 14 (Static Export) — Netlify CDN                  |
+-------------------------------+---------------------------------+
                                | HTTPS REST
+-------------------------------v---------------------------------+
|                       API GATEWAY LAYER                        |
|           FastAPI + Gunicorn + Uvicorn Workers                 |
|       CORS Middleware · Global Exception Handler               |
+-------+----------+-----------+-------------+-------------------+
        |          |           |             |
    +---v---+  +--v----+  +---v---+     +---v---+
    |  QA   |  |Analyze|  |  OCR  |     |Simulate
    |Router |  |Router |  |Router |     | Router|
    +---+---+  +--+----+  +---+---+     +---+---+
        |          |           |             |
+-------v----------v-----------v-------------v-------------------+
|                       SERVICE LAYER                            |
|  Rules Engine · RAG Pipeline · OCR Processor · Dual-Check     |
|  Session Store · PDF Generator · Explanation Engine           |
+----------------------------------------------------------------+
        |
+-------v---------------------------------------------------------+
|                    CONFIGURATION LAYER                         |
|     config/rules/v{YYYY-YY}.json — Versioned Tax Rules        |
|     config/qa_corpus/ — RAG Knowledge Documents               |
+----------------------------------------------------------------+
```

### 2.2 Key Innovations

#### Innovation 1 — Version-Controlled Rules Engine

All Indian Income Tax rules (slab rates, deductions, surcharges, rebates) are stored as **versioned JSON files** (`config/rules/v2024-25.json`, `v2025-26.json`, `v2026-27.json`). The engine evaluates any financial year independently without code changes, enabling seamless annual updates by modifying only configuration — not source code.

#### Innovation 2 — Dual-LLM Orchestration with Graceful Fallback

The QA service calls **Groq** (Llama 3.3-70B) as the primary LLM. On failure or unavailability, it automatically falls back to **Cohere** (command-r-plus). Maximum uptime is maintained without manual intervention.

#### Innovation 3 — RAG-Grounded Tax Q&A

Rather than relying on generic LLM knowledge, ConsulTax retrieves the most semantically relevant chunks from a curated Indian tax law corpus before prompting the LLM. This dramatically reduces hallucination rates for jurisdiction-specific tax advice.

#### Innovation 4 — Dual-Check Validation System

After OCR extraction, the `dual_check` module automatically computes tax figures using the rules engine and compares them against OCR-parsed values from uploaded documents. Discrepancies above a configurable tolerance threshold (default: INR 100) are surfaced as structured warnings.

#### Innovation 5 — Thread-Safe In-Memory Session Store

User sessions are managed by a thread-safe, TTL-aware in-memory store (`app/session/store.py`) backed by `threading.RLock`. Each session holds tax profiles, document state, and full conversation history — without requiring an external database for standard deployments.

#### Innovation 6 — Hard-Contracted Disclaimer Propagation

Every API response schema (`AnalyzeResponse`, `ChatResponse`, `OCRUploadResponse`, etc.) enforces the regulatory disclaimer as a **required, non-nullable Pydantic field**, ensuring it is present in 100% of API payloads by contract.

---

## 3. System Design

### 3.1 Tax Calculation Flow

```
User Input (Frontend Form)
        |
        v
FrontendProfileInput (Pydantic Validation)
        |
        v
  Rules Engine Evaluator
  +-- calculate_gross_income()
  +-- apply_standard_deduction()
  +-- evaluate_deductions()       <- Section 80C/80D/80E/24B/10-HRA
  +-- calculate_slab_tax()        <- Progressive slab tiers
  +-- apply_surcharge()
  +-- apply_health_and_education_cess()
  +-- apply_rebate_87a()          <- With marginal relief
        |
        v
  Regime Comparison (Old vs New)
        |
        v
  Recommendation Engine + AI Explanation
        |
        v
  AnalyzeResponse (JSON) -> Frontend
```

### 3.2 OCR Processing Flow

```
File Upload (PDF / Image)
        |
        v
  OCR Processor (app/ocr/)
  +-- Extract text via pypdf / Pillow
  +-- Parse key-value fields
  |   (gross income, TDS, PAN, employer name...)
  +-- Assign confidence scores per field
  +-- Build DocumentData schema
        |
        v
  Dual-Check Validator
  +-- Run Rules Engine on extracted profile
  +-- Compare OCR totals vs computed totals
  +-- Flag discrepancies > tolerance (INR 100)
        |
        v
  OCRUploadResponse (JSON) -> Frontend -> Tax Planner Sync
```

### 3.3 Conversational QA (RAG) Flow

```
User Question
        |
        v
  Session Context Retrieval
        |
        v
  RAG Retrieval Pipeline (app/qa/retrieval.py)
  +-- BM25 / TF-IDF chunk scoring on qa_corpus
        |
        v
  Prompt Construction (app/qa/answer_generator.py)
  +-- System prompt + retrieved chunks + tax profile
        |
        v
  LLM Call (Groq primary -> Cohere fallback)
        |
        v
  Response Formatting + Citation Assembly
        |
        v
  ChatResponse -> Frontend
```

### 3.4 Session Lifecycle

| Phase | Action |
|---|---|
| **Create** | POST `/api/session` returns `session_id` (UUID) |
| **Active** | All subsequent calls pass `session_id`; TTL reset on each touch |
| **Expire** | After `SESSION_TTL_SECONDS` (default: 1800s) of inactivity |
| **Cleanup** | Expired sessions are lazily evicted on next access |

### 3.5 Deployment Architecture

```
+------------------+          +----------------------+
|   Netlify CDN    |          |  Render.com (Docker) |
|                  |  HTTPS   |                      |
|  Next.js Static  |<-------->|  FastAPI + Gunicorn  |
|  (out/ folder)   |          |  2 Uvicorn Workers   |
+------------------+          +----------------------+
```

---

## 4. Technology Stack

### Backend

| Category | Technology | Version |
|---|---|---|
| Framework | FastAPI | `>=0.110.0` |
| ASGI Server | Uvicorn + Gunicorn | `>=0.28.0` / `>=21.2.0` |
| Data Validation | Pydantic v2 | `>=2.6.0` |
| LLM — Primary | Groq (Llama 3.3-70B) | `>=0.4.0` |
| LLM — Fallback | Cohere (command-r-plus) | `>=5.0.0` |
| LLM — Optional | OpenAI, Anthropic | `>=1.0.0` / `>=0.18.0` |
| OCR / PDF Parsing | pypdf | `>=4.0.0` |
| PDF Export | ReportLab | `>=4.0.0` |
| HTTP Client | httpx | `>=0.27.0` |
| Templating | Jinja2 | `>=3.1.0` |
| Testing | pytest + pytest-asyncio | `>=8.0.0` |
| Runtime | Python | `3.12` |
| Container | Docker | `python:3.12-slim` |

### Frontend

| Category | Technology |
|---|---|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| Styling | Vanilla CSS (custom design system) |
| Build Output | Static Export (`out/`) |
| Hosting | Netlify |
| API Communication | Fetch API (REST) |

### Infrastructure

| Component | Platform |
|---|---|
| Backend Hosting | Render.com (Docker Web Service) |
| Frontend Hosting | Netlify (CDN, Static) |
| CI/CD | Git push triggers Render auto-deploy and Netlify build |
| Configuration | Environment variables (`.env` / Render / Netlify dashboards) |

---

## 5. API Reference

All routes are prefixed with `/api`. Full interactive documentation is at `https://consultax.onrender.com/docs`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check — returns app name, environment, status |
| `POST` | `/api/analyze` | Full tax analysis: Old + New regime comparison, deductions, recommendations |
| `POST` | `/api/qa` | Conversational tax Q&A with RAG grounding |
| `POST` | `/api/ocr/upload` | Upload Form 16 or salary slip; returns extracted fields + confidence scores |
| `POST` | `/api/form16/summarize` | AI-generated plain-language summary of Form 16 |
| `POST` | `/api/simulate` | What-if tax scenario simulation |
| `POST` | `/api/session` | Create a new advisory session |
| `GET` | `/api/session/{session_id}` | Retrieve session state |
| `DELETE` | `/api/session/{session_id}` | Terminate and clear a session |
| `POST` | `/api/export/pdf` | Generate and download a tax analysis PDF report |
| `GET` | `/api/rules/diff` | Compare tax rules between two financial years |
| `GET` | `/api/sample-documents` | Retrieve sample Form 16 / payslip documents for testing |

### Example: Tax Analysis Request

```bash
curl -X POST https://consultax.onrender.com/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "name": "Rahul Sharma",
      "financial_year": "2024-25",
      "age": 32,
      "employment_income": 1500000,
      "provident_fund": 46800,
      "elss_investment": 50000,
      "health_insurance_self_family": 25000,
      "home_loan_interest": 200000,
      "tax_paid": 120000,
      "regime": "new"
    },
    "include_recommendations": true
  }'
```

### Example: OCR Upload Request

```bash
curl -X POST https://consultax.onrender.com/api/ocr/upload \
  -F "file=@form16.pdf" \
  -F "document_type=form16"
```

---

## 6. Folder Structure

```
consulTax/
|-- app/                          # Core backend application (FastAPI)
|   |-- main.py                   # Entrypoint: router registration, CORS, global exception handler
|   |-- config.py                 # Centralized settings loader (dotenv -> Settings class)
|   |-- api/                      # HTTP route handlers (thin controllers only)
|   |   |-- analyze.py            # POST /api/analyze — tax computation endpoint
|   |   |-- qa.py                 # POST /api/qa — RAG-powered conversational Q&A
|   |   |-- ocr.py                # POST /api/ocr/upload — document OCR processing
|   |   |-- form16.py             # POST /api/form16/summarize — Form 16 AI explainer
|   |   |-- simulate.py           # POST /api/simulate — what-if tax scenario simulator
|   |   |-- session.py            # CRUD /api/session — session lifecycle management
|   |   |-- export.py             # POST /api/export/pdf — PDF report generation
|   |   |-- rules_diff.py         # GET /api/rules/diff — cross-year rule comparison
|   |   +-- sample_documents.py   # GET /api/sample-documents — test document fixtures
|   |-- schemas/                  # Pydantic data models
|   |   |-- api.py                # Request/Response schemas (AnalyzeRequest, ChatRequest, OCRUploadResponse)
|   |   +-- domain.py             # Core domain models (TaxProfile, IncomeDetails, DeductionDetails)
|   |-- rules_engine/             # Deterministic tax calculation engine
|   |   |-- evaluator.py          # Slabs, surcharge, cess, rebate 87A, deductions computation
|   |   +-- loader.py             # Loads versioned JSON rule files from config/rules/
|   |-- qa/                       # Conversational Q&A and RAG pipeline
|   |   |-- answer_generator.py   # LLM prompt construction + Groq/Cohere API calls
|   |   +-- retrieval.py          # BM25/TF-IDF retrieval over config/qa_corpus/
|   |-- ocr/                      # OCR document processing
|   |   +-- processor.py          # PDF/image text extraction, field parsing, confidence scoring
|   |-- dual_check/               # OCR vs rules-engine cross-validation
|   |   +-- validator.py          # validate_ocr_vs_computed() with tolerance thresholds
|   |-- session/                  # User session management
|   |   +-- store.py              # Thread-safe in-memory TTL store (SessionStore, SessionData)
|   |-- simulator/                # What-if tax scenario engine
|   |   +-- engine.py             # Applies profile adjustments and re-evaluates tax
|   |-- explanation/              # AI-generated human-readable explanation layer
|   |   +-- explainer.py          # Formats rules engine output into plain-language summaries
|   |-- pdf/                      # PDF report generation
|   |   +-- generator.py          # ReportLab-based tax analysis report builder
|   |-- document/                 # Document ingestion utilities
|   |-- audit/                    # Audit trail recording
|   |-- diff/                     # Rule diff logic
|   |-- middleware/               # Custom middleware (request ID, rate limiting stubs)
|   |-- observability/            # Logging, Sentry integration stubs
|   +-- services/                 # Shared service utilities
|
|-- config/                       # External, version-controlled configuration data
|   |-- rules/                    # Tax rule definitions (JSON, one file per financial year)
|   |   |-- v2024-25.json         # FY 2024-25: slabs, deductions, surcharges, rebates
|   |   |-- v2025-26.json         # FY 2025-26: updated rule set
|   |   +-- v2026-27.json         # FY 2026-27: updated rule set
|   +-- qa_corpus/                # Plain-text Indian tax law documents for RAG retrieval
|
|-- docs/                         # Project documentation
|
|-- frontend/                     # Next.js 14 frontend application
|   |-- app/
|   |   |-- page.tsx              # Main page: Tax Planner, Chat, OCR Scanner, Simulator
|   |   |-- layout.tsx            # Root layout with metadata and font configuration
|   |   +-- styles.css            # Full custom CSS design system
|   |-- public/
|   |   +-- _redirects            # Netlify SPA routing rules
|   |-- next.config.mjs           # Next.js config (static export, unoptimized images)
|   +-- package.json              # Frontend npm dependencies
|
|-- tests/                        # Automated test suite
|   |-- test_analyze.py           # Integration tests for /api/analyze
|   |-- test_qa.py                # Tests for conversational Q&A
|   |-- test_ocr.py               # OCR processing tests
|   +-- test_rules_engine.py      # Unit tests for rules evaluator
|
|-- scripts/                      # Developer utility scripts
|
|-- Dockerfile                    # Docker image definition (python:3.12-slim)
|-- render.yaml                   # Render.com deployment configuration
|-- netlify.toml                  # Netlify build and redirect configuration
|-- requirements.txt              # Python dependencies with pinned version ranges
|-- pyproject.toml                # Project metadata and linting configuration
|-- pytest.ini                    # Pytest configuration
|-- .env.example                  # Template for required environment variables
+-- README.md                     # This document
```

---

## 7. Installation & Operation

### Prerequisites

| Requirement | Version |
|---|---|
| Python | `3.12+` |
| Node.js | `18+` |
| npm | `9+` |
| Git | Latest |

---

### 7.1 Backend Setup

**Step 1 — Clone the Repository**

```bash
git clone https://github.com/<your-org>/consulTax.git
cd consulTax
```

**Step 2 — Create and Activate Virtual Environment**

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

**Step 3 — Install Python Dependencies**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Step 4 — Configure Environment Variables**

```bash
cp .env.example .env
# Edit .env and add your API keys (see Section 8)
```

**Step 5 — Run the Development Server**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Available at:
- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

**Step 6 — Production Server (Gunicorn)**

```bash
gunicorn app.main:app \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker
```

---

### 7.2 Frontend Setup

**Step 1 — Navigate to Frontend Directory**

```bash
cd frontend
```

**Step 2 — Install Node Dependencies**

```bash
npm install
```

**Step 3 — Configure Backend URL**

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

For production, use:

```env
NEXT_PUBLIC_API_BASE_URL=https://consultax.onrender.com
```

**Step 4 — Start Development Server**

```bash
npm run dev
# Available at http://localhost:3000
```

**Step 5 — Build Static Export (Production)**

```bash
npm run build
# Output generated in frontend/out/
```

---

### 7.3 Docker Setup

**Build the Image**

```bash
docker build -t consultax:latest .
```

**Run the Container**

```bash
docker run -p 8000:8000 \
  -e GROQ_API_KEY=your_key_here \
  -e COHERE_API_KEY=your_key_here \
  consultax:latest
```

---

## 8. Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_NAME` | No | `Tax Assistant` | Display name for the application |
| `ENVIRONMENT` | No | `development` | Runtime environment (`development` / `production`) |
| `DEBUG` | No | `false` | Enable verbose error output in responses |
| `GROQ_API_KEY` | **Yes** | — | Groq API key for Llama 3.3-70B (primary LLM) |
| `COHERE_API_KEY` | **Yes** | — | Cohere API key for command-r-plus (fallback LLM) |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model identifier |
| `COHERE_MODEL` | No | `command-r-plus` | Cohere model identifier |
| `SESSION_TTL_SECONDS` | No | `1800` | User session timeout in seconds |
| `SUPABASE_URL` | No | — | Supabase project URL (optional persistent storage) |
| `SUPABASE_ANON_KEY` | No | — | Supabase anonymous API key |
| `SENTRY_DSN` | No | — | Sentry DSN for error tracking (optional) |

**Example `.env`**

```env
APP_NAME=ConsulTax
ENVIRONMENT=development
DEBUG=false

GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
COHERE_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

GROQ_MODEL=llama-3.3-70b-versatile
COHERE_MODEL=command-r-plus

SESSION_TTL_SECONDS=1800
```

---

## 9. Deployment

### 9.1 Backend — Render.com

The repository includes `render.yaml` for zero-configuration deployments:

1. Connect your GitHub repository to [Render.com](https://render.com).
2. Render auto-detects `render.yaml` and creates the Docker web service.
3. Add `GROQ_API_KEY` and `COHERE_API_KEY` as secret environment variables in the Render dashboard.
4. Every push to `main` triggers an automatic Docker rebuild and deploy.

**Live URL:** `https://consultax.onrender.com`

### 9.2 Frontend — Netlify

The repository includes `netlify.toml` for zero-configuration builds:

```toml
[build]
  base    = "frontend"
  command = "npm run build"
  publish = "out"

[[redirects]]
  from   = "/*"
  to     = "/index.html"
  status = 200
```

**Deploy Steps:**

1. Connect your GitHub repository to [Netlify](https://netlify.com).
2. Netlify reads `netlify.toml` automatically.
3. Set `NEXT_PUBLIC_API_BASE_URL=https://consultax.onrender.com` in Netlify environment settings.
4. Every push to `main` triggers an automatic build and CDN deployment.

---

## 10. Testing

**Run all tests:**

```bash
pytest
```

**Run with verbose output:**

```bash
pytest -v
```

**Run a specific module:**

```bash
pytest tests/test_rules_engine.py -v
pytest tests/test_analyze.py -v
pytest tests/test_ocr.py -v
```

**Run with coverage report:**

```bash
pytest --cov=app --cov-report=term-missing
```

**Live interactive testing:**
Use the Swagger UI at `https://consultax.onrender.com/docs` to test all endpoints without any local setup.

---

## 11. Compliance & Disclaimer

> **ConsulTax is an AI-powered advisory tool and is NOT a certified tax authority, Chartered Accountant, or registered tax professional.**
>
> - All computations are based on information provided by the user and the rules configured in the system.
> - Results may not account for all individual circumstances, recent legislative amendments, or judicial interpretations.
> - No real financial data is collected or stored beyond the active session TTL.
> - This tool is intended for informational and educational purposes only.
> - **Always consult a qualified Chartered Accountant (CA) or registered tax professional before making any filing, investment, or compliance decisions.**
>
> This disclaimer is contractually enforced at the Pydantic schema level and is a required field in every API response payload.

---

## 12. Contributing

1. **Fork** the repository and create a feature branch: `git checkout -b feature/your-feature-name`
2. **Follow** existing code conventions — type annotations, docstrings, and Pydantic schemas are required for all new modules.
3. **Write tests** for any new routes, engine logic, or utilities.
4. **Run the full test suite** before submitting: `pytest -v`
5. **Submit a Pull Request** with a clear description of the change and its rationale.

### Code Standards

| Standard | Requirement |
|---|---|
| Type Hints | Mandatory on all function signatures |
| Docstrings | Required for all modules, classes, and public functions |
| Pydantic Schemas | Required for all API request and response models |
| Disclaimer Field | Must be present in all new API response schemas |
| Test Coverage | Required for all new API routes and engine logic |

---

*ConsulTax — Built with precision for Indian tax compliance.*
*Backend on Render · Frontend on Netlify · Powered by Groq & Cohere*
