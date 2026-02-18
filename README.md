# InsureFlow-AI

**Compliance-First, Explainable, QR-Enabled Insurance Claim Intelligence Platform**

## Overview

InsureFlow-AI is a production-grade insurance claim processing backend built with FastAPI. It combines regulatory-compliant architecture with a hybrid fraud detection engine, QR-based cashless authorization, OCR document processing, and speech-to-text claim filing -- all enforced through role-based access control and immutable audit trails.

### Core Capabilities

- **Hybrid Fraud Detection Engine** -- Three-layer analysis (deterministic rules, statistical anomalies, AI narrative) with privacy-first design and full auditability
- **QR-Based Cashless Authorization** -- HMAC-SHA256 signed, single-use, time-limited tokens
- **OCR Document Processing** -- Automated extraction and parsing of medical invoices, prescriptions, and vehicle documents
- **Speech-to-Text Claim Filing** -- Voice-based claim submission with structured data extraction
- **Compliance-by-Design** -- Consent tracking (DPDP Act), data retention policies, human-in-the-loop enforcement
- **Enterprise Audit Trails** -- Immutable logging for every action; AI never auto-rejects

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL
- Docker and Docker Compose (optional, for containerised deployment)
- Tesseract OCR (for document processing)

### Environment Setup

```bash
git clone <repository-url>
cd insureflow-ai
```

Create a `.env` file with the following required variables:

```ini
SECRET_KEY=<generate-with-secrets.token_urlsafe(32)>
QR_SECRET_KEY=<generate-with-secrets.token_urlsafe(32)>
ENCRYPTION_KEY=<generate-with-cryptography.fernet.Fernet.generate_key()>
DATABASE_URL=postgresql://user:password@localhost:5432/insureflow
```

Generate secure keys:

```python
import secrets
print(secrets.token_urlsafe(32))

from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### Run with Docker

```bash
cd docker
docker-compose up --build
```

### Run Locally (Conda)

```bash
conda activate insureflow
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Create Admin User

```bash
python scripts/create_admin.py
```

Application: `http://localhost:8000`

API Documentation: `http://localhost:8000/api/docs`

---

## Project Structure

