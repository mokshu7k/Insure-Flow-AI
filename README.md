# InsureFlow-AI

**Compliance-First, Explainable, QR-Enabled Insurance Claim Intelligence Platform**

## 🎯 Core Value Proposition

InsureFlow-AI solves the critical gap in insurance claim systems by combining:

1. **Compliance-by-Design Architecture** - Built for regulatory scrutiny
2. **Explainable AI Fraud Detection** - Multi-agent system with human-readable reasoning
3. **QR-based Cashless Authorization** - Secure, single-use tokens
4. **Human-in-the-Loop Enforcement** - AI assists, never auto-rejects
5. **Enterprise Audit Trails** - Immutable logging for all actions

## 🏗️ Architecture

```
FastAPI Backend
├── Multi-Agent Fraud Detection
├── QR Authorization System
├── Compliance Enforcement Layer
├── Audit Logging (Immutable)
└── PostgreSQL Database
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)

### 1. Clone Repository

```bash
git clone <repository-url>
cd insureflow_ai
```

### 2. Environment Setup

```bash
cp .env.example .env
# Edit .env with your configuration
```

**CRITICAL**: Generate secure keys:

```python
# Generate SECRET_KEY and QR_SECRET_KEY
import secrets
print(secrets.token_urlsafe(32))

# Generate ENCRYPTION_KEY
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### 3. Start with Docker

```bash
docker-compose up --build
```

Application will be available at: `http://localhost:8000`

API Documentation: `http://localhost:8000/api/docs`

### 4. Create Admin User

```bash
docker-compose exec app python scripts/create_admin.py
```

## 📁 Project Structure

```
insureflow_ai/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration
│   ├── dependencies.py         # FastAPI dependencies
│   │
│   ├── api/                    # HTTP layer
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── claims.py
│   │       ├── fraud.py
│   │       └── qr.py
│   │
│   ├── core/                   # Core utilities
│   │   ├── security.py         # JWT, password hashing
│   │   ├── rbac.py             # Role-based access control
│   │   ├── exceptions.py       # Custom exceptions
│   │   ├── logging.py          # Logging setup
│   │   └── constants.py        # Application constants
│   │
│   ├── models/                 # SQLAlchemy ORM
│   │   ├── user.py
│   │   ├── consent.py
│   │   ├── claim.py
│   │   ├── document.py
│   │   ├── fraud.py
│   │   ├── qr.py
│   │   ├── settlement.py
│   │   ├── audit.py
│   │   └── access_log.py
│   │
│   ├── schemas/                # Pydantic models
│   │   ├── auth.py
│   │   ├── claim.py
│   │   ├── fraud.py
│   │   └── qr.py
│   │
│   ├── services/               # Business logic
│   │   ├── auth_service.py
│   │   ├── consent_service.py
│   │   ├── claim_service.py
│   │   ├── fraud_service.py
│   │   ├── qr_service.py
│   │   └── audit_service.py
│   │
│   ├── ai_agents/              # Multi-agent fraud system
│   │   ├── orchestrator.py
│   │   ├── rule_agent.py
│   │   ├── anomaly_agent.py
│   │   ├── behavior_agent.py
│   │   └── explanation_agent.py
│   │
│   ├── utils/                  # Utilities
│   │   └── qr_signer.py
│   │
│   └── db/
│       └── session.py          # Database session
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## 🔐 Security Features

### Authentication
- JWT with short-lived access tokens (15 min)
- Rotating refresh tokens (7 days)
- RBAC enforcement at service layer

### QR Authorization
- HMAC-SHA256 signed tokens
- Single-use enforcement
- Time-limited validity
- Provider validation

### Data Protection
- Encrypted file storage
- Password hashing (bcrypt)
- Immutable audit logs
- Document access logging

## 🤖 AI Fraud Detection

### Multi-Agent Architecture

1. **Rule Agent** - Deterministic fraud checks
2. **Anomaly Agent** - Statistical outlier detection
3. **Behavior Agent** - User pattern analysis
4. **Explanation Agent** - Human-readable reasoning

### Key Features

- **Explainable**: Every fraud score has detailed explanation
- **Non-deterministic**: Never auto-rejects claims
- **Compliant**: Stores reasoning for audit trails
- **Transparent**: Shows which signals triggered flags

### Fraud Score Workflow

```
Claim Submitted
    ↓
Multi-Agent Analysis
    ↓
Fraud Score Calculated (0.0 - 1.0)
    ↓
Score >= 0.7 → MANUAL_REVIEW_REQUIRED
Score < 0.7  → FRAUD_ANALYZED
    ↓
Human Admin Decision
```

## 📊 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register user
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/refresh` - Refresh token
- `GET /api/v1/auth/me` - Get current user

### Claims
- `POST /api/v1/claims/` - Create claim (requires consent)
- `GET /api/v1/claims/` - List claims
- `GET /api/v1/claims/{id}` - Get claim details
- `PUT /api/v1/claims/{id}/status` - Update status (admin)
- `POST /api/v1/claims/{id}/analyze` - Trigger fraud analysis (admin)

### Fraud Detection
- `GET /api/v1/fraud/assessment/{claim_id}` - Get fraud assessment

### QR Authorization
- `POST /api/v1/qr/authorize` - Create QR authorization (admin)
- `POST /api/v1/qr/validate` - Validate QR token (provider)

## 🎭 User Roles

| Role | Permissions |
|------|-------------|
| `CUSTOMER` | Submit claims, view own claims |
| `PROVIDER` | Validate QR authorizations |
| `INSURER_ADMIN` | Approve/reject claims, trigger fraud analysis, create QR |
| `AUDITOR` | Read-only access to all data |

## ✅ Compliance Checklist

- [x] Consent logging (DPDP Act)
- [x] Immutable audit trail
- [x] Human-in-the-loop enforcement
- [x] Explainable AI decisions
- [x] Document access logging (HIPAA-aligned)
- [x] No financial credential storage
- [x] Encrypted file storage
- [x] Role-based authorization
- [x] Data retention tracking

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## 📈 Production Deployment

### Security Hardening

1. **Change all default secrets** in `.env`
2. **Enable HTTPS** (configure nginx with SSL)
3. **Set DEBUG=false**
4. **Configure firewall** rules
5. **Enable rate limiting**
6. **Set up log monitoring**
7. **Configure backup** for PostgreSQL

### Monitoring

- Health check endpoint: `/health`
- Audit logs: `/app/logs/audit.log`
- Application logs: `/app/logs/insureflow.log`

### Database Migrations

```bash
# Generate migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## 🤝 Contributing

This is a production-grade system. All contributions must:

1. Include tests
2. Follow existing architecture patterns
3. Maintain compliance requirements
4. Update documentation

## 📄 License

[Your License Here]

## 🆘 Support

For issues or questions, contact: [Your Contact]

---

**Built with compliance-first architecture. Not a demo. Not a prototype. Production-ready.**