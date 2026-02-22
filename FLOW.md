# InsureFlow AI — Complete System Flow

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Roles & Access Control](#roles--access-control)
3. [Tech Stack](#tech-stack)
4. [Authentication Flow](#authentication-flow)
5. [Claim Lifecycle (Core Flow)](#claim-lifecycle-core-flow)
6. [Document Upload & OCR Pipeline](#document-upload--ocr-pipeline)
7. [Fraud Detection Agent (LangGraph 6-Node)](#fraud-detection-agent-langgraph-6-node)
8. [Cashless Claims Flow](#cashless-claims-flow)
9. [Settlement Flow](#settlement-flow)
10. [AI Agents Summary](#ai-agents-summary)
11. [Audit Agent & Sweep System](#audit-agent--sweep-system)
12. [Compliance & Consent](#compliance--consent)
13. [Dashboard](#dashboard)
14. [Frontend Pages & Navigation](#frontend-pages--navigation)
15. [Database Models](#database-models)
16. [API Routes Reference](#api-routes-reference)
17. [Seed Credentials](#seed-credentials)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Next.js 14 Frontend  (localhost:3000)                          │
│  React + Zustand + Tailwind                                     │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP (REST JSON)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Backend  (localhost:8000)                              │
│  app/main.py → /api/* (13 router modules)                       │
│  Async (asyncpg + SQLAlchemy 2.x)                               │
└──────┬──────────────────────────────────────────────┬──────────┘
       │                                              │
       ▼                                              ▼
┌──────────────┐                          ┌──────────────────────┐
│  PostgreSQL  │                          │  Google Gemini 2.5   │
│  (asyncpg)   │                          │  Flash (LangGraph)   │
└──────────────┘                          └──────────────────────┘
```

All files uploaded by users are **Fernet-encrypted** before writing to disk (`storage/encrypted/`). All state changes are logged to the immutable `audit_logs` table.

---

## Roles & Access Control

| Role | Description | Key Permissions |
|---|---|---|
| `CUSTOMER` | Policyholder | File claims, upload docs, track status, chat with AI |
| `PROVIDER` | Hospital / Garage | View network claims, generate cashless QR, accept authorizations |
| `CLAIM_ADJUSTER` | Internal reviewer | Review claims, run fraud analysis, chat with adjuster agent, update status |
| `INSURER_ADMIN` | Super admin | Everything + settlement initiation, QR generation, compliance views, trigger audit sweeps |
| `AUDITOR` | Compliance officer | Read-only: audit sweep runs, findings, compliance trail, dashboard |

RBAC is enforced via `require_role()` / `require_any_role()` FastAPI dependency factories in `app/core/rbac.py`.

---

## Tech Stack

**Backend**
- Python 3.11 + FastAPI (async)
- SQLAlchemy 2.x + asyncpg (PostgreSQL)
- Alembic (migrations)
- LangChain + LangGraph (AI agent pipelines)
- Google Gemini 2.5 Flash (LLM for OCR, fraud, adjuster, audit, customer chat)
- GCP Cloud Speech-to-Text + TTS (voice in customer chat)
- Fernet (document encryption at rest)
- JWT (access + refresh tokens, HttpOnly cookies)
- Prometheus metrics endpoint at `/metrics`

**Frontend**
- Next.js 14 (App Router, `"use client"`)
- TypeScript
- Zustand (auth state)
- Custom CSS variables (dark/light design system)
- Lucide React icons

---

## Authentication Flow

```
POST /api/auth/register  →  creates user, hashes password (bcrypt)
POST /api/auth/login     →  verifies password, issues:
                              - access_token  (JWT, 15 min, HttpOnly cookie)
                              - refresh_token (JWT, 7 days, HttpOnly cookie)
POST /api/auth/refresh   →  rotates tokens using refresh_token
POST /api/auth/logout    →  clears cookies
GET  /api/auth/me        →  returns current user from JWT
```

**Frontend guard**: `AuthGuard` component wraps all protected pages.  
- `requireAdmin` prop → blocks CUSTOMER and PROVIDER.  
- `useIsAuditor()`, `useIsAdmin()`, `useIsAdjuster()` hooks read Zustand store.

---

## Claim Lifecycle (Core Flow)

```
CUSTOMER files claim
        │
        ▼
POST /api/claims
  • Auto-resolves active policy by claim_type (no manual policy number)
  • Validates claim_amount ≤ sum_insured
  • Creates Claim (status = SUBMITTED)
  • Logs to audit_logs
        │
        ▼
CUSTOMER uploads documents
POST /api/claim-documents
  • Optional inline OCR preview (no DB write)
  • Gemini template-aware extraction runs in background
  • Document encrypted and saved to disk
  • ClaimDocument row created
        │
        ▼
CLAIM_ADJUSTER / INSURER_ADMIN reviews claim
PATCH /api/claims/{id}/status
  • Status machine enforced (only valid transitions allowed)
  • Optional adjuster_notes

Valid status transitions:
  SUBMITTED → UNDER_REVIEW → APPROVED → SETTLED
                           → REJECTED
                           → MANUAL_REVIEW_REQUIRED → APPROVED/REJECTED
  SUBMITTED → PRE_AUTHORIZED (cashless path) → SETTLED / REJECTED
        │
        ▼
POST /api/fraud/analyze/{claim_id}          ← manual trigger
POST /api/fraud/agent-analyze/{id}/{doc_id} ← LangGraph 6-node agent
  • Stores FraudAssessment with score 0–1 and risk_level
        │
        ▼
POST /api/settlements/{claim_id}  (INSURER_ADMIN only)
  • Creates Settlement record
  • Claim moves to SETTLED
```

---

## Document Upload & OCR Pipeline

```
Frontend (upload wizard)
  │
  ├─ Step 1: POST /api/claim-documents/inline-ocr
  │    • No DB write
  │    • Gemini: relevance check + field extraction in one call
  │    • Returns: is_relevant, extracted_fields, confidence, missing_fields
  │    • User can review/edit before submitting
  │
  └─ Step 2: POST /api/claim-documents  (with precomputed_data from Step 1)
       • Creates ClaimDocument (status = PENDING)
       • File encrypted with Fernet → saved to storage/encrypted/
       • Background task runs full pipeline:
           1. Fetch DocumentRequirement (template) for this claim_type + doc_type
           2. Build extraction prompt via extraction_service
           3. Gemini multimodal extraction
           4. Wrong-document detection (gatekeeper)
           5. Validate required fields + template validation_rules
           6. promote_fields() → write promoted columns (dates, amounts, names)
           7. DocumentGatekeeper authenticity check
           8. Cross-document consistency checks against other docs on same claim
           9. Persist results → ClaimDocument.status = COMPLETED / FAILED
```

**Document types supported**: Aadhaar, PAN, Hospital Bill, Discharge Summary, FIR, Prescription, Repair Estimate, Death Certificate, and more — all defined as `DocumentRequirement` rows with `extraction_template` and `validation_rules` JSON.

---

## Fraud Detection Agent (LangGraph 6-Node)

Triggered by `POST /api/fraud/agent-analyze/{claim_id}/{document_id}`.

```
START
  ├──▶ Node 1: extraction_integrity_node
  │      • Checks extraction confidence, required field completeness
  │      • Flags: MISSING_REQUIRED_FIELD, LOW_CONFIDENCE
  │
  ├──▶ Node 2: cross_document_consistency_node  (after Node 1)
  │      • Compares fields across all docs on the claim
  │      • Flags: NAME_MISMATCH, DOB_MISMATCH, DATE_INCONSISTENCY
  │
  ├──▶ Node 3: document_intelligence_node  (after Node 2)
  │      • Policy date checks (CLAIM_BEFORE_POLICY, VERY_EARLY_CLAIM)
  │      • Prior fraud history lookup
  │      • Flags: PRIOR_FRAUD_HISTORY, CLAIM_BEFORE_POLICY
  │
  ├──▶ Node 4: image_forensics_node  (PARALLEL — no LLM)
  │      • Pixel-level analysis (copy-move detection, perceptual hash duplicates)
  │      • Flags: COPY_MOVE_DETECTED, PHASH_DUPLICATE
  │
  ├──▶ Node 5: document_content_fraud_node  (after Node 3, Gemini)
  │      • Gemini reads document image + extracted data
  │      • Looks for bill inflation, phantom procedures, forged seals
  │      • Flags: CONTENT_CRITICAL, ARITHMETIC_MISMATCH
  │
  └──▶ Node 6: behavioral_risk_node  (PARALLEL — no LLM)
         • Claim frequency, amount patterns, provider patterns
         • Flags: HIGH_CLAIM_FREQUENCY, AMOUNT_SPIKE

All outputs → aggregator_node (Gemini)
  • Receives all node scores + flags
  • Issues final_score (0–1), risk_level (MINIMAL/LOW/MEDIUM/HIGH/VERY_HIGH)
  • Writes risk_explanation (human-readable) + critical_signals
  • Triggers MANUAL_REVIEW_REQUIRED if certain instant-review patterns present:
      COPY_MOVE_DETECTED, PHASH_DUPLICATE, CLAIM_BEFORE_POLICY,
      VERY_EARLY_CLAIM, PRIOR_FRAUD_HISTORY, ARITHMETIC_MISMATCH, CONTENT_CRITICAL

→ Saved to FraudAssessment table
→ UserFraudProfile updated (running risk stats)
```

---

## Cashless Claims Flow

Cashless = hospital directly billed, no reimbursement. Uses QR codes for authorization.

```
CUSTOMER
  POST /api/claims  (claim_type = CASHLESS, provider_id = hospital UUID)
    → Claim created, status = SUBMITTED

PROVIDER (Hospital)
  GET /api/cashless/network-claims
    → Sees all CASHLESS claims assigned to them

  POST /api/cashless/generate-qr
    → Creates QRToken (30 min expiry, HMAC-signed)
    → Returns QR image (base64 PNG)

CUSTOMER
  GET /api/cashless/scan/{token}
    → Validates token, returns estimate details

  POST /api/cashless/accept
    → Customer approves estimate
    → Claim moves to PRE_AUTHORIZED

INSURER_ADMIN
  POST /api/cashless/authorize
    → Reviews and authorizes cashless request

PROVIDER — discharge
  POST /api/settlements/{claim_id}
    → Initiates settlement, Claim → SETTLED
```

---

## Settlement Flow

```
Claim must be in APPROVED or PRE_AUTHORIZED status

POST /api/settlements/{claim_id}  (INSURER_ADMIN only)
  → Creates Settlement (status = COMPLETED, settlement_reference generated)
  → Claim.status = SETTLED
  → Logged to audit_logs

Legacy QR settlement (reimbursement):
POST /api/qr/generate/{claim_id}  → issues payment QR token
POST /api/qr/verify               → validates token
```

---

## AI Agents Summary

| Agent | Location | Trigger | LLM | Purpose |
|---|---|---|---|---|
| **Customer Chat** | `ai_agents/agent/` | `POST /api/agent/message` | Gemini 2.5 Flash | 3-node: supervisor → data_node (8 DB tools) → synthesizer. Answers customer queries about their claims. Supports voice (GCP STT/TTS). Sliding window memory persisted in `agent_sessions` table |
| **Fraud Detection** | `ai_agents/fraud/` | `POST /api/fraud/agent-analyze` | Gemini 2.5 Flash | 6-node LangGraph. Sequential extraction+consistency+intelligence+content-fraud nodes + 2 parallel (image forensics + behavioural). Final Gemini aggregation → FraudAssessment |
| **Adjuster Agent** | `ai_agents/adjuster/` | `POST /api/adjuster/chat` `POST /api/adjuster/report/{id}` | Gemini 2.5 Flash | Single Gemini node with 6 read-only DB tools. CLAIM_ADJUSTER / INSURER_ADMIN only. Can generate full PDF-ready claim reports |
| **Audit Sweeper** | `ai_agents/auditor/` | `scripts/run_audit.py` `POST /api/audit/trigger` | Gemini 2.5 Flash | 3-node: data_collection (10 SQL tools, parallel) → analysis (Gemini classifies findings) → persistence (AuditRun + AuditFinding rows, immutable) |

---

## Audit Agent & Sweep System

### Running a sweep
```bash
# Manual
python -m scripts.run_audit

# Via API (AUDITOR or INSURER_ADMIN)
POST /api/audit/trigger  →  returns run_id immediately (BackgroundTask)

# Cron (recommended)
0 2 * * *  cd /app && python -m scripts.run_audit
```

### The 3-node pipeline
```
data_collection_node
  Runs 10 SQL signal detectors concurrently:
  1.  adjuster_provider_collusion  — adjuster approval rate >2x for specific provider
  2.  provider_overbilling         — avg claim spike >2.5x 30-day baseline
  3.  underpayment_pattern         — adjuster systematically cuts approved amounts
  4.  high_fraud_score_approved    — fraud_score >0.70 on APPROVED/SETTLED claim
  5.  abnormal_settlement_speed    — SUBMITTED → SETTLED in <24 hours
  6.  settlement_discrepancy       — settlement.amount vs claim.approved_amount >5%
  7.  claim_amount_gap             — >40% cut with no adjuster notes
  8.  provider_cluster_activity    — 3+ providers, identical procedures, 7 days
  9.  user_claim_surge             — >4 claims in 30 days, no fraud flag
  10. document_integrity           — repeated re-submissions / FAIL results
        │
        ▼
analysis_node (Gemini 2.5 Flash)
  Gemini receives all raw signals → produces structured JSON array of findings:
  {finding_type, severity, entity_type, entity_id, description,
   gemini_narrative, recommended_action, evidence}
  + SUMMARY: executive paragraph
        │
        ▼
persistence_node
  Saves AuditRun + AuditFinding rows (append-only, no UPDATE/DELETE ever)
```

### Reading results (AUDITOR / INSURER_ADMIN)
```
GET /api/audit/runs                    — list all sweeps
GET /api/audit/runs/{run_id}           — run + all findings inlined
GET /api/audit/findings                — findings with severity/type/entity filters
GET /api/audit/findings/{finding_id}   — single finding, full evidence
```

**Frontend**: `/audit` page (login as AUDITOR to see it in nav).

---

## Compliance & Consent

```
POST /api/compliance/consent     — record explicit DPDP consent (IP logged)
GET  /api/compliance/consent     — check if user has valid consent
GET  /api/compliance/audit       — immutable audit trail (own records for CX,
                                   all records for ADMIN/AUDITOR)
POST /api/compliance/deletion    — DPDP right-to-erasure request
```

Every mutable operation (claim creation, status change, login, document upload, fraud analysis, settlement) writes an immutable row to `audit_logs` via `audit_service.log_action()`.

---

## Dashboard

`GET /api/dashboard/*` — role-scoped metrics:

| Endpoint | Access | Returns |
|---|---|---|
| `/dashboard/overview` | ADMIN / ADJUSTER / AUDITOR | Claim counts, approval rate, fraud blocked, settlement totals |
| `/dashboard/fraud-distribution` | ADMIN / ADJUSTER / AUDITOR | Fraud score histogram |
| `/dashboard/sla` | ADMIN / ADJUSTER / AUDITOR | SLA performance by status bucket |
| `/dashboard/compliance-summary` | ADMIN / ADJUSTER / AUDITOR | Consent rate, deletion requests, audit log count |
| `/dashboard/customer` | Any role | Scoped to own claims — personal metrics |

---

## Frontend Pages & Navigation

| Route | Visible To | Description |
|---|---|---|
| `/` | Public | Landing page with role cards and login CTAs |
| `/login` | Public | Email/password login |
| `/register` | Public | Role selection + registration |
| `/dashboard` | All authenticated | Role-scoped metrics cards |
| `/claims` | All authenticated | List claims; CUSTOMER sees own, admins see all |
| `/claims/[id]` | All authenticated | Claim detail: docs, fraud score, audit trail, status actions |
| `/cashless` | CUSTOMER + PROVIDER + ADMIN | QR generation (provider), scan+accept (customer) |
| `/adjuster` | ADMIN / ADJUSTER | Chat with adjuster AI; generate claim report |
| `/audit` | AUDITOR / ADMIN | Browse audit sweep runs; drill into findings; trigger new sweep |
| `/compliance` | ADMIN / AUDITOR | Immutable audit trail log browser |
| `/chat` | All authenticated | Customer AI chat (text + voice) |
| `/profile` | All authenticated | Account details, role badge, permission list |

**LeftRail nav visibility rules:**
- `alwaysShow` → everyone (Dashboard, Claims, Cashless, Assistant, Profile)
- `adminOnly` → INSURER_ADMIN only (Adjuster)
- `auditorRole` → INSURER_ADMIN + AUDITOR (Audit)
- `complianceRole` → INSURER_ADMIN + AUDITOR (Compliance)

---

## Database Models

| Model | Table | Purpose |
|---|---|---|
| `User` | `users` | All user accounts with role |
| `Insurer` | `insurers` | Tenant (insurer company) |
| `PolicyType` | `policy_types` | Health/Motor/Life/Travel templates |
| `DocumentRequirement` | `document_requirements` | Required docs per policy_type + extraction templates |
| `Policy` | `policies` | User's active insurance policies |
| `PolicyNominee` | `policy_nominees` | Policy nominees |
| `Claim` | `claims` | Core claim record |
| `ClaimStatusHistory` | `claim_status_history` | Every status transition (who, when, notes) |
| `ClaimDocument` | `claim_documents` | Uploaded docs with OCR results |
| `DocumentValidationResult` | `document_validation_results` | Per-field validation output |
| `FraudAssessment` | `fraud_assessments` | LangGraph fraud agent output |
| `UserFraudProfile` | `user_fraud_profiles` | Running risk stats per user |
| `Settlement` | `settlements` | Payment settlement record |
| `QRToken` | `qr_tokens` | Cashless QR authorization tokens |
| `AuditLog` | `audit_logs` | Immutable system action log |
| `ConsentRecord` | `consent_records` | DPDP consent with IP + version |
| `DocumentAccessLog` | `document_access_logs` | HIPAA-style doc access trail |
| `AuditRun` | `audit_runs` | One row per auditor sweep |
| `AuditFinding` | `audit_findings` | One row per suspicious pattern found |
| `AgentSession` | `agent_sessions` | Customer AI chat history (sliding window) |
| `KYCDocument` | `kyc_documents` | KYC uploads |

---

## API Routes Reference

```
/api/auth/*
  POST  /register         — create account
  POST  /login            — get JWT tokens (HttpOnly cookies)
  POST  /refresh          — rotate tokens
  POST  /logout           — clear cookies
  GET   /me               — current user

/api/policies/*
  GET   /                 — list my policies

/api/claims/*
  POST  /                 — file a new claim (CUSTOMER only)
  GET   /                 — list claims (scoped by role)
  GET   /{id}             — claim detail
  PATCH /{id}/status      — update status (ADMIN/ADJUSTER)
  PATCH /{id}             — update amount/description (owner)

/api/claim-documents/*
  POST  /inline-ocr       — OCR preview, no DB write
  POST  /                 — upload document
  GET   /claim/{id}       — list docs for a claim
  GET   /{id}/download    — download encrypted file

/api/fraud/*
  POST  /analyze/{id}                         — rule-based fraud analysis
  POST  /agent-analyze/{claimId}/{docId}      — LangGraph 6-node agent
  GET   /{claim_id}                           — get assessment

/api/settlements/{claim_id}
  POST  /                 — initiate settlement (INSURER_ADMIN)

/api/qr/*
  POST  /generate/{id}    — generate payment QR
  POST  /verify           — verify QR token

/api/cashless/*
  GET   /network-claims   — provider's assigned claims
  POST  /generate-qr      — hospital generates cashless QR
  GET   /scan/{token}     — customer scans QR
  POST  /accept           — customer accepts estimate
  POST  /authorize        — insurer authorizes

/api/compliance/*
  POST  /consent          — give DPDP consent
  GET   /consent          — check consent status
  GET   /audit            — audit trail
  POST  /deletion         — erasure request

/api/dashboard/*
  GET   /overview         — platform overview stats
  GET   /fraud-distribution
  GET   /sla
  GET   /compliance-summary
  GET   /customer         — personal metrics

/api/agent/*
  GET   /sessions         — list chat sessions
  POST  /sessions         — create session
  POST  /sessions/{id}/message  — send message (text)
  POST  /voice            — voice message (STT → agent → TTS)
  DELETE /sessions/{id}   — delete session

/api/adjuster/*
  POST  /chat             — chat with adjuster agent
  POST  /report/{id}      — generate claim report
  GET   /report/{id}      — get cached report

/api/speech/*
  POST  /transcribe       — audio → text (GCP STT / Gemini fallback)

/api/audit/*
  POST  /trigger          — start audit sweep (background, returns run_id)
  GET   /runs             — list sweep runs
  GET   /runs/{id}        — run detail + findings
  GET   /findings         — findings with filters
  GET   /findings/{id}    — single finding

/health                   — health check (no auth)
/metrics                  — Prometheus metrics (no auth)
/api/docs                 — Swagger UI
/api/redoc                — ReDoc
```

---

## Seed Credentials

Run from `insureflow-backend/`:
```bash
venv\Scripts\python scripts\seed_data.py
```

| Email | Password | Role |
|---|---|---|
| `admin@insureflow.ai` | `Admin@123` | INSURER_ADMIN |
| `adjuster@insureflow.ai` | `Admin@123` | CLAIM_ADJUSTER |
| `auditor@insureflow.ai` | `Auditor@123` | AUDITOR |
| `customer1@test.ai` | `Test1234!` | CUSTOMER |
| `customer2@test.ai` | `Test1234!` | CUSTOMER |
| `hospital@provider.ai` | `Provider@123` | PROVIDER |

Seeded also: 4 active policies per customer (HEALTH, MOTOR, REIMBURSEMENT, CASHLESS) + 3 sample claims per customer + 1 settlement.