```
insureflow-ai/
├── app/
│   ├── main.py                          # FastAPI application entry point
│   ├── config.py                        # Application settings (from .env)
│   ├── dependencies.py                  # FastAPI dependency injection
│   │
│   ├── api/                             # HTTP layer
│   │   ├── router.py                    # Root API router
│   │   └── v1/
│   │       ├── auth.py                  # Register, login, refresh, profile
│   │       ├── claims.py               # Create, list, update, analyze claims
│   │       ├── fraud.py                # Fraud assessment retrieval
│   │       ├── qr.py                   # QR authorization and validation
│   │       ├── documents.py            # Document upload and access
│   │       ├── settlements.py          # Settlement processing
│   │       ├── compliance.py           # Consent and compliance endpoints
│   │       ├── dashboard.py            # Admin dashboard data
│   │       └── users.py               # User management
│   │
│   ├── core/                            # Cross-cutting infrastructure
│   │   ├── security.py                  # JWT tokens, password hashing
│   │   ├── rbac.py                      # Role-based access control
│   │   ├── exceptions.py               # Custom exception hierarchy
│   │   ├── logging.py                   # Structured + audit logging
│   │   └── constants.py                # Enums (ClaimType, ClaimStatus, etc.)
│   │
│   ├── models/                          # SQLAlchemy ORM models
│   │   ├── base.py                      # Base model with timestamps
│   │   ├── user.py                      # User accounts
│   │   ├── consent.py                   # DPDP consent records
│   │   ├── claim.py                     # Insurance claims
│   │   ├── document.py                  # Uploaded documents
│   │   ├── fraud.py                     # Fraud assessment records
│   │   ├── qr.py                        # QR authorization tokens
│   │   ├── settlement.py               # Settlement records
│   │   ├── audit.py                     # Audit log entries
│   │   └── access_log.py              # Document access log
│   │
│   ├── schemas/                         # Pydantic request/response models
│   │   ├── auth.py, claim.py, fraud.py
│   │   ├── document.py, qr.py
│   │   └── dashboard.py, settlement.py, user.py
│   │
│   ├── services/                        # Business logic layer
│   │   ├── auth_service.py              # Authentication and registration
│   │   ├── claim_service.py             # Claim lifecycle management
│   │   ├── fraud_service.py             # Fraud analysis orchestration
│   │   ├── document_service.py          # Document storage and retrieval
│   │   ├── qr_service.py               # QR token generation and validation
│   │   ├── settlement_service.py        # Settlement processing
│   │   ├── consent_service.py           # Consent management
│   │   ├── audit_service.py             # Audit trail recording
│   │   └── dashboard_service.py        # Dashboard aggregations
│   │
│   ├── ai_agents/                       # Fraud detection system
│   │   ├── orchestrator.py              # Legacy wrapper -> fraud engine
│   │   ├── rule_agent.py               # Legacy wrapper -> layer1
│   │   ├── anomaly_agent.py            # Legacy wrapper -> layer2
│   │   ├── behavior_agent.py           # Legacy wrapper -> layer2
│   │   ├── explanation_agent.py        # Legacy wrapper -> layer3
│   │   ├── utils.py                     # Shared utilities
│   │   └── fraud/                       # Production fraud engine
│   │       ├── __init__.py              # Public API exports
│   │       ├── config.py               # All thresholds, weights, versioning
│   │       ├── schemas.py              # Frozen Pydantic layer schemas
│   │       ├── privacy.py              # PII sanitisation gateway
│   │       ├── layer1_deterministic.py  # Rule-based checks
│   │       ├── layer2_statistical.py    # Anomaly + behavioral analysis
│   │       ├── layer3_narrative.py      # AI explanation with timeout fallback
│   │       ├── aggregator.py           # Weighted score combiner
│   │       ├── adapter.py              # Engine -> legacy schema converter
│   │       ├── audit_logger.py         # Fraud-specific audit logging
│   │       └── orchestrator.py         # Layer coordinator
│   │
│   ├── compliance/                      # Regulatory enforcement
│   │   ├── consent_validator.py         # DPDP Act consent enforcement
│   │   ├── access_monitor.py           # Document access tracking
│   │   ├── human_override.py           # Human-in-the-loop enforcement
│   │   └── retention_policy.py         # Data retention management
│   │
│   ├── ocr/                            # Document processing
│   │   ├── preprocess.py               # Image preprocessing
│   │   ├── extractor.py                # Text extraction (Tesseract)
│   │   ├── parser.py                   # Structured data parsing
│   │   └── pipeline.py                # End-to-end OCR pipeline
│   │
│   ├── speech/                          # Voice processing
│   │   ├── transcriber.py              # Speech-to-text
│   │   └── claim_parser.py            # Transcript -> structured claim
│   │
│   ├── utils/                           # Shared utilities
│   │   ├── encryption.py               # Fernet file encryption
│   │   ├── file_storage.py             # Encrypted file storage
│   │   ├── qr_signer.py               # HMAC-SHA256 QR signing
│   │   └── validators.py              # Input validation helpers
│   │
│   └── db/
│       ├── session.py                   # SQLAlchemy session factory
│       ├── seed.py                      # Database seeding script
│       └── migrations/                 # Alembic migration files
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── scripts/
│   ├── create_admin.py                  # Admin user creation
│   └── run_worker.py                   # Background worker
│
├── tests/
│   ├── pytest.ini                       # Test configuration
│   ├── unit/                            # Unit tests (no DB, no HTTP)
│   ├── integration/                     # Integration tests (DB required)
│   └── e2e/                            # End-to-end tests (full stack)
│
├── alembic.ini
├── requirements.txt
└── .env
```

---

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register a new user |
| POST | `/api/v1/auth/login` | Login and receive JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user profile |

### Claims

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/claims/` | Submit a new claim (requires consent) |
| GET | `/api/v1/claims/` | List claims (filtered by role) |
| GET | `/api/v1/claims/{id}` | Get claim details |
| PUT | `/api/v1/claims/{id}/status` | Update claim status (admin) |
| POST | `/api/v1/claims/{id}/analyze` | Trigger fraud analysis (admin) |

### Fraud Detection

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/fraud/assessment/{claim_id}` | Get fraud assessment with explanation |

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/` | Upload claim document |
| GET | `/api/v1/documents/{id}` | Retrieve document (access-logged) |

### QR Authorization

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/qr/authorize` | Create QR authorization (admin) |
| POST | `/api/v1/qr/validate` | Validate QR token (provider) |

### Settlements

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/settlements/` | Initiate settlement |
| GET | `/api/v1/settlements/{id}` | Get settlement status |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |

---

## User Roles

| Role | Permissions |
|------|-------------|
| CUSTOMER | Submit claims, view own claims, upload documents |
| PROVIDER | Validate QR authorizations |
| INSURER_ADMIN | Approve/reject claims, trigger fraud analysis, create QR authorizations, manage settlements |
| AUDITOR | Read-only access to all data including fraud assessments and audit logs |

---

## Fraud Detection Engine

The fraud detection system is a three-layer hybrid engine located at `app/ai_agents/fraud/`.

### Layer Architecture

```
Claim Context
    |
    v
Layer 1: Deterministic Rules
    |  Pure business logic (amount thresholds, policy format)
    |  Returns: score + signal list
    v
Layer 2: Statistical Analysis
    |  Z-score anomaly detection + behavioral patterns
    |  Reads pre-fetched history (no DB queries)
    |  Returns: score + anomaly list
    v
Layer 3: Narrative / AI
    |  Generates structured explanation
    |  Routes through privacy.py before any processing
    |  Local-only by default; external AI opt-in with timeout fallback
    |  Returns: score + structured reasoning
    v
