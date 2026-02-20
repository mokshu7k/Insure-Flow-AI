# InsureFlow AI - Backend

**Full-stack insurance claim intelligence platform** built for TechFiesta 2026.
FastAPI (Python 3.12) + Next.js 16 frontend + GCP Cloud SQL (PostgreSQL).

---

## What it does

| Feature | Detail |
|---|---|
| **Claim wizard** | 4-step guided flow: pick type, upload docs, review OCR output, confirm & submit |
| **Document intelligence** | LangExtract + Gemini 2.5 Flash extracts structured fields from PDFs/images |
| **6-layer fraud engine** | Deterministic -> Statistical -> Behavioural -> Network -> ML -> AI narrative |
| **Customer dashboard** | Approval rate, avg claim size, recovery rate, status breakdown |
| **Admin dashboard** | Portfolio overview, fraud distribution, pending manual reviews |
| **AI Claims Assistant** | LangGraph agent - full-page /chat + floating bubble on every claims page |
| **QR cashless auth** | HMAC-SHA256 signed single-use tokens for provider payment authorisation |
| **RBAC** | CUSTOMER / CLAIM_ADJUSTER / INSURER_ADMIN / AUDITOR / PROVIDER |
| **Compliance** | DPDP consent tracking, immutable audit log, human-in-the-loop enforcement |

---

## Stack

\Backend   FastAPI 0.115 + SQLAlchemy 2 (async) + asyncpg + Alembic
AI/ML     LangGraph + LangExtract + Gemini 2.5 Flash + GCP TTS/STT
DB        GCP Cloud SQL PostgreSQL 16
Frontend  Next.js 16 (App Router) + TypeScript
Auth      JWT (Bearer + HttpOnly cookie) + bcrypt + Fernet encryption
\
---

## Project layout

\insureflow-backend/
app/
  ai_agents/        LangGraph agent + GCP voice
  api/              FastAPI routers (claims, documents, agent, auth, dashboard)
  compliance/       DPDP consent, data retention, access monitoring
  core/             RBAC, security, constants, exceptions
  db/               Async session
  models/           SQLAlchemy ORM models
  ocr/              LangExtract extraction pipeline
  schemas/          Pydantic request/response models
  services/         Business logic (claims, documents, fraud, dashboard)
  main.py           App factory, CORS, router registration
frontend/           Next.js 16 app
  src/
    app/            Pages (dashboard, claims, claims/new, chat, adjuster)
    components/     Layout, UI, AuthGuard, ClaimAssistantBubble
    services/       API clients (claimService, documentService, agentService)
    store/          Zustand stores (auth, claim)
    types/          Shared TypeScript interfaces
migrations/         Alembic migrations
scripts/
  seed_data.py      Idempotent seed - 4 users, 11 claims, 1 settlement
  train_fraud_model.py
requirements.txt
\
---

## Quick start

### 1 - Prerequisites
- Python 3.12, Node 20+
- PostgreSQL (or use the GCP Cloud SQL instance - credentials in .env)

### 2 - Backend

\\ash
cd insureflow-backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env           # fill in secrets
python -m alembic upgrade head
python scripts/seed_data.py    # optional test data
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
\
API docs: http://localhost:8000/docs

### 3 - Frontend

\\ash
cd frontend
npm install
npm run dev
\
App: http://localhost:3000

---

## Environment variables (.env)

\\ini
DATABASE_URL=postgresql+asyncpg://postgres:<password>@<host>/insureflow
SECRET_KEY=<secrets.token_urlsafe(32)>
REFRESH_SECRET_KEY=<secrets.token_urlsafe(32)>
ENCRYPTION_KEY=<Fernet.generate_key().decode()>
QR_SECRET_KEY=<secrets.token_urlsafe(32)>
GCP_API_KEY=<your-gemini-api-key>
GCP_PROJECT_ID=<your-gcp-project>
ENCRYPTED_STORAGE_DIR=./storage
MAX_UPLOAD_SIZE=10485760
\
---

## Test credentials (after seed)

| Email | Password | Role |
|---|---|---|
| customer1@test.ai | Test1234! | CUSTOMER |
| customer2@test.ai | Test1234! | CUSTOMER |
| admin@insureflow.ai | Admin@123 | INSURER_ADMIN |
| adjuster@insureflow.ai | Admin@123 | CLAIM_ADJUSTER |

Policy numbers for wizard: POL-HEALTH-TEST-001, POL-MOTOR-TEST-001, POL-REIMB-TEST-001

---

## API overview

\POST  /api/auth/register
POST  /api/auth/login
POST  /api/auth/refresh

GET   /api/claims                 list (paginated, filter by status)
POST  /api/claims                 create
GET   /api/claims/{id}
PATCH /api/claims/{id}            update amount/description (CUSTOMER, SUBMITTED)
PATCH /api/claims/{id}/status     adjuster status transitions

POST  /api/documents              upload + OCR extraction
GET   /api/documents?claim_id=    list documents for a claim

GET   /api/dashboard/overview     admin portfolio metrics
GET   /api/dashboard/customer     customer personal metrics

POST  /api/agent/sessions
POST  /api/agent/sessions/{id}/message
POST  /api/agent/sessions/{id}/voice

POST  /api/qr/authorize
POST  /api/qr/validate
POST  /api/settlements
\
---

## Frontend pages

| Route | Who | Description |
|---|---|---|
| /login | all | Login / register |
| /dashboard | all | Customer metrics or Admin portfolio (auto-switches by role) |
| /claims | all | Paginated claim list with status filter |
| /claims/new | CUSTOMER | 4-step guided claim wizard |
| /claims/[id] | all | Claim detail |
| /chat | all | Full-page AI Claims Assistant |
| /adjuster | ADJUSTER/ADMIN | Review queue + status transitions |
| /compliance | ADMIN/AUDITOR | Consent & audit log viewer |
| /profile | all | Account info |

A floating Assistant bubble appears on all /claims/** pages.

---

## Fraud detection layers

\Layer 1  Deterministic rules   amount thresholds, duplicate detection, blacklists
Layer 2  Statistical anomaly   z-score on amount/frequency distributions
Layer 3  Behavioural flags     velocity, submission timing, device patterns
Layer 4  Network analysis      provider clustering, shared attributes
Layer 5  ML classifier         IsolationForest / RandomForest trained model
Layer 6  Gemini narrative      human-readable explanation of combined signals
\
Final score 0-1: LOW / MEDIUM / HIGH / CRITICAL.
AI can flag; only a human adjuster approves or rejects.