Aggregator
    |  Weighted combination (0.40 / 0.35 / 0.25)
    |  Degrades gracefully if AI fails (renormalises weights)
    |  Returns: clamped score in [0.0, 1.0]
    v
Frozen FraudAssessmentResponse
    (config_version embedded for traceability)
```

### Production Safety

- All scores normalised to [0.0, 1.0] before aggregation
- Deterministic: same input always produces same output (no randomness)
- AI timeout fallback: sets `ai_degraded_mode = True`, zeroes narrative weight, renormalises
- Config versioning: `CONFIG_VERSION` and `BASELINE_VERSION` embedded in every response
- Privacy-first: PII sanitised before any AI processing (strict / balanced / raw modes)
- Immutable responses: `FraudAssessmentResponse` is a frozen Pydantic model
- Audit logging: every assessment logged without raw claim data

### Fraud Score Workflow

```
Claim Submitted
    |
    v
Three-Layer Analysis
    |
    v
Fraud Score (0.0 - 1.0)
    |
    v
Score >= 0.7  -->  MANUAL_REVIEW_REQUIRED
Score < 0.7   -->  FRAUD_ANALYZED
    |
    v
Human Admin Decision (AI never auto-rejects)
```

---

## Security

### Authentication and Authorization

- JWT access tokens with 15-minute expiry
- Rotating refresh tokens with 7-day expiry
- Role-based access control enforced at the service layer
- bcrypt password hashing

### QR Authorization

- HMAC-SHA256 signed tokens
- Single-use enforcement
- Time-limited validity
- Provider identity validation

### Data Protection

- Fernet-encrypted file storage
- Encrypted document storage with access logging
- Immutable audit logs (separate log file, no rotation)
- PII sanitisation layer in fraud engine

---

## Compliance

- Consent logging aligned with DPDP Act
- Immutable audit trail for all user and system actions
- Human-in-the-loop enforcement (AI never auto-rejects claims)
- Explainable AI decisions with structured reasoning stored per assessment
- Document access logging (HIPAA-aligned)
- No financial credential storage
- Configurable data retention policies (default: 7 years)
- Role-based authorization at every endpoint

---

## Testing

```bash
# Activate environment
conda activate insureflow

# Run all tests
pytest

# Run unit tests only
pytest tests/unit/ -v

# Run with coverage
pytest --cov=app tests/

# Run fraud engine tests specifically
pytest tests/unit/test_fraud_agents.py -v
```

Test markers:
- `unit` -- No database or HTTP required
- `integration` -- Database required
- `e2e` -- Full HTTP stack
- `compliance` -- Compliance-specific tests

---

## Database Migrations

```bash
# Generate a new migration
alembic revision --autogenerate -m "description"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

---

## Production Deployment

### Security Hardening

1. Set all secret keys in `.env` (never use defaults)
2. Set `DEBUG=false`
3. Configure HTTPS via reverse proxy (nginx with SSL)
4. Restrict `ALLOWED_ORIGINS` to your frontend domain
5. Enable rate limiting (`RATE_LIMIT_PER_MINUTE` in config)
6. Configure firewall rules for database and application ports
7. Set up PostgreSQL backups

### Monitoring

- Health check: `GET /health`
- Application logs: configured via `LOG_FILE` (default: `/app/logs/insureflow.log`, 10MB rotation, 5 backups)
- Audit logs: `/app/logs/audit.log` (immutable, no rotation)
- Fraud engine logs: structured entries with `config_version` for traceability

### Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| SECRET_KEY | Yes | -- | JWT signing key |
| QR_SECRET_KEY | Yes | -- | QR token HMAC key |
| ENCRYPTION_KEY | Yes | -- | Fernet file encryption key |
| DATABASE_URL | Yes | -- | PostgreSQL connection string |
| DEBUG | No | false | Enable debug mode |
| LOG_LEVEL | No | INFO | Logging level |
| FRAUD_THRESHOLD | No | 0.7 | Score threshold for manual review |
| ALLOWED_ORIGINS | No | http://localhost:3000 | CORS allowed origins |
| RATE_LIMIT_PER_MINUTE | No | 60 | API rate limit |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.104 |
| Language | Python 3.11+ |
| Database | PostgreSQL (SQLAlchemy 2.0 ORM) |
| Migrations | Alembic |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Validation | Pydantic 2.5 |
| OCR | Tesseract (pytesseract) + OpenCV |
| Encryption | cryptography (Fernet) |
| Testing | pytest + pytest-asyncio + httpx |
| Deployment | Docker + Docker Compose |

---

## Contributing

All contributions must:

1. Include tests for new functionality
2. Follow existing architecture patterns
3. Maintain compliance requirements (consent, audit, human-in-loop)
4. Update documentation
5. Pass the existing test suite

---

## License

[Your License Here]

---

**Built with compliance-first architecture. Not a demo. Not a prototype. Production-ready.**